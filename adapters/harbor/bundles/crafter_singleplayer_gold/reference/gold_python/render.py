"""Small symbolic render helpers for Crafter."""

from __future__ import annotations

import struct
import zlib
from typing import Any


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


def render_rgb_frame(engine: Any, *, tile_size: int = 8) -> RGBFrame:
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


def render_png_bytes(engine: Any, *, tile_size: int = 8) -> bytes:
    """Render the local symbolic view as a tiny RGB PNG without external deps."""

    width, height, pixel_rows = render_rgb_frame(engine, tile_size=tile_size)
    return encode_png_rgb(width, height, pixel_rows)


def encode_png_rgb(width: int, height: int, rows: RGBRows) -> bytes:
    return _encode_png_rgb(width, height, rows)


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
