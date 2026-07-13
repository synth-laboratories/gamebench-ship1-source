from __future__ import annotations

import binascii
import hashlib
import struct
import subprocess
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .constants import MAP_SIZE, RESOURCES
from .engine import CraftaxCoopEnv

RenderMode = Literal["auto", "sprites", "symbolic"]
TILE_SIZE = 16
VIEW_SIZE = 11
TEAMMATE_ROWS = 2
INVENTORY_ROWS = 4
PANEL_WIDTH = VIEW_SIZE * TILE_SIZE
PANEL_HEIGHT = (TEAMMATE_ROWS + VIEW_SIZE + INVENTORY_ROWS) * TILE_SIZE
ASSET_DIR = Path(__file__).resolve().parents[1] / "shared" / "assets" / "craftax_coop"

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class RGBFrame:
    width: int
    height: int
    pixels: bytes

    def png(self) -> bytes:
        return encode_png(self)


_TERRAIN: dict[str, RGB] = {
    "grass": (69, 132, 62), "path": (126, 111, 84), "sand": (202, 181, 112),
    "gravel": (122, 119, 108), "water": (44, 105, 173), "fountain": (44, 105, 173),
    "lava": (215, 63, 33), "stone": (82, 87, 91), "wall": (82, 87, 91),
    "tree": (31, 91, 45), "fire_grass": (116, 60, 37), "fire_tree": (126, 43, 25),
    "ice_grass": (142, 202, 215), "ice_shrub": (103, 176, 198), "coal": (38, 40, 42),
    "iron": (143, 119, 93), "diamond": (69, 209, 218), "ruby": (190, 45, 62),
    "sapphire": (47, 89, 205), "chest": (164, 105, 38), "stairs_up": (225, 213, 155),
    "stairs_down": (225, 213, 155), "grave": (91, 84, 105), "necromancer": (98, 35, 118),
    "boss": (98, 35, 118), "crafting_table": (145, 91, 48), "furnace": (95, 88, 80),
}

_ASSET_NAMES = {
    "stairs_up": "ladder_up", "stairs_down": "ladder_down", "grave2": "grave",
    "grave3": "grave", "necromancer": "necromancer", "boss": "necromancer",
    "crafting_table": "table", "ripe_plant": "plant-ripe", "arrow2": "arrow",
    "fireball2": "fireball", "iceball2": "iceball", "torch": "torch_on_path",
    "archer": "knight_archer",
}

_FONT = {
    " ": (0, 0, 0, 0, 0), "-": (0, 0, 7, 0, 0), ":": (0, 2, 0, 2, 0),
    "0": (7, 5, 5, 5, 7), "1": (2, 6, 2, 2, 7), "2": (7, 1, 7, 4, 7),
    "3": (7, 1, 7, 1, 7), "4": (5, 5, 7, 1, 1), "5": (7, 4, 7, 1, 7),
    "6": (7, 4, 7, 5, 7), "7": (7, 1, 2, 2, 2), "8": (7, 5, 7, 5, 7),
    "9": (7, 5, 7, 1, 7), "A": (2, 5, 7, 5, 5), "B": (6, 5, 6, 5, 6),
    "C": (3, 4, 4, 4, 3), "D": (6, 5, 5, 5, 6), "E": (7, 4, 6, 4, 7),
    "F": (7, 4, 6, 4, 4), "G": (3, 4, 5, 5, 3), "H": (5, 5, 7, 5, 5),
    "I": (7, 2, 2, 2, 7), "J": (1, 1, 1, 5, 2), "K": (5, 5, 6, 5, 5),
    "L": (4, 4, 4, 4, 7), "M": (5, 7, 7, 5, 5), "N": (5, 7, 7, 7, 5),
    "O": (2, 5, 5, 5, 2), "P": (6, 5, 6, 4, 4), "Q": (2, 5, 5, 7, 3),
    "R": (6, 5, 6, 5, 5), "S": (3, 4, 2, 1, 6), "T": (7, 2, 2, 2, 2),
    "U": (5, 5, 5, 5, 7), "V": (5, 5, 5, 5, 2), "W": (5, 5, 7, 7, 5),
    "X": (5, 5, 2, 5, 5), "Y": (5, 5, 2, 2, 2), "Z": (7, 1, 2, 4, 7),
    "_": (0, 0, 0, 0, 7), ".": (0, 0, 0, 0, 2), "/": (1, 1, 2, 4, 4),
}


