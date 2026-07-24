"""Deterministic grid and Sokoban planner for the MiniHack policy sweep."""

from __future__ import annotations

from collections import deque
from typing import Any

DIRS = ((-1, 0, "north"), (1, 0, "south"), (0, 1, "east"), (0, -1, "west"))


def _grid(readout: dict[str, Any]) -> tuple[set[tuple[int, int]], set[tuple[int, int]], set[tuple[int, int]], set[tuple[int, int]]]:
    rows = str(readout.get("ascii", "")).splitlines()
    walls = {(r, c) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch == "#"}
    goals = {(r, c) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch == ">"}
    targets = {(r, c) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch in "%*"}
    boxes = {tuple(p) for p in (readout.get("public") or {}).get("boulders", [])}
    return walls, goals, targets, boxes


def _walk(start: tuple[int, int], goals: set[tuple[int, int]], walls: set[tuple[int, int]], blocked: set[tuple[int, int]]) -> list[dict[str, Any]]:
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        pos, path = queue.popleft()
        if pos in goals:
            return path
        for dr, dc, name in DIRS:
            nxt = (pos[0] + dr, pos[1] + dc)
            if nxt in seen or nxt in walls or nxt in blocked:
                continue
            seen.add(nxt)
            queue.append((nxt, path + [{"kind": "move", "direction": name}]))
    return []


def _sokoban_step(start: tuple[int, int], boxes: set[tuple[int, int]], targets: set[tuple[int, int]], walls: set[tuple[int, int]]) -> list[dict[str, Any]]:
    """Move the leftmost unfinished box along its row to its matching target."""
    by_row = {row: max(col for r, col in targets if r == row) for row in {r for r, _ in targets}}
    unfinished = [(r, c) for r, c in boxes if c < by_row.get(r, c)]
    if not unfinished:
        return []
    row, col = min(unfinished)
    stand = (row, col - 1)
    if start == stand:
        return [{"kind": "move", "direction": "east"}]
    path = _walk(start, {stand}, walls, boxes)
    return path


def _legal(action: dict[str, Any], valid: list[dict[str, Any]]) -> bool:
    return action in valid


def choose_actions(
    *, observation_text: str, session: dict[str, Any], valid_actions: list[dict[str, Any]],
    engine: Any = None, readout: dict[str, Any], seed: int, ply: int,
) -> dict[str, Any]:
    if not valid_actions:
        return {"actions": [{"kind": "wait"}], "policy_reason": "terminal"}
    public = readout.get("public") or {}
    player = tuple(public.get("player", [0, 0]))
    walls, goals, targets, boxes = _grid(readout)

    # Combat must be resolved before trying to walk through the monster.
    for action in valid_actions:
        if action.get("kind") == "attack":
            return {"actions": [action], "policy_reason": "adjacent monster"}
    if any(action.get("kind") == "pickup" for action in valid_actions):
        return {"actions": [{"kind": "pickup"}], "policy_reason": "collect item"}

    if targets and boxes:
        path = _sokoban_step(player, boxes, targets, walls)
    else:
        monsters = {tuple(p) for p in public.get("monsters", [])}
        lava = {tuple(p) for p in public.get("lava", [])}
        items = {tuple(x.get("position", [])) for x in public.get("items_on_ground", [])}
        inventory = set(public.get("inventory", []))
        blocked = monsters | boxes
        if lava and "levitation" not in inventory:
            path = _walk(player, items, walls, blocked | lava)
        else:
            path = _walk(player, goals, walls, blocked | lava - set(public.get("frozen", [])))
    if path and _legal(path[0], valid_actions):
        return {"actions": [path[0]], "policy_reason": "grid plan"}
    return {"actions": [valid_actions[0]], "policy_reason": "legal fallback"}
