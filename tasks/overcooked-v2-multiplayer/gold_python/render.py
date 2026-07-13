"""Pixel rendering for Overcooked v2 symbolic gold."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from engine import OvercookedV2Engine


TILE_SIZE = 8
COLORS: dict[str, tuple[int, int, int]] = {
    "floor": (40, 40, 48),
    "wall": (24, 24, 32),
    "onion": (180, 120, 40),
    "tomato": (200, 60, 60),
    "pepper": (80, 180, 80),
    "pot": (120, 80, 80),
    "dish": (200, 200, 220),
    "serve": (80, 160, 220),
    "counter": (100, 100, 110),
    "indicator": (220, 180, 60),
    "button": (220, 120, 180),
    "agent_0": (60, 180, 255),
    "agent_1": (255, 120, 60),
    "agent_2": (120, 255, 120),
    "agent_3": (200, 120, 255),
}


def _ingredient_color(index: int) -> tuple[int, int, int]:
    if index == 0:
        return COLORS["onion"]
    if index == 1:
        return COLORS["tomato"]
    if index == 2:
        return COLORS["pepper"]
    return (160, 160, 160)


def render_pixel_rgb(engine: "OvercookedV2Engine") -> list[list[list[int]]]:
    assert engine.resolved is not None
    layout = engine.resolved.layout
    height = layout.height * TILE_SIZE
    width = layout.width * TILE_SIZE
    image = [[list(COLORS["floor"]) for _ in range(width)] for _ in range(height)]

    def paint_tile(row: int, col: int, color: tuple[int, int, int]) -> None:
        for dr in range(TILE_SIZE):
            for dc in range(TILE_SIZE):
                image[row * TILE_SIZE + dr][col * TILE_SIZE + dc] = list(color)

    for row in range(layout.height):
        for col in range(layout.width):
            pos = (row, col)
            if pos in engine.layout_walls:
                paint_tile(row, col, COLORS["wall"])
            else:
                paint_tile(row, col, COLORS["floor"])

    for pos in engine.pots:
        paint_tile(pos[0], pos[1], COLORS["pot"])
    for pos in engine.dish_dispensers:
        paint_tile(pos[0], pos[1], COLORS["dish"])
    for pos in engine.serve_tiles:
        paint_tile(pos[0], pos[1], COLORS["serve"])
    for pos in engine.counters:
        paint_tile(pos[0], pos[1], COLORS["counter"])
    for pos in engine.recipe_indicators:
        paint_tile(pos[0], pos[1], COLORS["indicator"])
    for pos in engine.button_recipe_indicators:
        ticks = engine.button_activation_ticks.get(f"{pos[0]},{pos[1]}", 0)
        color = COLORS["button"] if ticks > 0 else (140, 90, 120)
        paint_tile(pos[0], pos[1], color)
    for pile_pos, ing_index in engine.ingredient_pile_map.items():
        paint_tile(pile_pos[0], pile_pos[1], _ingredient_color(ing_index))

    for agent_id, agent in engine.agents.items():
        color = COLORS.get(agent_id, (200, 200, 200))
        row, col = agent.position
        for dr in range(2, TILE_SIZE - 2):
            for dc in range(2, TILE_SIZE - 2):
                image[row * TILE_SIZE + dr][col * TILE_SIZE + dc] = list(color)

    return image
