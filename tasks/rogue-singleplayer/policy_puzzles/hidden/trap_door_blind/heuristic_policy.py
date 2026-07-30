"""Hidden flawed policy — steps on known trap tiles."""

from __future__ import annotations

from collections import deque
from typing import Any


def choose_action(observation: dict[str, Any], seed: int = 0, ply: int = 0) -> str:
    del seed, ply
    ascii_map = observation.get("ascii") or observation.get("observation_text", "")
    rows = ascii_map.splitlines()
    start = target = None
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "@":
                start = (r, c)
            elif ch == "^" and target is None:
                target = (r, c)
    if start and target:
        path = _bfs(rows, start, target)
        return path[0] if path else "."
    return "."


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
    del session, engine, valid_actions
    observation = readout if isinstance(readout, dict) else {"ascii": observation_text}
    action = choose_action(observation, seed=seed, ply=ply)
    return {"actions": [action], "policy_reason": "trap door blind"}


def _bfs(rows: list[str], start: tuple[int, int], target: tuple[int, int]) -> list[str]:
    directions = [("h", 0, -1), ("j", 1, 0), ("k", -1, 0), ("l", 0, 1)]
    blocked = {" ", "|", "-"}
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        (row, col), path = queue.popleft()
        for action, dy, dx in directions:
            nr, nc = row + dy, col + dx
            if nr < 0 or nc < 0 or nr >= len(rows) or nc >= len(rows[0]) or (nr, nc) in seen:
                continue
            if rows[nr][nc] in blocked:
                continue
            seen.add((nr, nc))
            if (nr, nc) == target:
                return [*path, action]
            queue.append(((nr, nc), [*path, action]))
    return []
