"""Procedural sprite renderer for GameBench DungeonGrid states.

Adapted from the source DungeonGrid procedural pixel-grid style. This version is
dependency-free and renders directly to RGB rows for local GIF/PNG generation.
"""

from __future__ import annotations

from typing import Any

RGB = tuple[int, int, int]
RGBRows = list[list[RGB]]
RGBFrame = tuple[int, int, RGBRows]

TILE = 48
PAD = 18
HUD_W = 220
MSG_H = 42
SPRITE = 16

BG = (15, 12, 10)
PANEL = (32, 26, 23)
TEXT = (239, 226, 199)
MUTED = (157, 138, 112)
OUTLINE = (20, 17, 15)
VOID = (7, 7, 8)
STONE = (82, 82, 76)
STONE_LIGHT = (124, 120, 108)
WOOD_DARK = (72, 43, 24)
WOOD = (128, 76, 35)
WOOD_LIGHT = (178, 112, 48)
BONE = (218, 210, 184)
GOLD = (226, 174, 62)
RED = (177, 54, 49)
GREEN = (84, 145, 64)
BLUE = (57, 93, 154)
TORCH = (239, 119, 36)
BURGUNDY = (101, 40, 48)


def render_rgb_frame(state: dict[str, Any], *, tile_size: int = TILE) -> RGBFrame:
    rows_ascii = state["map"]["ascii"].splitlines()
    map_w = int(state["map"]["width"])
    map_h = int(state["map"]["height"])
    tile = max(32, int(tile_size))
    board_w = map_w * tile
    board_h = map_h * tile
    width = PAD * 3 + board_w + HUD_W
    height = PAD * 3 + MSG_H + board_h
    canvas: RGBRows = [[BG for _ in range(width)] for _ in range(height)]

    _rounded_rect(canvas, PAD, PAD, width - PAD, PAD + MSG_H, PANEL, (74, 60, 46), 8)
    _text_blocks(canvas, PAD + 12, PAD + 10, _message(state), TEXT)
    _small_blocks(canvas, PAD + 12, PAD + 27, _subtitle(state), MUTED)

    board_x = PAD
    board_y = PAD * 2 + MSG_H
    _rounded_rect(canvas, board_x - 6, board_y - 6, board_x + board_w + 6, board_y + board_h + 6, (19, 16, 14), (91, 72, 49), 10)
    _draw_tiles(canvas, rows_ascii, board_x, board_y, tile)
    _draw_statics(canvas, state, board_x, board_y, tile)
    _draw_entities(canvas, state, board_x, board_y, tile)
    _draw_hud(canvas, state, board_x + board_w + PAD, board_y, HUD_W, board_h)
    return width, height, canvas


def _draw_tiles(canvas: RGBRows, rows_ascii: list[str], x0: int, y0: int, tile: int) -> None:
    for y, row in enumerate(rows_ascii):
        for x, char in enumerate(row):
            box = _tile_box(x0, y0, x, y, tile)
            if char == "#":
                _paint_scaled(canvas, box, _sprite_wall())
            elif char == " ":
                _rect(canvas, *box, VOID)
            else:
                _paint_scaled(canvas, box, _sprite_floor((x + y) % 2 == 0))


def _draw_statics(canvas: RGBRows, state: dict[str, Any], x0: int, y0: int, tile: int) -> None:
    for door in state.get("doors", {}).values():
        _draw_sprite_at(canvas, door["pos"], x0, y0, tile, _sprite_marker("open_door" if door.get("open") else "door"))
    for trap in state.get("traps", {}).values():
        if trap.get("revealed") or trap.get("armed"):
            _draw_sprite_at(canvas, trap["pos"], x0, y0, tile, _sprite_marker("trap"))
    for chest in state.get("chests", {}).values():
        if not chest.get("opened"):
            _draw_sprite_at(canvas, chest["pos"], x0, y0, tile, _sprite_marker("chest"))
    objective = state.get("objective") or {}
    if objective.get("pos") and not objective.get("carrier"):
        _draw_sprite_at(canvas, objective["pos"], x0, y0, tile, _sprite_marker("objective"))
    escape = objective.get("escape_tile")
    if escape:
        _draw_sprite_at(canvas, escape, x0, y0, tile, _sprite_marker("exit"))


