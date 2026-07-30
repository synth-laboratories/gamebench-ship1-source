"""Greedy cooperative heuristic for Overcooked v2 symbolic MARL."""

from __future__ import annotations

from collections import deque
from typing import Any

AGENT_IDS = ("agent_0", "agent_1")
WAIT = {"kind": "wait"}
DIRECTIONS = {
    "north": (-1, 0),
    "south": (1, 0),
    "east": (0, 1),
    "west": (0, -1),
}
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}


def _bfs(
    start: tuple[int, int],
    goals: set[tuple[int, int]],
    walls: set[tuple[int, int]],
    blocked: set[tuple[int, int]],
    fixtures: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    if start in goals:
        return [start]
    queue: deque[tuple[tuple[int, int], list[tuple[int, int]]]] = deque([(start, [start])])
    seen = {start}
    while queue:
        pos, path = queue.popleft()
        if pos in goals:
            return path
        for dr, dc in DIRECTIONS.values():
            npos = (pos[0] + dr, pos[1] + dc)
            if npos in seen or npos in walls or npos in blocked or npos in fixtures:
                continue
            seen.add(npos)
            queue.append((npos, path + [npos]))
    return [start]


def _fixtures(ascii_rows: list[str]) -> dict[str, set[tuple[int, int]]]:
    fixtures = {"O": set(), "T": set(), "D": set(), "P": set(), "S": set(), "all": set()}
    for row_index, row in enumerate(ascii_rows):
        for col_index, char in enumerate(row):
            if char in {"O", "T", "D", "P", "S"}:
                fixtures[char].add((row_index, col_index))
                fixtures["all"].add((row_index, col_index))
            elif char.isdigit():
                fixtures["O"].add((row_index, col_index))
                fixtures["all"].add((row_index, col_index))
    return fixtures


def _adjacent_targets(position: tuple[int, int]) -> dict[str, tuple[int, int]]:
    targets: dict[str, tuple[int, int]] = {}
    for direction, (dr, dc) in DIRECTIONS.items():
        targets[direction] = (position[0] + dr, position[1] + dc)
    return targets


def _face_action(direction: str, valid: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidate = {"kind": "move", "direction": direction}
    return candidate if candidate in valid else None


def _adjacent_walkable_goals(
    fixture_goals: set[tuple[int, int]],
    walls: set[tuple[int, int]],
    blocked: set[tuple[int, int]],
    fixtures: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    goals: set[tuple[int, int]] = set()
    for fixture in fixture_goals:
        for dr, dc in DIRECTIONS.values():
            cell = (fixture[0] + dr, fixture[1] + dc)
            if cell in walls or cell in fixtures:
                continue
            if cell not in blocked:
                goals.add(cell)
    return goals


def _move_toward_goal(
    position: tuple[int, int],
    fixture_goals: set[tuple[int, int]],
    valid: list[dict[str, Any]],
    walls: set[tuple[int, int]],
    blocked: set[tuple[int, int]],
    fixtures: set[tuple[int, int]],
) -> dict[str, Any]:
    goals = _adjacent_walkable_goals(fixture_goals, walls, blocked, fixtures)
    if not goals:
        return WAIT
    path = _bfs(position, goals, walls, blocked, fixtures)
    if len(path) < 2:
        return WAIT
    dr = path[1][0] - path[0][0]
    dc = path[1][1] - path[0][1]
    direction = {(-1, 0): "north", (1, 0): "south", (0, 1): "east", (0, -1): "west"}[(dr, dc)]
    candidate = {"kind": "move", "direction": direction}
    return candidate if candidate in valid else WAIT


def _interact_toward(
    position: tuple[int, int],
    facing: str,
    target: tuple[int, int],
    valid: list[dict[str, Any]],
) -> dict[str, Any]:
    adj = _adjacent_targets(position)
    for direction, cell in adj.items():
        if cell == target:
            if direction == facing and {"kind": "interact"} in valid:
                return {"kind": "interact"}
            face = _face_action(direction, valid)
            if face is not None:
                return face
            if {"kind": "interact"} in valid:
                return {"kind": "interact"}
    return WAIT


def choose_action_for_agent(
    agent_id: str,
    readout: dict[str, Any],
    valid_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    if not valid_actions:
        return WAIT
    obs = (readout.get("observations") or {}).get(agent_id) or {}
    position = tuple(obs.get("position", [0, 0]))
    facing = str(obs.get("facing", "south"))
    held = obs.get("held")
    public = readout.get("public") or {}
    ascii_rows = str(readout.get("ascii", "")).splitlines()
    fixtures = _fixtures(ascii_rows)
    walls = {(r, c) for r, row in enumerate(ascii_rows) for c, ch in enumerate(row) if ch == "#"}
    other_positions = {
        tuple(agent.get("position", [0, 0]))
        for other_id, agent in public.get("agents", {}).items()
        if other_id != agent_id
    }
    blocked = set(other_positions)

    soup_ready = bool(public.get("soup_ready"))
    pot_onions = int(public.get("pot_onions", 0))
    required = int(obs.get("required_onions", public.get("required_onions", 1)) or 1)

    if held in {"soup", "plated_soup"} and fixtures["S"]:
        action = _interact_toward(position, facing, next(iter(fixtures["S"])), valid_actions)
        if action != WAIT:
            return action
        return _move_toward_goal(position, fixtures["S"], valid_actions, walls, blocked, fixtures["all"])

    if soup_ready and held is None and fixtures["P"]:
        action = _interact_toward(position, facing, next(iter(fixtures["P"])), valid_actions)
        if action != WAIT:
            return action
        return _move_toward_goal(position, fixtures["P"], valid_actions, walls, blocked, fixtures["all"])

    if held and held.startswith("ing_") and fixtures["P"]:
        required_total = sum(int(obs.get("recipe_ingredients", public.get("recipe_ingredients", [1])) or [1]))
        pot_total = sum(int(value) for value in (public.get("pot_ingredients") or {}).values())
        if pot_total < required_total:
            action = _interact_toward(position, facing, next(iter(fixtures["P"])), valid_actions)
            if action != WAIT:
                return action
            return _move_toward_goal(position, fixtures["P"], valid_actions, walls, blocked, fixtures["all"])

    if held in {"onion", "ing_0"} and fixtures["P"] and pot_onions < required:
        action = _interact_toward(position, facing, next(iter(fixtures["P"])), valid_actions)
        if action != WAIT:
            return action
        return _move_toward_goal(position, fixtures["P"], valid_actions, walls, blocked, fixtures["all"])

    if held is None and fixtures["O"]:
        action = _interact_toward(position, facing, next(iter(fixtures["O"])), valid_actions)
        if action != WAIT:
            return action
        return _move_toward_goal(position, fixtures["O"], valid_actions, walls, blocked, fixtures["all"])

    if {"kind": "interact"} in valid_actions:
        return {"kind": "interact"}
    return valid_actions[0]


def choose_joint_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: dict[str, list[dict[str, Any]]] | list[dict[str, Any]],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    joint_valid = readout.get("joint_valid_actions") or {}
    if isinstance(valid_actions, dict):
        joint_valid = valid_actions
    agent_ids = tuple(sorted(joint_valid.keys()))
    actions = {
        agent_id: choose_action_for_agent(agent_id, readout, list(joint_valid.get(agent_id, [WAIT])))
        for agent_id in agent_ids
    }
    leader = agent_ids[0] if agent_ids else "agent_0"
    if len(agent_ids) > 1 and actions[leader] != WAIT:
        for other_id in agent_ids[1:]:
            if actions[other_id] != WAIT:
                actions[other_id] = WAIT
    return {
        "joint_action": actions,
        "policy_reason": f"heuristic ply={ply} deliveries={readout.get('public', {}).get('deliveries', 0)}",
    }
