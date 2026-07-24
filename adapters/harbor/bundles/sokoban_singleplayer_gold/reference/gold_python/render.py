"""Render helpers for Sokoban v0."""

from __future__ import annotations

import struct
import zlib

from observations import ascii_board


COLORS = {
    "#": (45, 48, 54),
    " ": (238, 238, 232),
    ".": (246, 214, 92),
    "$": (171, 111, 62),
    "*": (80, 170, 105),
    "@": (80, 140, 220),
    "+": (80, 170, 220),
}


def render_ascii(engine: object) -> str:
    return ascii_board(engine.room_fixed, engine.player, engine.boxes)


def render_svg(engine: object, *, tile_size: int = 32) -> str:
    rows = render_ascii(engine).splitlines()
    width = max(len(row) for row in rows) if rows else 0
    height = len(rows)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width * tile_size}" height="{height * tile_size}" viewBox="0 0 {width * tile_size} {height * tile_size}">'
    ]
    for r, row in enumerate(rows):
        for c, ch in enumerate(row.ljust(width)):
            color = COLORS.get(ch, COLORS[" "])
            parts.append(
                f'<rect x="{c * tile_size}" y="{r * tile_size}" width="{tile_size}" height="{tile_size}" fill="rgb({color[0]},{color[1]},{color[2]})"/>'
            )
            if ch in "$*@+":
                label = "P" if ch in "@+" else "B"
                parts.append(
                    f'<text x="{c * tile_size + tile_size / 2}" y="{r * tile_size + tile_size * 0.66}" text-anchor="middle" font-size="{tile_size * 0.5}" font-family="monospace" fill="white">{label}</text>'
                )
    parts.append("</svg>")
    return "".join(parts)


def render_png_bytes(engine: object, *, tile_size: int = 24) -> bytes:
    rows = render_ascii(engine).splitlines()
    width_tiles = max(len(row) for row in rows) if rows else 1
    height_tiles = max(len(rows), 1)
    width = width_tiles * tile_size
    height = height_tiles * tile_size
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        tile_r = y // tile_size
        row = rows[tile_r].ljust(width_tiles) if tile_r < len(rows) else " " * width_tiles
        for x in range(width):
            ch = row[x // tile_size]
            raw.extend(COLORS.get(ch, COLORS[" "]))
    return _png(width, height, bytes(raw))


def _png(width: int, height: int, raw_scanlines: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    return b"\x89PNG\r\n\x1a\n" + chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
    ) + chunk(b"IDAT", zlib.compress(raw_scanlines)) + chunk(b"IEND", b"")