def _draw_entities(canvas: RGBRows, state: dict[str, Any], x0: int, y0: int, tile: int) -> None:
    for monster in state.get("monsters", {}).values():
        if int(monster.get("hp", 0)) <= 0:
            continue
        _draw_sprite_at(canvas, monster["pos"], x0, y0, tile, _sprite_monster(monster.get("role", "")))
        x, y = _pos(monster["pos"])
        bx1, by1, bx2, _ = _tile_box(x0, y0, x, y, tile)
        _hp_bar(canvas, bx1 + 6, by1 + 4, bx2 - 6, by1 + 7, monster.get("hp", 1), monster.get("max_hp", monster.get("hp", 1)))
    active = state.get("active_agent")
    for agent_id, hero in state.get("heroes", {}).items():
        x, y = _pos(hero["pos"])
        box = _tile_box(x0, y0, x, y, tile)
        if agent_id == active:
            _outline(canvas, box, (255, 221, 116), 2)
        _paint_scaled(canvas, box, _sprite_hero(hero.get("role", "")))
        _hp_bar(canvas, box[0] + 6, box[1] + 4, box[2] - 6, box[1] + 7, hero.get("hp", 1), hero.get("max_hp", 1))


def _draw_hud(canvas: RGBRows, state: dict[str, Any], x: int, y: int, w: int, h: int) -> None:
    _rounded_rect(canvas, x, y, x + w, y + h, PANEL, (74, 60, 46), 10)
    _text_blocks(canvas, x + 12, y + 12, "DungeonGrid", TEXT)
    yy = y + 34
    lines = [
        f"active {state.get('active_agent', '-')}",
        f"reward {state.get('total_reward', 0):.2f}",
        f"step {state.get('step_index', 0)}",
        f"turn {state.get('turn_index', 0)}",
    ]
    for line in lines:
        _small_blocks(canvas, x + 12, yy, line, MUTED)
        yy += 18
    yy += 6
    _small_blocks(canvas, x + 12, yy, "party", GOLD)
    yy += 18
    for agent_id, hero in state.get("heroes", {}).items():
        _small_blocks(canvas, x + 18, yy, f"{agent_id} {hero.get('role')}", TEXT)
        yy += 15
        _small_blocks(canvas, x + 28, yy, f"hp {hero.get('hp')}/{hero.get('max_hp')}", MUTED)
        yy += 17
    achievements = state.get("achievements") or []
    if achievements:
        yy += 6
        _small_blocks(canvas, x + 12, yy, "achievements", GOLD)
        yy += 18
        for item in achievements[-4:]:
            _small_blocks(canvas, x + 18, yy, str(item).split(".")[-1][:18], TEXT)
            yy += 15


def _sprite_floor(alt: bool) -> RGBRows:
    base = (70, 70, 66) if alt else (64, 64, 61)
    s = _blank(base)
    _rect(s, 0, 15, 15, 15, (31, 31, 30))
    _rect(s, 15, 0, 15, 15, (31, 31, 30))
    _rect(s, 0, 0, 15, 0, (102, 98, 88))
    s[4][3] = (95, 92, 84)
    s[10][11] = (45, 44, 43)
    if alt:
        _line(s, 5, 2, 7, 4, (43, 42, 41))
    return s


def _sprite_wall() -> RGBRows:
    s = _blank(STONE)
    _rect(s, 0, 0, 15, 15, STONE)
    _rect(s, 1, 1, 7, 4, STONE_LIGHT)
    _rect(s, 8, 1, 14, 4, (103, 101, 93))
    _rect(s, 1, 5, 4, 9, (70, 70, 66))
    _rect(s, 5, 5, 11, 9, (99, 97, 90))
    _rect(s, 12, 5, 14, 9, (63, 63, 60))
    _rect(s, 1, 10, 7, 14, (56, 56, 54))
    _rect(s, 8, 10, 14, 14, (73, 72, 68))
    _rect(s, 0, 0, 15, 0, (151, 137, 103))
    _rect(s, 0, 15, 15, 15, (30, 28, 26))
    return s