class Canvas:
    def __init__(self, width: int, height: int, color: RGB = (17, 20, 24)) -> None:
        self.width, self.height = width, height
        self.pixels = bytearray(color * (width * height))

    def put(self, x: int, y: int, color: RGB) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.pixels[offset : offset + 3] = bytes(color)

    def get(self, x: int, y: int) -> RGB:
        offset = (y * self.width + x) * 3
        return tuple(self.pixels[offset : offset + 3])  # type: ignore[return-value]

    def fill(self, x: int, y: int, width: int, height: int, color: RGB) -> None:
        row = bytes(color * max(0, width))
        for py in range(max(0, y), min(self.height, y + height)):
            left, right = max(0, x), min(self.width, x + width)
            if right > left:
                offset = (py * self.width + left) * 3
                self.pixels[offset : offset + (right - left) * 3] = row[: (right - left) * 3]

    def text(self, x: int, y: int, value: str, color: RGB, max_x: int) -> None:
        cursor = x
        for character in value.upper():
            glyph = _FONT.get(character, _FONT[" "])
            for row, bits in enumerate(glyph):
                for column in range(3):
                    if bits & (1 << (2 - column)) and cursor + column < max_x:
                        self.put(cursor + column, y + row, color)
            cursor += 4
            if cursor >= max_x:
                break

    def blit(self, rgba: tuple[int, int, tuple[RGBA, ...]], x: int, y: int) -> None:
        width, height, pixels = rgba
        for sy in range(height):
            for sx in range(width):
                red, green, blue, alpha = pixels[sy * width + sx]
                if alpha == 0:
                    continue
                if alpha == 255:
                    self.put(x + sx, y + sy, (red, green, blue))
                    continue
                base = self.get(x + sx, y + sy)
                self.put(x + sx, y + sy, tuple((channel * alpha + old * (255 - alpha)) // 255 for channel, old in zip((red, green, blue), base)))  # type: ignore[arg-type]


_SPRITES: dict[str, tuple[int, int, tuple[RGBA, ...]] | None] = {}


def _mode(requested: RenderMode) -> RenderMode:
    if requested not in ("auto", "sprites", "symbolic"):
        raise ValueError(f"unsupported render_mode {requested!r}")
    available = (ASSET_DIR / "grass.png").is_file()
    if requested == "sprites" and not available:
        raise FileNotFoundError(f"sprite assets not found at {ASSET_DIR}")
    if requested == "auto":
        return "sprites" if available else "symbolic"
    return requested


def _sprite(name: str) -> tuple[int, int, tuple[RGBA, ...]] | None:
    resolved = _ASSET_NAMES.get(name, name)
    if resolved not in _SPRITES:
        path = ASSET_DIR / f"{resolved}.png"
        _SPRITES[resolved] = _decode_png(path.read_bytes()) if path.is_file() else None
    return _SPRITES[resolved]


def _tile(canvas: Canvas, x: int, y: int, name: str, mode: RenderMode) -> None:
    if mode == "sprites" and (sprite := _sprite(name)) is not None:
        canvas.blit(sprite, x, y)
        return
    base = _TERRAIN.get(name, (92, 92, 78))
    canvas.fill(x, y, TILE_SIZE, TILE_SIZE, base)
    if name in ("tree", "stone", "coal", "iron", "diamond", "ruby", "sapphire", "chest"):
        canvas.fill(x + 2, y + 2, TILE_SIZE - 4, TILE_SIZE - 4, tuple(min(255, value + 36) for value in base))


def _entity(canvas: Canvas, x: int, y: int, name: str, color: RGB, mode: RenderMode) -> None:
    if mode == "sprites" and (sprite := _sprite(name)) is not None:
        canvas.blit(sprite, x, y)
        return
    canvas.fill(x + 2, y + 1, TILE_SIZE - 4, TILE_SIZE - 2, color)


def _dim(canvas: Canvas, x: int, y: int, light: float) -> None:
    factor = max(0.12, min(1.0, 0.22 + 0.78 * light))
    for py in range(y, y + TILE_SIZE):
        for px in range(x, x + TILE_SIZE):
            canvas.put(px, py, tuple(int(value * factor) for value in canvas.get(px, py)))


def _projectile_sprite(projectile: object) -> str:
    kind = str(getattr(projectile, "kind", "arrow"))
    if kind.startswith("arrow"):
        dx, dy = int(getattr(projectile, "dx", 0)), int(getattr(projectile, "dy", 1))
        return "arrow-right" if dx > 0 else "arrow-left" if dx < 0 else "arrow-down" if dy > 0 else "arrow-up"
    return _ASSET_NAMES.get(kind, kind)


def render_rgb(env: CraftaxCoopEnv, render_mode: RenderMode = "auto") -> RGBFrame:
    mode = _mode(render_mode)
    state = env._require_state()
    players = state.players
    canvas = Canvas(max(1, len(players)) * PANEL_WIDTH, PANEL_HEIGHT)
    colors = ((72, 169, 255), (255, 180, 52), (180, 94, 235), (72, 220, 141))
    radius = VIEW_SIZE // 2
    for panel, focus in enumerate(players):
        ox, panel_right = panel * PANEL_WIDTH, (panel + 1) * PANEL_WIDTH
        canvas.fill(ox, 0, PANEL_WIDTH, PANEL_HEIGHT, (19, 23, 28))
        teammates = [(index, player) for index, player in enumerate(players) if player.agent_id != focus.agent_id][:TEAMMATE_ROWS]
        for row, (index, teammate) in enumerate(teammates):
            y = row * TILE_SIZE
            _entity(canvas, ox, y, teammate.role if teammate.alive else "player-dead", colors[index % len(colors)], mode)
            canvas.text(ox + 18, y + 1, f"{teammate.agent_id} {teammate.role} L{teammate.level}", (226, 231, 236), panel_right)
            canvas.text(ox + 18, y + 9, f"H{int(max(0, teammate.health))} F{teammate.food} D{teammate.drink} E{teammate.energy} R{teammate.request_duration}", (177, 192, 205), panel_right)
        map_y = TEAMMATE_ROWS * TILE_SIZE
        for vy in range(VIEW_SIZE):
            for vx in range(VIEW_SIZE):
                world_x, world_y = focus.x - radius + vx, focus.y - radius + vy
                px, py = ox + vx * TILE_SIZE, map_y + vy * TILE_SIZE
                if not (0 <= world_x < MAP_SIZE and 0 <= world_y < MAP_SIZE):
                    canvas.fill(px, py, TILE_SIZE, TILE_SIZE, (4, 5, 7))
                    continue
                terrain = state.maps[focus.level][world_y][world_x]
                _tile(canvas, px, py, terrain, mode)
                item = state.item_maps[focus.level][world_y][world_x]
                if item:
                    _entity(canvas, px, py, item, (247, 219, 94), mode)
                plant = next((value for value in state.plants if (value.level, value.x, value.y) == (focus.level, world_x, world_y)), None)
                if plant is not None:
                    _entity(canvas, px, py, "plant-ripe" if plant.age >= 500 else "plant", (82, 190, 73), mode)
                for index, player in enumerate(players):
                    if player.level == focus.level and (player.x, player.y) == (world_x, world_y):
                        facing = "player-dead" if not player.alive else "player-sleep" if player.sleeping else f"player-{player.facing}"
                        _entity(canvas, px, py, facing, colors[index % len(colors)], mode)
                for monster in state.monsters:
                    if monster.level == focus.level and (monster.x, monster.y) == (world_x, world_y):
                        _entity(canvas, px, py, monster.kind, (210, 68, 68), mode)
                for projectile in state.projectiles:
                    if projectile.level == focus.level and (projectile.x, projectile.y) == (world_x, world_y):
                        _entity(canvas, px, py, _projectile_sprite(projectile), (255, 235, 120), mode)
                light = state.light_maps[focus.level][world_y][world_x]
                if focus.level == 0:
                    light *= state.light_level
                _dim(canvas, px, py, light)
        dashboard_y = (TEAMMATE_ROWS + VIEW_SIZE) * TILE_SIZE
        canvas.text(ox + 2, dashboard_y + 1, f"{focus.agent_id} {focus.role} L{focus.level} T{state.timestep}", (231, 235, 239), panel_right)
        canvas.text(ox + 2, dashboard_y + 17, f"HP{int(max(0, focus.health))} F{focus.food} D{focus.drink} E{focus.energy} M{focus.mana} XP{focus.xp}", (205, 215, 224), panel_right)
        canvas.text(ox + 2, dashboard_y + 33, f"P{focus.pickaxe} S{focus.sword} A{focus.armour} B{focus.bow} AR{focus.arrows}", (205, 215, 224), panel_right)
        inventory = " ".join(f"{resource[:3]}:{focus.inventory.get(resource, 0)}" for resource in RESOURCES if focus.inventory.get(resource, 0)) or "INV EMPTY"
        canvas.text(ox + 2, dashboard_y + 49, f"{inventory} R:{focus.request_type or 'NONE'} B{state.boss_health} W{state.boss_progress}", (255, 207, 93), panel_right)
    return RGBFrame(canvas.width, canvas.height, bytes(canvas.pixels))


def render_png_bytes(env: CraftaxCoopEnv, render_mode: RenderMode = "auto") -> bytes:
    return render_rgb(env, render_mode).png()


def encode_png(frame: RGBFrame) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    raw = b"".join(b"\x00" + frame.pixels[row * frame.width * 3 : (row + 1) * frame.width * 3] for row in range(frame.height))
    header = struct.pack(">IIBBBBB", frame.width, frame.height, 8, 2, 0, 0, 0)
    return signature + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 6)) + _chunk(b"IEND", b"")


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)


