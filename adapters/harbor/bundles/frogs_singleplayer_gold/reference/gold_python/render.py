"""Minimal FrogsGame render helpers."""

from __future__ import annotations

from engine import FrogsEngine


PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def render_svg(engine: FrogsEngine) -> str:
    readout = engine.symbolic_readout()
    board = readout["public"]["board"]
    frogs = {tuple(cell) for cell in readout["public"]["frogs"]}
    cell = 48
    palette = {
        "blue": "#7fb3ff",
        "red": "#ff8f8f",
        "green": "#8fd19e",
        "yellow": "#f2d16b",
    }
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{len(board) * cell}" height="{len(board) * cell}" viewBox="0 0 {len(board) * cell} {len(board) * cell}">']
    for row_index, row in enumerate(board):
        for col_index, color in enumerate(row):
            x = col_index * cell
            y = row_index * cell
            fill = palette.get(color, "#dddddd")
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}" stroke="#222" stroke-width="1"/>')
            if (row_index, col_index) in frogs:
                parts.append(f'<circle cx="{x + cell / 2}" cy="{y + cell / 2}" r="14" fill="#1f2933"/>')
    parts.append("</svg>")
    return "".join(parts)


def render_png_bytes(engine: FrogsEngine) -> bytes:
    return PNG_1X1