def _sprite_marker(kind: str) -> RGBRows:
    s = _blank((0, 0, 0), alpha=True)
    if kind == "door":
        _rect(s, 5, 2, 11, 14, WOOD_DARK)
        _rect(s, 6, 3, 10, 13, WOOD)
        _line(s, 7, 3, 7, 13, WOOD_LIGHT)
        s[8][10] = GOLD
    elif kind == "open_door":
        _rect(s, 4, 2, 7, 14, WOOD_DARK)
        _poly(s, [(8, 3), (13, 5), (13, 13), (8, 14)], (42, 33, 27))
    elif kind == "chest":
        _rect(s, 3, 7, 13, 13, WOOD)
        _rect(s, 4, 4, 12, 8, WOOD_LIGHT)
        _rect(s, 3, 8, 13, 8, GOLD)
        _rect(s, 7, 8, 8, 11, GOLD)
    elif kind == "trap":
        _rect(s, 3, 4, 12, 12, (29, 28, 27))
        for x in (5, 8, 11):
            _poly(s, [(x, 6), (x - 1, 11), (x + 1, 11)], BONE)
    elif kind == "objective":
        _poly(s, [(8, 2), (13, 7), (8, 14), (3, 7)], GOLD)
        _rect(s, 7, 6, 9, 9, BURGUNDY)
    elif kind == "exit":
        _rect(s, 2, 2, 14, 14, (20, 30, 34))
        _poly(s, [(8, 3), (13, 8), (8, 13), (3, 8)], (30, 73, 88))
    return s


def _sprite_hero(role: str) -> RGBRows:
    s = _blank((0, 0, 0), alpha=True)
    if role == "wizard":
        _line(s, 12, 3, 12, 14, WOOD_LIGHT)
        _poly(s, [(8, 1), (4, 6), (12, 6)], BLUE)
        _rect(s, 5, 6, 11, 13, BLUE)
        _rect(s, 6, 6, 10, 8, (219, 178, 132))
        _rect(s, 6, 8, 10, 11, BONE)
        _line(s, 8, 9, 8, 13, GOLD)
    elif role == "barbarian":
        _line(s, 3, 4, 3, 13, BONE)
        _rect(s, 2, 3, 4, 4, BONE)
        _rect(s, 6, 5, 10, 12, (164, 164, 156))
        _rect(s, 6, 3, 10, 6, (199, 199, 188))
        _rect(s, 10, 7, 13, 12, BLUE)
    else:
        _rect(s, 5, 6, 11, 13, (88, 108, 132))
        _rect(s, 6, 3, 10, 7, (206, 154, 107))
    return s


def _sprite_monster(role: str) -> RGBRows:
    s = _blank((0, 0, 0), alpha=True)
    if role == "crypt_brute":
        _rect(s, 4, 6, 12, 13, (82, 124, 56))
        _rect(s, 5, 3, 11, 8, GREEN)
        _rect(s, 4, 8, 6, 10, STONE_LIGHT)
        _rect(s, 10, 8, 12, 10, STONE_LIGHT)
        _line(s, 13, 5, 14, 13, STONE_LIGHT)
        s[5][6] = OUTLINE
        s[5][10] = OUTLINE
    else:
        _rect(s, 4, 7, 12, 13, GREEN)
        _rect(s, 5, 4, 11, 9, (102, 159, 67))
        _poly(s, [(5, 5), (2, 6), (5, 7)], GREEN)
        _poly(s, [(11, 5), (14, 6), (11, 7)], GREEN)
        _line(s, 12, 6, 14, 13, BONE)
    return s


