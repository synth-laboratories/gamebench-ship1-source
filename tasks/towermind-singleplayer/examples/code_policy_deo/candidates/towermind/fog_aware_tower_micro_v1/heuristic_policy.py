"""Fog-aware TowerMind candidate using public pickup, tower, and micro state.

The policy has no level, seed, or fixture branches. It first secures pickup
gold, places complementary defenses at non-fog spatial slots nearest to active
pressure, and then controls visible hero/knights for adjacent attacks or safe
one-cell pursuit. It therefore preserves the TowerMind macro/micro tradeoff
without relying on evaluator-only state.
"""

from __future__ import annotations

from typing import Any


TOWER_COSTS = {"archer": 3, "magician": 4, "knight": 5}


def act(observation: dict[str, Any]) -> dict[str, Any]:
    state = observation["structured"]
    friendlies = [item for item in state["friendlies"] if item["pos"] is not None]
    coins = state["coins"]
    for friendly in friendlies:
        for coin in coins:
            if coin["at"] == friendly["pos"]:
                return {"kind": "collect", "actor": friendly["id"], "target": friendly["pos"]}

    built_kinds = {tower["kind"] for tower in state["towers"]}
    for tower in ("magician", "knight", "archer"):
        if tower not in built_kinds and state["gold"] >= TOWER_COSTS[tower]:
            slot = _choose_slot(state)
            if slot is not None:
                return {"kind": "build", "tower": tower, "target": slot}

    for friendly in _micro_priority(friendlies):
        target = _adjacent_enemy(friendly["pos"], state["enemies"])
        if target is not None:
            return {"kind": "attack", "actor": friendly["id"], "target": target["id"]}

    for friendly in _micro_priority(friendlies):
        step = _safe_pursuit_step(friendly["pos"], state)
        if step is not None:
            return {"kind": "move", "actor": friendly["id"], "target": step}
    return {"kind": "wait"}


def _choose_slot(state: dict[str, Any]) -> str | None:
    occupied = {tower["slot"] for tower in state["towers"]}
    fog = {tuple(cell) for cell in state["fog_cells"]}
    candidates = [
        (name, position)
        for name, position in state["build_slots"].items()
        if name not in occupied and tuple(position) not in fog
    ]
    if not candidates:
        return None
    pressure = [enemy["pos"] for enemy in state["enemies"]]
    if not pressure:
        return min(candidates, key=lambda item: (item[1][0], item[1][1]))[0]
    return min(
        candidates,
        key=lambda item: (min(_distance(item[1], point) for point in pressure), item[1][0], item[1][1]),
    )[0]


def _micro_priority(friendlies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(friendlies, key=lambda item: (not item["id"].startswith("knight_"), item["id"]))


def _adjacent_enemy(position: list[int], enemies: list[dict[str, Any]]) -> dict[str, Any] | None:
    reachable = [enemy for enemy in enemies if _distance(position, enemy["pos"]) <= 1]
    if not reachable:
        return None
    return max(reachable, key=lambda enemy: (enemy["path_index"], enemy["id"]))


def _safe_pursuit_step(position: list[int], state: dict[str, Any]) -> list[int] | None:
    if not state["enemies"]:
        return None
    target = max(state["enemies"], key=lambda enemy: (enemy["path_index"], enemy["id"]))["pos"]
    options = [
        [position[0] + 1, position[1]],
        [position[0] - 1, position[1]],
        [position[0], position[1] + 1],
        [position[0], position[1] - 1],
    ]
    fog = {tuple(cell) for cell in state["fog_cells"]}
    legal = [
        cell
        for cell in options
        if 0 <= cell[0] < 10 and 0 <= cell[1] < 7 and tuple(cell) not in fog
    ]
    if not legal:
        return None
    current_distance = _distance(position, target)
    best = min(legal, key=lambda cell: (_distance(cell, target), cell[0], cell[1]))
    return best if _distance(best, target) < current_distance else None


def _distance(left: list[int], right: list[int]) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1])