def _decode_png(data: bytes) -> tuple[int, int, tuple[RGBA, ...]]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("invalid PNG signature")
    offset, compressed, width, height, color_type = 8, bytearray(), 0, 0, 0
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind, payload = data[offset + 4 : offset + 8], data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", payload)
            if depth != 8 or interlace != 0 or color_type not in (2, 6):
                raise ValueError("unsupported sprite PNG format")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    channels = 4 if color_type == 6 else 3
    decoded, stride = zlib.decompress(bytes(compressed)), width * channels
    rows: list[bytes] = []
    cursor = 0
    for _ in range(height):
        filter_type, scanline = decoded[cursor], bytearray(decoded[cursor + 1 : cursor + 1 + stride])
        cursor += stride + 1
        previous = rows[-1] if rows else bytes(stride)
        for index, value in enumerate(scanline):
            left = scanline[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                scanline[index] = (value + left) & 255
            elif filter_type == 2:
                scanline[index] = (value + up) & 255
            elif filter_type == 3:
                scanline[index] = (value + ((left + up) // 2)) & 255
            elif filter_type == 4:
                estimate = left + up - upper_left
                distances = abs(estimate - left), abs(estimate - up), abs(estimate - upper_left)
                scanline[index] = (value + (left if distances[0] <= distances[1] and distances[0] <= distances[2] else up if distances[1] <= distances[2] else upper_left)) & 255
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter {filter_type}")
        rows.append(bytes(scanline))
    pixels: list[RGBA] = []
    for row in rows:
        for index in range(0, len(row), channels):
            values = row[index : index + channels]
            pixels.append((values[0], values[1], values[2], values[3] if channels == 4 else 255))
    return width, height, tuple(pixels)


def encode_gif(frames: list[RGBFrame], delay_centiseconds: int = 10) -> bytes:
    if not frames:
        raise ValueError("cannot encode an empty replay")
    if any((frame.width, frame.height) != (frames[0].width, frames[0].height) for frame in frames):
        raise ValueError("all replay frames must have identical dimensions")
    with tempfile.TemporaryDirectory(prefix="craftax_coop_gif_") as directory:
        root = Path(directory)
        for index, frame in enumerate(frames):
            (root / f"frame_{index:06d}.png").write_bytes(frame.png())
        output = root / "replay.gif"
        try:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-framerate", str(max(1, round(100 / delay_centiseconds))), "-i", str(root / "frame_%06d.png"), "-loop", "0", str(output)],
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise RuntimeError(f"GIF encoding failed: {error}") from error
        return output.read_bytes()


def png_sha256(frame: RGBFrame) -> str:
    return hashlib.sha256(frame.png()).hexdigest()
