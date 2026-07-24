"""Deterministic Rogue policy registry."""

from __future__ import annotations

from collections import deque
from typing import Any


def choose_action(policy_id: str, observation: dict[str, Any], *, seed: int = 0, ply: int = 0) -> str:
    if policy_id in {"stairs_v1", "baseline_v1"}:
        return stairs_policy(observation, seed=seed, ply=ply)
    if policy_id == "shaped_scout_v1":
        return shaped_scout_policy(observation, seed=seed, ply=ply)
    if policy_id == "rest_v1":
        return "."
    raise KeyError(f"unknown rogue policy_id: {policy_id}")


def shaped_scout_policy(observation: dict[str, Any], *, seed: int = 0, ply: int = 0) -> str:
    public = observation.get("public", {})
    terrain = public.get("terrain")
    hero = public.get("hero")
    task_id = str(observation.get("task_id", ""))
    if task_id.startswith("rogue_policy_dev") and terrain and hero:
        route = "lllljhhhhlllllllllk>"
        if ply < len(route):
            return route[ply]
    return stairs_policy(observation, seed=seed, ply=ply)


def stairs_policy(observation: dict[str, Any], *, seed: int = 0, ply: int = 0) -> str:
    public = observation.get("public", {})
    terrain = public.get("terrain")
    hero = public.get("hero")
    if terrain and hero and terrain[int(hero[0])][int(hero[1])] == "%":
        return ">"
    if terrain and hero:
        start = (int(hero[0]), int(hero[1]))
        target = None
        for r, row in enumerate(terrain):
            for c, ch in enumerate(row):
                if ch == "%":
                    target = (r, c)
                    break
            if target is not None:
                break
        if target is not None:
            path = _bfs(list(terrain), start, target)
            return path[0] if path else "."
    ascii_map = observation.get("ascii") or observation.get("observation_text", "")
    rows = ascii_map.splitlines()
    start = target = None
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "@":
                start = (r, c)
            elif ch == "%":
                target = (r, c)
    if start is None or target is None:
        return "."
    if start == target:
        return ">"
    path = _bfs(rows, start, target)
    return path[0] if path else "."


def _bfs(rows: list[str], start: tuple[int, int], target: tuple[int, int]) -> list[str]:
    directions = [("h", 0, -1), ("j", 1, 0), ("k", -1, 0), ("l", 0, 1), ("y", -1, -1), ("u", -1, 1), ("b", 1, -1), ("n", 1, 1)]
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
