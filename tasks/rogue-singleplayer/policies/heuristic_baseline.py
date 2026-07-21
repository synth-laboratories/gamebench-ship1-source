"""Stable prototype Rogue code-policy baseline."""

from __future__ import annotations

from collections import deque
from typing import Any


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[str],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    del observation_text, session, engine, seed, ply
    action = _stairs_policy(readout)
    if action not in valid_actions:
        action = valid_actions[0]
    return {"actions": [action], "policy_reason": f"stairs policy chose {action}"}


def _stairs_policy(observation: dict[str, Any]) -> str:
    public = observation.get("public", {})
    terrain = public.get("terrain")
    hero = public.get("hero")
    if terrain and hero and terrain[int(hero[0])][int(hero[1])] == "%":
        return ">"
    if terrain and hero:
        start = (int(hero[0]), int(hero[1]))
        target = next(
            (
                (row_index, column_index)
                for row_index, row in enumerate(terrain)
                for column_index, value in enumerate(row)
                if value == "%"
            ),
            None,
        )
        if target is not None:
            path = _bfs(list(terrain), start, target)
            return path[0] if path else "."
    rows = str(
        observation.get("ascii") or observation.get("observation_text") or ""
    ).splitlines()
    start = target = None
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            if value == "@":
                start = (row_index, column_index)
            elif value == "%":
                target = (row_index, column_index)
    if start is None or target is None:
        return "."
    if start == target:
        return ">"
    path = _bfs(rows, start, target)
    return path[0] if path else "."


def _bfs(
    rows: list[str], start: tuple[int, int], target: tuple[int, int]
) -> list[str]:
    directions = (
        ("h", 0, -1),
        ("j", 1, 0),
        ("k", -1, 0),
        ("l", 0, 1),
        ("y", -1, -1),
        ("u", -1, 1),
        ("b", 1, -1),
        ("n", 1, 1),
    )
    blocked = {" ", "|", "-"}
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        (row, column), path = queue.popleft()
        for action, delta_row, delta_column in directions:
            neighbor = (row + delta_row, column + delta_column)
            next_row, next_column = neighbor
            if (
                neighbor in seen
                or next_row < 0
                or next_column < 0
                or next_row >= len(rows)
                or next_column >= len(rows[next_row])
                or rows[next_row][next_column] in blocked
            ):
                continue
            next_path = [*path, action]
            if neighbor == target:
                return next_path
            seen.add(neighbor)
            queue.append((neighbor, next_path))
    return []
