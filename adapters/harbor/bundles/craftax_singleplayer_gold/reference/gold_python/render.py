"""Small SVG/PNG projections for symbolic Craftax states."""

from __future__ import annotations

from typing import Any

from engine import CraftaxEngine


COLORS = {
    ".": "#6aaa54",
    ",": "#9a8f73",
    "~": "#3b82c4",
    "S": "#777777",
    "T": "#236b2e",
    "C": "#333333",
    "I": "#a67c52",
    "D": "#5ec4ff",
    "s": "#4777d9",
    "r": "#d94f4f",
    "H": "#8b5a2b",
    "A": "#a16207",
    "F": "#525252",
    "p": "#4ade80",
    "P": "#facc15",
    ">": "#f97316",
    "<": "#f97316",
    "#": "#27272a",
    "%": "#3f3f46",
    "^": "#a8a29e",
    "L": "#ef4444",
    "O": "#38bdf8",
    "Y": "#fb923c",
    "y": "#bae6fd",
    "E": "#f97316",
    "e": "#60a5fa",
    "N": "#a855f7",
    "n": "#c084fc",
    "+": "#71717a",
    " ": "#020617",
    "!": "#fde047",
    "P_PLAYER": "#ffffff",
}


def render_svg(engine: CraftaxEngine, tile_size: int = 18) -> str:
    readout = engine.symbolic_readout()
    rows = readout["ascii"].splitlines()
    width = len(rows[0]) * tile_size if rows else tile_size
    height = len(rows) * tile_size if rows else tile_size
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#111827"/>',
    ]
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            color_key = "P_PLAYER" if char == "P" else char
            color = COLORS.get(color_key, "#d1d5db")
            parts.append(f'<rect x="{x * tile_size}" y="{y * tile_size}" width="{tile_size}" height="{tile_size}" fill="{color}"/>')
            if char not in ".,":
                parts.append(
                    f'<text x="{x * tile_size + tile_size / 2}" y="{y * tile_size + tile_size * 0.68}" '
                    f'font-size="{max(8, int(tile_size * 0.65))}" text-anchor="middle" fill="#111827">{char}</text>'
                )
    parts.append("</svg>")
    return "".join(parts)


def render_png_bytes(engine: CraftaxEngine) -> bytes:
    # The lightweight task keeps PNG optional; callers can use SVG everywhere.
    # Returning SVG bytes here preserves the route without adding image deps.
    return render_svg(engine).encode("utf-8")


def render_state(engine: CraftaxEngine) -> dict[str, Any]:
    readout = engine.symbolic_readout()
    return {"profile": "ascii_tui", "ascii": readout["ascii"], "grid_hash": readout["grid_hash"]}
