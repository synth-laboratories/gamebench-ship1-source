"""Small symbolic and sprite render helpers for Crafter."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any, Literal

RenderMode = Literal["auto", "symbolic", "sprites"]

ASSETS_DIR = Path(__file__).resolve().parents[1] / "shared" / "assets" / "crafter"
NATIVE_SPRITE_PX = 16
DEFAULT_RENDER_TILE_SIZE = 16


RGB = tuple[int, int, int]
RGBRows = list[list[RGB]]
RGBFrame = tuple[int, int, RGBRows]

TILE_CHAR = {
    "water": "~",
    "grass": ".",
    "stone": "^",
    "path": ":",
    "sand": ",",
    "tree": "T",
    "lava": "L",
    "coal": "c",
    "iron": "i",
    "diamond": "d",
    "table": "#",
    "furnace": "F",
    "sapphire": "s",
    "ruby": "r",
    "chest": "C",
}

TILE_RGB = {
    "water": (46, 112, 176),
    "grass": (74, 152, 74),
    "stone": (116, 120, 126),
    "path": (137, 116, 84),
    "sand": (202, 186, 124),
    "tree": (34, 105, 52),
    "lava": (211, 69, 38),
    "coal": (53, 57, 61),
    "iron": (168, 131, 84),
    "diamond": (86, 192, 202),
    "table": (129, 83, 45),
    "furnace": (78, 72, 66),
    "sapphire": (70, 101, 204),
    "ruby": (196, 50, 73),
    "chest": (160, 96, 36),
}
UNKNOWN_RGB = (30, 34, 38)
PLAYER_RGB = (246, 240, 205)
ENTITY_RGB = (42, 25, 20)


def render_ascii(observation: dict[str, Any]) -> str:
    view = observation.get("view", {})
    tiles = view.get("tiles", [])
    if not tiles:
        return ""
    xs = [int(tile["pos"][0]) for tile in tiles]
    ys = [int(tile["pos"][1]) for tile in tiles]
    player_pos = observation.get("player", {}).get("pos", [])
    entities = {tuple(entity.get("pos", [])): str(entity.get("kind", "?"))[:1].upper() for entity in view.get("entities", [])}
    rows: list[str] = []
    by_pos = {(int(tile["pos"][0]), int(tile["pos"][1])): tile for tile in tiles}
    for y in range(min(ys), max(ys) + 1):
        chars: list[str] = []
        for x in range(min(xs), max(xs) + 1):
            if player_pos == [x, y]:
                chars.append("@")
            elif (x, y) in entities:
                chars.append(entities[(x, y)])
            else:
                chars.append(TILE_CHAR.get(str(by_pos.get((x, y), {}).get("kind")), "?"))
        rows.append("".join(chars))
    return "\n".join(rows)


def render_svg(engine: Any, *, tile_size: int = 14) -> str:
    observation = engine.observation
    ascii_map = render_ascii(observation)
    lines = ascii_map.splitlines() or [""]
    width = max(len(line) for line in lines) * tile_size
    height = len(lines) * tile_size
    text = "\n".join(
        f'<text x="4" y="{(idx + 1) * tile_size - 3}" font-family="monospace" font-size="12">{line}</text>'
        for idx, line in enumerate(lines)
    )
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="white"/>{text}</svg>'


def sprites_available() -> bool:
    return (ASSETS_DIR / "grass.png").is_file()


def render_rgb_frame(
    engine: Any,
    *,
    tile_size: int = 8,
    render_mode: RenderMode = "auto",
) -> RGBFrame:
    mode = render_mode
    if mode == "auto":
        mode = "sprites" if sprites_available() else "symbolic"
    if mode == "sprites":
        return _render_rgb_frame_sprites(engine, tile_size=tile_size)
    return _render_rgb_frame_symbolic(engine, tile_size=tile_size)


def _render_rgb_frame_symbolic(engine: Any, *, tile_size: int = 8) -> RGBFrame:
    """Render the local symbolic view as RGB rows without external deps."""
    observation = engine.observation
    view = observation.get("view", {})
    tiles = view.get("tiles", [])
    if not tiles:
        return 1, 1, [[UNKNOWN_RGB]]
    xs = [int(tile["pos"][0]) for tile in tiles]
    ys = [int(tile["pos"][1]) for tile in tiles]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    grid_width = max_x - min_x + 1
    grid_height = max_y - min_y + 1
    by_pos = {(int(tile["pos"][0]), int(tile["pos"][1])): tile for tile in tiles}
    player_pos = tuple(int(value) for value in observation.get("player", {}).get("pos", [0, 0]))
    entity_pos = {tuple(int(value) for value in entity.get("pos", [])) for entity in view.get("entities", [])}

    pixel_rows: list[list[tuple[int, int, int]]] = []
    for y in range(min_y, max_y + 1):
        tile_row: list[tuple[int, int, int]] = []
        for x in range(min_x, max_x + 1):
            if (x, y) == player_pos:
                rgb = PLAYER_RGB
            elif (x, y) in entity_pos:
                rgb = ENTITY_RGB
            else:
                kind = str(by_pos.get((x, y), {}).get("kind", "unknown"))
                rgb = TILE_RGB.get(kind, UNKNOWN_RGB)
            tile_row.extend([rgb] * tile_size)
        for _ in range(tile_size):
            pixel_rows.append(list(tile_row))
    return grid_width * tile_size, grid_height * tile_size, pixel_rows


def _player_sprite_name(facing: Any) -> str:
    if not isinstance(facing, (list, tuple)) or len(facing) < 2:
        return "player-down"
    fx, fy = int(facing[0]), int(facing[1])
    if fy == -1:
        return "player-up"
    if fy == 1:
        return "player-down"
    if fx == -1:
        return "player-left"
    if fx == 1:
        return "player-right"
    return "player-down"


def _entity_sprite_name(entity: dict[str, Any]) -> str:
    kind = str(entity.get("kind", "unknown"))
    if kind == "plant":
        grown = int((entity.get("metadata") or {}).get("grown", 0))
        return "plant-ripe" if grown >= 300 else "plant"
    return kind


def _render_rgb_frame_sprites(engine: Any, *, tile_size: int = 16) -> RGBFrame:
    observation = engine.observation
    view = observation.get("view", {})
    tiles = view.get("tiles", [])
    if not tiles:
        return 1, 1, [[UNKNOWN_RGB]]
    xs = [int(tile["pos"][0]) for tile in tiles]
    ys = [int(tile["pos"][1]) for tile in tiles]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    grid_width = max_x - min_x + 1
    grid_height = max_y - min_y + 1
    by_pos = {(int(tile["pos"][0]), int(tile["pos"][1])): tile for tile in tiles}
    player_pos = tuple(int(value) for value in observation.get("player", {}).get("pos", [0, 0]))
    player_facing = observation.get("player", {}).get("facing", [0, 1])
    entities = list(view.get("entities", []))

    width = grid_width * tile_size
    height = grid_height * tile_size
    canvas: RGBRows = [[UNKNOWN_RGB for _ in range(width)] for _ in range(height)]

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            kind = str(by_pos.get((x, y), {}).get("kind", "unknown"))
            sprite = _tile_sprite_name(kind)
            _blit_sprite(
                canvas,
                (x - min_x) * tile_size,
                (y - min_y) * tile_size,
                sprite,
                tile_size=tile_size,
                alpha=False,
            )

    for entity in entities:
        pos = entity.get("pos", [])
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        ex, ey = int(pos[0]), int(pos[1])
        if (ex, ey) == player_pos:
            continue
        sprite = _entity_sprite_name(entity)
        _blit_sprite(
            canvas,
            (ex - min_x) * tile_size,
            (ey - min_y) * tile_size,
            sprite,
            tile_size=tile_size,
            alpha=True,
        )

    _blit_sprite(
        canvas,
        (player_pos[0] - min_x) * tile_size,
        (player_pos[1] - min_y) * tile_size,
        _player_sprite_name(player_facing),
        tile_size=tile_size,
        alpha=True,
    )
    return width, height, canvas


def _tile_sprite_name(kind: str) -> str:
    if (ASSETS_DIR / f"{kind}.png").is_file():
        return kind
    return "unknown"


_sprite_cache: dict[str, tuple[int, int, list[list[tuple[int, int, int, int]]]]] = {}


def _load_sprite(name: str) -> tuple[int, int, list[list[tuple[int, int, int, int]]]]:
    cached = _sprite_cache.get(name)
    if cached is not None:
        return cached
    path = ASSETS_DIR / f"{name}.png"
    if not path.is_file():
        path = ASSETS_DIR / "unknown.png"
    decoded = _decode_png_rgba(path.read_bytes())
    _sprite_cache[name] = decoded
    return decoded


def _blit_sprite(
    canvas: RGBRows,
    dest_x: int,
    dest_y: int,
    sprite_name: str,
    *,
    tile_size: int,
    alpha: bool,
) -> None:
    _, _, sprite_rows = _load_sprite(sprite_name)
    native = len(sprite_rows)
    if native <= 0:
        return
    canvas_h = len(canvas)
    canvas_w = len(canvas[0]) if canvas else 0
    for dy in range(tile_size):
        sy = min(native - 1, (dy * native) // tile_size)
        for dx in range(tile_size):
            sx = min(native - 1, (dx * native) // tile_size)
            sr, sg, sb, sa = sprite_rows[sy][sx]
            if alpha and sa == 0:
                continue
            y = dest_y + dy
            x = dest_x + dx
            if y < 0 or y >= canvas_h or x < 0 or x >= canvas_w:
                continue
            if alpha and sa < 255:
                dr, dg, db = canvas[y][x]
                blend = sa / 255.0
                canvas[y][x] = (
                    int(sr * blend + dr * (1.0 - blend)),
                    int(sg * blend + dg * (1.0 - blend)),
                    int(sb * blend + db * (1.0 - blend)),
                )
            else:
                canvas[y][x] = (sr, sg, sb)


def _decode_png_rgba(data: bytes) -> tuple[int, int, list[list[tuple[int, int, int, int]]]]:
    width = height = 0
    bit_depth = 0
    color_type = 0
    idat = bytearray()
    for kind, payload in _png_chunks(data):
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            idat.extend(payload)
    if bit_depth != 8 or color_type not in (2, 6):
        raise ValueError(f"unsupported PNG: depth={bit_depth} type={color_type}")
    bpp = 3 if color_type == 2 else 4
    stride = width * bpp
    raw = zlib.decompress(bytes(idat))
    rows: list[list[tuple[int, int, int, int]]] = []
    idx = 0
    prev = bytes(stride)
    for _ in range(height):
        filter_type = raw[idx]
        idx += 1
        scanline = raw[idx : idx + stride]
        idx += stride
        recon = _png_unfilter_scanline(filter_type, scanline, prev, bpp)
        prev = recon
        if color_type == 2:
            row: list[tuple[int, int, int, int]] = []
            for px in range(width):
                off = px * 3
                row.append((recon[off], recon[off + 1], recon[off + 2], 255))
            rows.append(row)
        else:
            row = []
            for px in range(width):
                off = px * 4
                row.append((recon[off], recon[off + 1], recon[off + 2], recon[off + 3]))
            rows.append(row)
    return width, height, rows


def _png_chunks(data: bytes):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos = 8
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        yield kind, payload


def _png_paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _png_unfilter_scanline(filter_type: int, row: bytes, prev: bytes, bpp: int) -> bytes:
    out = bytearray(len(row))
    for index, value in enumerate(row):
        left = out[index - bpp] if index >= bpp else 0
        up = prev[index] if prev else 0
        up_left = prev[index - bpp] if prev and index >= bpp else 0
        if filter_type == 0:
            recon = value
        elif filter_type == 1:
            recon = (value + left) & 0xFF
        elif filter_type == 2:
            recon = (value + up) & 0xFF
        elif filter_type == 3:
            recon = (value + ((left + up) // 2)) & 0xFF
        elif filter_type == 4:
            recon = (value + _png_paeth(left, up, up_left)) & 0xFF
        else:
            raise ValueError(f"unsupported PNG filter {filter_type}")
        out[index] = recon
    return bytes(out)


def render_png_bytes(engine: Any, *, tile_size: int = 8, render_mode: RenderMode = "auto") -> bytes:
    """Render the local symbolic view as a tiny RGB PNG without external deps."""

    width, height, pixel_rows = render_rgb_frame(engine, tile_size=tile_size, render_mode=render_mode)
    return encode_png_rgb(width, height, pixel_rows)


def encode_png_rgb(width: int, height: int, rows: RGBRows) -> bytes:
    return _encode_png_rgb(width, height, rows)


def encode_gif_via_ffmpeg(frames: list[RGBFrame], *, delay_cs: int = 10) -> bytes:
    """Encode RGB frames as GIF via ffmpeg palettegen/paletteuse."""
    import subprocess
    import tempfile

    if not frames:
        raise ValueError("cannot write GIF with zero frames")
    fps = max(1, min(50, round(100 / max(1, delay_cs))))
    with tempfile.TemporaryDirectory(prefix="crafter_replay_gif_") as tmp:
        tmp_path = Path(tmp)
        for idx, (width, height, rows) in enumerate(frames):
            (tmp_path / f"frame_{idx:04d}.png").write_bytes(encode_png_rgb(width, height, rows))
        out = tmp_path / "replay.gif"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                str(fps),
                "-i",
                str(tmp_path / "frame_%04d.png"),
                "-frames:v",
                str(len(frames)),
                "-vf",
                f"fps={fps},split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=none",
                str(out),
            ],
            check=True,
        )
        return out.read_bytes()


def encode_gif_rgb_frames(frames: list[RGBFrame], *, delay_cs: int = 10) -> bytes:
    """Encode RGB frames as a small GIF89a animation without external deps."""

    usable = [frame for frame in frames if frame[0] > 0 and frame[1] > 0 and frame[2]]
    if not usable:
        usable = [(1, 1, [[UNKNOWN_RGB]])]
    width, height, _ = usable[0]
    usable = [frame for frame in usable if frame[0] == width and frame[1] == height]
    palette: list[RGB] = []
    palette_index: dict[RGB, int] = {}
    for _, _, rows in usable:
        for row in rows:
            for rgb in row:
                if rgb not in palette_index:
                    if len(palette) >= 256:
                        raise ValueError("GIF palette cannot exceed 256 colors")
                    palette_index[rgb] = len(palette)
                    palette.append(rgb)
    color_count = 2
    while color_count < len(palette):
        color_count *= 2
    color_count = min(max(color_count, 2), 256)
    palette.extend([(0, 0, 0)] * (color_count - len(palette)))
    color_bits = max(1, (color_count - 1).bit_length())
    min_code_size = max(2, color_bits)
    header = bytearray()
    header.extend(b"GIF89a")
    header.extend(struct.pack("<HH", width, height))
    header.append(0x80 | ((color_bits - 1) << 4) | ((color_count.bit_length() - 2) & 0x07))
    header.extend(b"\x00\x00")
    for red, green, blue in palette:
        header.extend((red, green, blue))
    header.extend(b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00")
    delay = max(1, min(int(delay_cs), 65535))
    for _, _, rows in usable:
        indexed = bytes(palette_index[rgb] for row in rows for rgb in row)
        header.extend(b"\x21\xf9\x04\x00")
        header.extend(struct.pack("<H", delay))
        header.extend(b"\x00\x00")
        header.append(0x2C)
        header.extend(struct.pack("<HHHH", 0, 0, width, height))
        header.append(0)
        header.append(min_code_size)
        encoded = _gif_lzw_encode(indexed, min_code_size)
        for start in range(0, len(encoded), 255):
            chunk = encoded[start : start + 255]
            header.append(len(chunk))
            header.extend(chunk)
        header.append(0)
    header.append(0x3B)
    return bytes(header)


def _encode_png_rgb(width: int, height: int, rows: list[list[tuple[int, int, int]]]) -> bytes:
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for red, green, blue in row:
            raw.extend((red, green, blue))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", header),
            _png_chunk(b"IDAT", zlib.compress(bytes(raw), level=6)),
            _png_chunk(b"IEND", b""),
        ]
    )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind)
    checksum = zlib.crc32(payload, checksum) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def _gif_lzw_encode(indices: bytes, min_code_size: int) -> bytes:
    clear_code = 1 << min_code_size
    end_code = clear_code + 1

    def reset_table() -> tuple[dict[bytes, int], int, int]:
        table = {bytes([idx]): idx for idx in range(clear_code)}
        return table, end_code + 1, min_code_size + 1

    table, next_code, code_size = reset_table()
    output_codes: list[tuple[int, int]] = [(clear_code, code_size)]
    if indices:
        word = bytes([indices[0]])
        for value in indices[1:]:
            candidate = word + bytes([value])
            if candidate in table:
                word = candidate
                continue
            output_codes.append((table[word], code_size))
            if next_code < 4096:
                table[candidate] = next_code
                next_code += 1
                if next_code == (1 << code_size) and code_size < 12:
                    code_size += 1
            else:
                output_codes.append((clear_code, code_size))
                table, next_code, code_size = reset_table()
            word = bytes([value])
        output_codes.append((table[word], code_size))
    output_codes.append((end_code, code_size))

    packed = bytearray()
    bit_buffer = 0
    bit_count = 0
    for code, size in output_codes:
        bit_buffer |= code << bit_count
        bit_count += size
        while bit_count >= 8:
            packed.append(bit_buffer & 0xFF)
            bit_buffer >>= 8
            bit_count -= 8
    if bit_count:
        packed.append(bit_buffer & 0xFF)
    return bytes(packed)