def _draw_sprite_at(canvas: RGBRows, pos: Any, x0: int, y0: int, tile: int, sprite: RGBRows) -> None:
    x, y = _pos(pos)
    _paint_scaled(canvas, _tile_box(x0, y0, x, y, tile), sprite)


def _paint_scaled(canvas: RGBRows, box: tuple[int, int, int, int], sprite: RGBRows) -> None:
    x1, y1, x2, y2 = box
    w = x2 - x1 + 1
    h = y2 - y1 + 1
    for yy in range(h):
        sy = min(SPRITE - 1, yy * SPRITE // h)
        for xx in range(w):
            sx = min(SPRITE - 1, xx * SPRITE // w)
            rgb = sprite[sy][sx]
            if rgb != (-1, -1, -1):
                _set(canvas, x1 + xx, y1 + yy, rgb)


def _blank(rgb: RGB, *, alpha: bool = False) -> RGBRows:
    fill = (-1, -1, -1) if alpha else rgb
    return [[fill for _ in range(SPRITE)] for _ in range(SPRITE)]


def _hp_bar(canvas: RGBRows, x1: int, y1: int, x2: int, y2: int, hp: Any, max_hp: Any) -> None:
    try:
        hp_f = max(0.0, float(hp))
        max_f = max(1.0, float(max_hp))
    except (TypeError, ValueError):
        hp_f, max_f = 1.0, 1.0
    _rect(canvas, x1, y1, x2, y2, (30, 20, 18))
    fill_x = x1 + int((x2 - x1) * min(1.0, hp_f / max_f))
    _rect(canvas, x1, y1, fill_x, y2, RED if hp_f / max_f < 0.4 else (88, 158, 76))


def _message(state: dict[str, Any]) -> str:
    tail = state.get("event_log_tail") or []
    if tail:
        event = tail[-1]
        if isinstance(event, dict):
            return str(event.get("summary") or event.get("kind") or event)[:42]
        return str(event)[:42]
    return str(state.get("title") or "DungeonGrid")


def _subtitle(state: dict[str, Any]) -> str:
    return f"turn {state.get('turn_index', 0)}  active {state.get('active_agent', '-')}"


def _pos(pos: Any) -> tuple[int, int]:
    if isinstance(pos, dict):
        return int(pos["x"]), int(pos["y"])
    return int(pos[0]), int(pos[1])


def _tile_box(x0: int, y0: int, x: int, y: int, tile: int) -> tuple[int, int, int, int]:
    return x0 + x * tile, y0 + y * tile, x0 + (x + 1) * tile - 1, y0 + (y + 1) * tile - 1


def _rounded_rect(canvas: RGBRows, x1: int, y1: int, x2: int, y2: int, fill: RGB, outline: RGB, radius: int) -> None:
    _rect(canvas, x1 + radius, y1, x2 - radius, y2, fill)
    _rect(canvas, x1, y1 + radius, x2, y2 - radius, fill)
    _rect(canvas, x1 + radius, y1 + radius, x2 - radius, y2 - radius, fill)
    _outline(canvas, (x1, y1, x2, y2), outline, 1)


def _outline(canvas: RGBRows, box: tuple[int, int, int, int], color: RGB, width: int) -> None:
    x1, y1, x2, y2 = box
    for i in range(width):
        _rect(canvas, x1 + i, y1 + i, x2 - i, y1 + i, color)
        _rect(canvas, x1 + i, y2 - i, x2 - i, y2 - i, color)
        _rect(canvas, x1 + i, y1 + i, x1 + i, y2 - i, color)
        _rect(canvas, x2 - i, y1 + i, x2 - i, y2 - i, color)


def _rect(canvas: RGBRows, x1: int, y1: int, x2: int, y2: int, color: RGB) -> None:
    for y in range(max(0, y1), min(len(canvas), y2 + 1)):
        row = canvas[y]
        for x in range(max(0, x1), min(len(row), x2 + 1)):
            row[x] = color


def _line(canvas: RGBRows, x1: int, y1: int, x2: int, y2: int, color: RGB) -> None:
    dx = abs(x2 - x1)
    dy = -abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx + dy
    x, y = x1, y1
    while True:
        _set(canvas, x, y, color)
        if x == x2 and y == y2:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def _poly(canvas: RGBRows, points: list[tuple[int, int]], color: RGB) -> None:
    min_y = min(y for _, y in points)
    max_y = max(y for _, y in points)
    for y in range(min_y, max_y + 1):
        nodes: list[int] = []
        j = len(points) - 1
        for i, (xi, yi) in enumerate(points):
            xj, yj = points[j]
            if (yi < y <= yj) or (yj < y <= yi):
                nodes.append(int(xi + (y - yi) / (yj - yi) * (xj - xi)))
            j = i
        nodes.sort()
        for a, b in zip(nodes[0::2], nodes[1::2]):
            _rect(canvas, a, y, b, y, color)


def _set(canvas: RGBRows, x: int, y: int, color: RGB) -> None:
    if 0 <= y < len(canvas) and 0 <= x < len(canvas[y]):
        canvas[y][x] = color


def _text_blocks(canvas: RGBRows, x: int, y: int, text: str, color: RGB) -> None:
    for idx, char in enumerate(text[:42]):
        _glyph(canvas, x + idx * 7, y, char, color, scale=1)


def _small_blocks(canvas: RGBRows, x: int, y: int, text: str, color: RGB) -> None:
    for idx, char in enumerate(text[:28]):
        _glyph(canvas, x + idx * 5, y, char, color, scale=1, small=True)


_FONT = {
    "a": ("010", "101", "111", "101", "101"),
    "b": ("110", "101", "110", "101", "110"),
    "c": ("011", "100", "100", "100", "011"),
    "d": ("110", "101", "101", "101", "110"),
    "e": ("111", "100", "110", "100", "111"),
    "f": ("111", "100", "110", "100", "100"),
    "g": ("011", "100", "101", "101", "011"),
    "h": ("101", "101", "111", "101", "101"),
    "i": ("111", "010", "010", "010", "111"),
    "j": ("001", "001", "001", "101", "010"),
    "k": ("101", "101", "110", "101", "101"),
    "l": ("100", "100", "100", "100", "111"),
    "m": ("101", "111", "111", "101", "101"),
    "n": ("101", "111", "111", "111", "101"),
    "o": ("111", "101", "101", "101", "111"),
    "p": ("110", "101", "110", "100", "100"),
    "q": ("111", "101", "101", "111", "001"),
    "r": ("110", "101", "110", "101", "101"),
    "s": ("011", "100", "010", "001", "110"),
    "t": ("111", "010", "010", "010", "010"),
    "u": ("101", "101", "101", "101", "111"),
    "v": ("101", "101", "101", "101", "010"),
    "w": ("101", "101", "111", "111", "101"),
    "x": ("101", "101", "010", "101", "101"),
    "y": ("101", "101", "010", "010", "010"),
    "z": ("111", "001", "010", "100", "111"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "-": ("000", "000", "111", "000", "000"),
    ".": ("000", "000", "000", "000", "010"),
    ":": ("000", "010", "000", "010", "000"),
}


def _glyph(canvas: RGBRows, x: int, y: int, char: str, color: RGB, *, scale: int, small: bool = False) -> None:
    ch = char.lower()
    pattern = _FONT.get(ch)
    if pattern is None:
        if ch == " ":
            return
        # Compact pseudo-letter: stable and readable enough for labels at GIF size.
        bits = ord(ch)
        pattern = tuple(format(((bits >> row) ^ (bits * 7 + row)) & 0b111, "03b") for row in range(5))
    px = 1 if small else scale
    for yy, row in enumerate(pattern):
        for xx, bit in enumerate(row):
            if bit == "1":
                _rect(canvas, x + xx * px, y + yy * px, x + xx * px + px - 1, y + yy * px + px - 1, color)
