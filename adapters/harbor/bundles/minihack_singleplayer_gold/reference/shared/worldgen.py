"""ASCII map parsing and seeded MiniHack-style layout builders."""

from __future__ import annotations

import random

from layout import ParsedLayout


def parse_ascii_rows(rows: list[str]) -> ParsedLayout:
    walls: set[tuple[int, int]] = set()
    goals: set[tuple[int, int]] = set()
    targets: set[tuple[int, int]] = set()
    boulders: set[tuple[int, int]] = set()
    monsters: set[tuple[int, int]] = set()
    lava: set[tuple[int, int]] = set()
    frozen: set[tuple[int, int]] = set()
    items: set[tuple[tuple[int, int], str]] = set()
    player: tuple[int, int] | None = None
    height = len(rows)
    width = max(len(row) for row in rows) if rows else 0
    for row_index, row in enumerate(rows):
        for col_index, char in enumerate(row):
            pos = (row_index, col_index)
            if char == "#":
                walls.add(pos)
            elif char in {".", " "}:
                continue
            elif char == "@":
                player = pos
            elif char in {"$", "0"}:
                boulders.add(pos)
            elif char in {"*", "%"}:
                targets.add(pos)
            elif char in {"<", ">", "X"}:
                goals.add(pos)
            elif char == "~":
                lava.add(pos)
            elif char == "=":
                frozen.add(pos)
            elif char == "M":
                monsters.add(pos)
            elif char == "L":
                items.add((pos, "levitation"))
            elif char == "F":
                items.add((pos, "freeze"))
            else:
                raise ValueError(f"unknown map character {char!r} at {pos}")
    if player is None:
        raise ValueError("map requires @ player start")
    return ParsedLayout(
        walls=frozenset(walls),
        goals=frozenset(goals),
        targets=frozenset(targets),
        player_start=player,
        boulders_start=frozenset(boulders),
        monsters_start=frozenset(monsters),
        lava_start=frozenset(lava),
        frozen_start=frozenset(frozen),
        items_start=frozenset(items),
        width=width,
        height=height,
    )


def build_layout(profile: str, seed: int) -> ParsedLayout:
    if profile == "corridor_straight":
        return parse_ascii_rows(
            [
                "#######",
                "#@....#",
                "#.....#",
                "#....>#",
                "#######",
            ]
        )
    if profile == "corridor_turn_left":
        return parse_ascii_rows(
            [
                "#######",
                "#@....#",
                "#.....#",
                "#.....#",
                "#>....#",
                "#######",
            ]
        )
    if profile == "corridor_turn_right":
        return parse_ascii_rows(
            [
                "#######",
                "#....@#",
                "#.....#",
                "#.....#",
                "#>....#",
                "#######",
            ]
        )
    if profile == "corridor_battle":
        return parse_ascii_rows(
            [
                "#######",
                "#@ .M>#",
                "#.....#",
                "#######",
            ]
        )
    if profile == "corridor_battle_two":
        return parse_ascii_rows(
            [
                "########",
                "#@ . M>#",
                "#......#",
                "########",
            ]
        )
    if profile == "quest_easy":
        return parse_ascii_rows(
            [
                "#######",
                "#@ L .#",
                "#~~~~~#",
                "#....>#",
                "#######",
            ]
        )
    if profile == "quest_medium":
        return parse_ascii_rows(
            [
                "########",
                "#@ F  .#",
                "#~M~~~~#",
                "#.....>#",
                "########",
            ]
        )
    if profile == "boxoban_hard":
        return parse_ascii_rows(
            [
                "#########",
                "#.@ $  %#",
                "#  $  % #",
                "#  $  % #",
                "#  $  % #",
                "#########",
            ]
        )
    if profile.startswith("maze_9x9"):
        return _build_maze(9, seed)
    if profile.startswith("maze_15x15"):
        return _build_maze(15, seed)
    raise ValueError(f"unsupported minihack profile {profile}")


def _build_maze(inner: int, seed: int) -> ParsedLayout:
    rng = random.Random(seed)
    grid = [[True for _ in range(inner)] for _ in range(inner)]
    stack = [(0, 0)]
    grid[0][0] = False
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    while stack:
        row, col = stack[-1]
        neighbors = []
        for dr, dc in directions:
            nr, nc = row + dr * 2, col + dc * 2
            if 0 <= nr < inner and 0 <= nc < inner and grid[nr][nc]:
                neighbors.append((nr, nc, dr, dc))
        if not neighbors:
            stack.pop()
            continue
        nr, nc, dr, dc = rng.choice(neighbors)
        grid[nr][nc] = False
        grid[row + dr][col + dc] = False
        stack.append((nr, nc))

    start_inner = (0, 0)
    goal_inner = (inner - 1, inner - 1)
    grid[start_inner[0]][start_inner[1]] = False
    grid[goal_inner[0]][goal_inner[1]] = False

    rows: list[str] = []
    offset = 1
    for row_index in range(inner + 2):
        chars: list[str] = []
        for col_index in range(inner + 2):
            if row_index == 0 or col_index == 0 or row_index == inner + 1 or col_index == inner + 1:
                chars.append("#")
                continue
            inner_row = row_index - offset
            inner_col = col_index - offset
            if grid[inner_row][inner_col]:
                chars.append("#")
            elif inner_row == start_inner[0] and inner_col == start_inner[1]:
                chars.append("@")
            elif inner_row == goal_inner[0] and inner_col == goal_inner[1]:
                chars.append(">")
            else:
                chars.append(".")
        rows.append("".join(chars))
    return parse_ascii_rows(rows)


_DIRECTIONS = {
    "north": (-1, 0),
    "south": (1, 0),
    "east": (0, 1),
    "west": (0, -1),
    "northeast": (-1, 1),
    "northwest": (-1, -1),
    "southeast": (1, 1),
    "southwest": (1, -1),
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}


def direction_delta(direction: str) -> tuple[int, int]:
    key = direction.lower().strip()
    if key not in _DIRECTIONS:
        raise ValueError(f"unknown direction {direction}")
    return _DIRECTIONS[key]


def cardinal_directions() -> tuple[str, ...]:
    return ("north", "south", "east", "west")
