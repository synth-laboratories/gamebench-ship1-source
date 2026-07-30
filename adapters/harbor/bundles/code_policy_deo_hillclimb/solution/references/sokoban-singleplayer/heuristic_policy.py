"""Exact small-board Sokoban planner for the policy sweep."""

from __future__ import annotations

from collections import deque
from typing import Any


_DIRECTIONS = (
    ("up", -1, 0),
    ("down", 1, 0),
    ("left", 0, -1),
    ("right", 0, 1),
)


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[str],
    engine: Any = None,
    seed: int = 0,
    readout: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    del observation_text, session, engine, seed, kwargs
    if not valid_actions:
        return {"actions": [], "policy_reason": "bfs: terminal"}

    current = readout or {}
    public = dict(current.get("public") or {})
    room = public.get("room_state") or []
    player = tuple(public.get("player") or ())
    boxes = frozenset(tuple(pos) for pos in public.get("boxes") or [])
    if not room or len(player) != 2:
        action = valid_actions[0]
        return {"actions": [action], "policy_reason": f"bfs: unavailable:{action}"}

    goals = frozenset(
        (r, c)
        for r, row in enumerate(room)
        for c, cell in enumerate(row)
        if cell in (2, 3, 6)
    )
    plan = _solve(room, player, boxes, goals)
    action = plan[0] if plan and plan[0] in valid_actions else valid_actions[0]
    return {
        "actions": [action],
        "policy_reason": f"bfs:{action}:remaining={max(0, len(plan) - 1)}",
    }


def _solve(
    room: list[list[int]],
    player: tuple[int, int],
    boxes: frozenset[tuple[int, int]],
    goals: frozenset[tuple[int, int]],
) -> list[str]:
    if boxes <= goals:
        return []
    height = len(room)
    width = max((len(row) for row in room), default=0)
    walls = {
        (r, c)
        for r, row in enumerate(room)
        for c in range(width)
        if c >= len(row) or row[c] == 0
    }
    start = (player, boxes)
    queue = deque([start])
    previous: dict[tuple[tuple[int, int], frozenset[tuple[int, int]]], tuple[Any, str] | None] = {
        start: None
    }
    while queue:
        state = queue.popleft()
        pos, state_boxes = state
        for action, dr, dc in _DIRECTIONS:
            nxt = (pos[0] + dr, pos[1] + dc)
            if nxt in walls:
                continue
            next_boxes = state_boxes
            if nxt in state_boxes:
                beyond = (nxt[0] + dr, nxt[1] + dc)
                if beyond in walls or beyond in state_boxes:
                    continue
                next_boxes = frozenset((state_boxes - {nxt}) | {beyond})
                if beyond not in goals and _dead_corner(beyond, walls, goals):
                    continue
            next_state = (nxt, next_boxes)
            if next_state in previous:
                continue
            previous[next_state] = (state, action)
            if next_boxes <= goals:
                return _reconstruct(next_state, previous)
            queue.append(next_state)
    return []


def _dead_corner(
    pos: tuple[int, int], walls: set[tuple[int, int]], goals: frozenset[tuple[int, int]]
) -> bool:
    r, c = pos
    return ((r - 1, c) in walls or (r + 1, c) in walls) and (
        (r, c - 1) in walls or (r, c + 1) in walls
    )


def _reconstruct(state: Any, previous: dict[Any, tuple[Any, str] | None]) -> list[str]:
    actions: list[str] = []
    while previous[state] is not None:
        parent, action = previous[state]
        actions.append(action)
        state = parent
    actions.reverse()
    return actions
