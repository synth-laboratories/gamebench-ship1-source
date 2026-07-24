"""Procedural tile renderer for Rogue visual artifacts."""

from __future__ import annotations

import struct
import zlib

from engine import RogueEngine


RGB = tuple[int, int, int]
RGBRows = list[list[RGB]]
RGBFrame = tuple[int, int, RGBRows]


def render_svg(engine: RogueEngine) -> str:
    ascii_map = engine.symbolic_readout()["ascii"].splitlines()
    cell_w = 10
    cell_h = 16
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{max(len(row) for row in ascii_map) * cell_w}" height="{len(ascii_map) * cell_h}" viewBox="0 0 {max(len(row) for row in ascii_map) * cell_w} {len(ascii_map) * cell_h}">', '<rect width="100%" height="100%" fill="#111"/>']
    for row_index, row in enumerate(ascii_map):
        for col_index, char in enumerate(row):
            if char != " ":
                color = "#e5e7eb" if char in ".@|-%" else "#f6d365"
                parts.append(f'<text x="{col_index * cell_w}" y="{(row_index + 1) * cell_h - 3}" fill="{color}" font-family="monospace" font-size="14">{char}</text>')
    parts.append("</svg>")
    return "".join(parts)


def render_png_bytes(engine: RogueEngine) -> bytes:
    width, height, rows = render_rgb_frame(engine)
    return encode_png_rgb(width, height, rows)


def render_rgb_frame(engine: RogueEngine, *, tile_size: int = 24, pad: int = 10) -> RGBFrame:
    ascii_text = engine.symbolic_readout()["ascii"]
    lines = ascii_text.splitlines()
    width_chars = max(len(line) for line in lines)
    cell = max(16, int(tile_size))
    width = width_chars * cell + pad * 2
    height = len(lines) * cell + pad * 2
    rows: RGBRows = [[(9, 11, 15) for _ in range(width)] for _ in range(height)]
    for y, line in enumerate(lines):
        for x, char in enumerate(line.ljust(width_chars)):
            _tile(rows, pad + x * cell, pad + y * cell, cell, char, alt=(x + y) % 2 == 0)
    return width, height, rows


def encode_png_rgb(width: int, height: int, rows: RGBRows) -> bytes:
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


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _tile(rows: RGBRows, x0: int, y0: int, cell: int, char: str, *, alt: bool) -> None:
    if char == " ":
        _rect(rows, x0, y0, cell, cell, (8, 10, 14))
        return
    if char in "|-":
        _rect(rows, x0, y0, cell, cell, (77, 82, 91))
        _rect(rows, x0 + 2, y0 + 2, cell - 4, cell - 4, (112, 118, 128))
        _rect(rows, x0 + 4, y0 + 4, cell - 8, cell - 8, (83, 89, 97))
        return

    _rect(rows, x0, y0, cell, cell, (34, 39, 48) if alt else (29, 34, 42))
    _rect(rows, x0, y0 + cell - 2, cell, 2, (15, 18, 24))
    _rect(rows, x0 + cell - 2, y0, 2, cell, (15, 18, 24))

    if char == "@":
        _rect(rows, x0 + 7, y0 + 5, 10, 14, (236, 197, 94))
        _rect(rows, x0 + 9, y0 + 3, 6, 5, (248, 250, 252))
        _rect(rows, x0 + 6, y0 + 12, 12, 4, (78, 121, 167))
    elif char == ">":
        for i in range(5):
            _rect(rows, x0 + 6 + i * 2, y0 + 6 + i * 2, 12 - i * 2, 2, (244, 127, 44))
    elif char == "*":
        _rect(rows, x0 + 8, y0 + 7, 9, 9, (248, 220, 92))
        _rect(rows, x0 + 10, y0 + 5, 5, 13, (250, 204, 21))
    elif char == "%":
        _rect(rows, x0 + 7, y0 + 9, 11, 7, (86, 171, 99))
        _rect(rows, x0 + 9, y0 + 6, 7, 5, (132, 204, 140))
    elif char == "^":
        _rect(rows, x0 + 6, y0 + 6, 12, 12, (80, 24, 24))
        for dx in (8, 12, 16):
            _rect(rows, x0 + dx, y0 + 8, 2, 8, (239, 197, 148))
    elif char == "+":
        _rect(rows, x0 + 8, y0 + 4, 8, 16, (128, 76, 35))
        _rect(rows, x0 + 10, y0 + 6, 4, 12, (178, 112, 48))
    elif char not in ".":
        _rect(rows, x0 + 6, y0 + 6, 12, 12, (175, 98, 201))
        _rect(rows, x0 + 8, y0 + 4, 8, 6, (210, 142, 232))


def _rect(rows: RGBRows, x0: int, y0: int, width: int, height: int, rgb: RGB) -> None:
    for y in range(y0, min(y0 + height, len(rows))):
        row = rows[y]
        for x in range(x0, min(x0 + width, len(row))):
            row[x] = rgb
