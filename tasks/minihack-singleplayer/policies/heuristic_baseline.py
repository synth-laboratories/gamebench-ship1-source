"""Greedy goal-seeking policy for MiniHack navigation scenarios."""

from __future__ import annotations

from collections import deque
from typing import Any


def choose_action(readout: dict[str, Any], seed: int, ply: int) -> dict[str, Any]:
    valid = readout.get("valid_actions") or []
    if not valid:
        return {"kind": "wait"}
    public = readout.get("public") or {}
    player = tuple(public.get("player", [0, 0]))
    ascii_rows = str(readout.get("ascii", "")).splitlines()
    if not ascii_rows:
        return valid[0]
    goals = {(row_index, col_index) for row_index, row in enumerate(ascii_rows) for col_index, char in enumerate(row) if char == ">"}
    targets = {(row_index, col_index) for row_index, row in enumerate(ascii_rows) for col_index, char in enumerate(row) if char == "*"}
    boulders = {tuple(cell) for cell in public.get("boulders", [])}
    if targets and boulders:
        return _boxoban_step(player, boulders, targets, ascii_rows, valid)
    if goals:
        return _nav_step(player, next(iter(goals)), ascii_rows, valid)
    return valid[0]


def _nav_step(
    player: tuple[int, int],
    goal: tuple[int, int],
    ascii_rows: list[str],
    valid: list[dict[str, Any]],
) -> dict[str, Any]:
    path = _bfs(player, goal, ascii_rows, set())
    if len(path) < 2:
        return valid[0]
    dr = path[1][0] - path[0][0]
    dc = path[1][1] - path[0][1]
    direction = {( -1, 0): "north", (1, 0): "south", (0, 1): "east", (0, -1): "west"}[(dr, dc)]
    candidate = {"kind": "move", "direction": direction}
    return candidate if candidate in valid else valid[0]


def _boxoban_step(
    player: tuple[int, int],
    boulders: set[tuple[int, int]],
    targets: set[tuple[int, int]],
    ascii_rows: list[str],
    valid: list[dict[str, Any]],
) -> dict[str, Any]:
    for direction in ("north", "south", "east", "west"):
        candidate = {"kind": "move", "direction": direction}
        if candidate not in valid:
            continue
        dr, dc = {"north": (-1, 0), "south": (1, 0), "east": (0, 1), "west": (0, -1)}[direction]
        nr, nc = player[0] + dr, player[1] + dc
        if (nr, nc) in boulders:
            br, bc = nr + dr, nc + dc
            if (br, bc) in targets:
                return candidate
        elif (nr, nc) in targets and not boulders:
            return candidate
    unresolved = next(iter(targets - boulders))
    return _nav_step(player, unresolved, ascii_rows, valid)


def _bfs(
    start: tuple[int, int],
    goal: tuple[int, int],
    ascii_rows: list[str],
    boulders: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    height = len(ascii_rows)
    width = max(len(row) for row in ascii_rows)
    walls = {(r, c) for r, row in enumerate(ascii_rows) for c, ch in enumerate(row) if ch == "#"}
    queue: deque[tuple[tuple[int, int], list[tuple[int, int]]]] = deque([(start, [start])])
    seen = {start}
    while queue:
        pos, path = queue.popleft()
        if pos == goal:
            return path
        for dr, dc in ((-1, 0), (1, 0), (0, 1), (0, -1)):
            npos = (pos[0] + dr, pos[1] + dc)
            if npos in seen or npos in walls or npos in boulders:
                continue
            if 0 <= npos[0] < height and 0 <= npos[1] < width:
                seen.add(npos)
                queue.append((npos, path + [npos]))
    return [start]


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[dict[str, Any]],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    action = choose_action(readout, seed, ply)
    return {"actions": [action], "policy_reason": f"heuristic ply={ply} profile={readout.get('profile', '')}"}
