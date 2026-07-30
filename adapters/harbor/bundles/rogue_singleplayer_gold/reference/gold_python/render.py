"""Minimal Rogue render helpers."""

from __future__ import annotations

from engine import RogueEngine


PNG_1X1 = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6360000002000154a24f5d0000000049454e44ae426082")


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
    return PNG_1X1
