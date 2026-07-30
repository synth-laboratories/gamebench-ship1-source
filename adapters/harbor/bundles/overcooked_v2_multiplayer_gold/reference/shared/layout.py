"""ASCII layout parsing for Overcooked v2 symbolic gold."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


AGENT_CHAR = {str(index): f"agent_{index}" for index in range(4)}


@dataclass(frozen=True)
class ParsedLayout:
    layout_id: str
    width: int
    height: int
    walls: frozenset[tuple[int, int]]
    ingredient_piles: frozenset[tuple[tuple[int, int], int]]
    dish_dispensers: frozenset[tuple[int, int]]
    pots: frozenset[tuple[int, int]]
    serve_tiles: frozenset[tuple[int, int]]
    counters: frozenset[tuple[int, int]]
    recipe_indicators: frozenset[tuple[int, int]]
    button_recipe_indicators: frozenset[tuple[int, int]]
    agent_starts: dict[str, tuple[int, int]]
    num_ingredients: int

    @property
    def onion_dispensers(self) -> frozenset[tuple[int, int]]:
        return frozenset(pos for pos, index in self.ingredient_piles if index == 0)

    def ingredient_index_at(self, pos: tuple[int, int]) -> int | None:
        for pile_pos, index in self.ingredient_piles:
            if pile_pos == pos:
                return index
        return None


def parse_ascii_rows(layout_id: str, rows: list[str]) -> ParsedLayout:
    walls: set[tuple[int, int]] = set()
    ingredient_piles: set[tuple[tuple[int, int], int]] = set()
    dish_dispensers: set[tuple[int, int]] = set()
    pots: set[tuple[int, int]] = set()
    serve_tiles: set[tuple[int, int]] = set()
    counters: set[tuple[int, int]] = set()
    recipe_indicators: set[tuple[int, int]] = set()
    button_recipe_indicators: set[tuple[int, int]] = set()
    agent_starts: dict[str, tuple[int, int]] = {}
    max_ingredient_index = -1
    height = len(rows)
    width = max(len(row) for row in rows) if rows else 0
    for row_index, row in enumerate(rows):
        for col_index, char in enumerate(row):
            pos = (row_index, col_index)
            if char in {"#", "W"}:
                walls.add(pos)
            elif char == "O":
                ingredient_piles.add((pos, 0))
                max_ingredient_index = max(max_ingredient_index, 0)
            elif char == "T":
                ingredient_piles.add((pos, 1))
                max_ingredient_index = max(max_ingredient_index, 1)
            elif char in AGENT_CHAR:
                agent_starts[AGENT_CHAR[char]] = pos
            elif char.isdigit():
                index = int(char)
                ingredient_piles.add((pos, index))
                max_ingredient_index = max(max_ingredient_index, index)
            elif char in {"D", "B"}:
                dish_dispensers.add(pos)
            elif char in {"P"}:
                pots.add(pos)
            elif char in {"S", "X"}:
                serve_tiles.add(pos)
            elif char == "C":
                counters.add(pos)
            elif char == "R":
                recipe_indicators.add(pos)
            elif char == "L":
                button_recipe_indicators.add(pos)
            elif char == "A":
                if "agent_0" not in agent_starts:
                    agent_starts["agent_0"] = pos
                elif "agent_1" not in agent_starts:
                    agent_starts["agent_1"] = pos
                elif "agent_2" not in agent_starts:
                    agent_starts["agent_2"] = pos
                else:
                    agent_starts["agent_3"] = pos
    num_ingredients = max(max_ingredient_index + 1, 1)
    return ParsedLayout(
        layout_id=layout_id,
        width=width,
        height=height,
        walls=frozenset(walls),
        ingredient_piles=frozenset(ingredient_piles),
        dish_dispensers=frozenset(dish_dispensers),
        pots=frozenset(pots),
        serve_tiles=frozenset(serve_tiles),
        counters=frozenset(counters),
        recipe_indicators=frozenset(recipe_indicators),
        button_recipe_indicators=frozenset(button_recipe_indicators),
        agent_starts=agent_starts,
        num_ingredients=num_ingredients,
    )


def walkable_tiles(layout: ParsedLayout) -> list[tuple[int, int]]:
    blocked = (
        layout.walls
        | layout.dish_dispensers
        | layout.pots
        | layout.serve_tiles
        | layout.recipe_indicators
        | layout.button_recipe_indicators
        | {pos for pos, _ in layout.ingredient_piles}
    )
    tiles: list[tuple[int, int]] = []
    for row_index in range(layout.height):
        for col_index in range(layout.width):
            pos = (row_index, col_index)
            if pos not in blocked:
                tiles.append(pos)
    return tiles


def load_layout(layout: dict[str, Any]) -> ParsedLayout:
    layout_id = str(layout.get("layout_id", "inline"))
    if layout.get("ascii"):
        return parse_ascii_rows(layout_id, [str(row) for row in layout["ascii"]])
    raise ValueError("layout requires ascii rows")
