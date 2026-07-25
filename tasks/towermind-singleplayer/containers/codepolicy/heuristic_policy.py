"""Legal pickup-first TowerMind DEO baseline.

This baseline deliberately demonstrates the paper's pickup-only economy while
leaving the placement and hero/knight-control opportunity to a candidate. It
uses only the public structured observation and never depends on seed, fixture,
or evaluator-only state.
"""

from __future__ import annotations

from typing import Any


def act(observation: dict[str, Any]) -> dict[str, Any]:
    state = observation["structured"]
    hero = next((item for item in state["friendlies"] if item["id"] == "hero"), None)
    if hero is None or hero["pos"] is None:
        return {"kind": "wait"}
    position = hero["pos"]
    for coin in state["coins"]:
        if coin["at"] == position:
            return {"kind": "collect", "actor": "hero", "target": position}
    if state["coins"]:
        target = min(
            (coin["at"] for coin in state["coins"]),
            key=lambda cell: _distance(position, cell),
        )
        step = _step_toward(position, target)
        if step is not None and step not in state["fog_cells"]:
            return {"kind": "move", "actor": "hero", "target": step}
    return {"kind": "wait"}


def _distance(left: list[int], right: list[int]) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1])


def _step_toward(position: list[int], target: list[int]) -> list[int] | None:
    if position[0] != target[0]:
        return [position[0] + (1 if target[0] > position[0] else -1), position[1]]
    if position[1] != target[1]:
        return [position[0], position[1] + (1 if target[1] > position[1] else -1)]
    return None
