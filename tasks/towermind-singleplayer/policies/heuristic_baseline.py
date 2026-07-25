"""Small deterministic placement-and-pickup baseline for local DEO smoke runs."""

from __future__ import annotations

from typing import Any


def act(observation: dict[str, Any]) -> dict[str, Any]:
    state = observation["structured"]
    friendlies = {item["id"]: item for item in state["friendlies"]}
    hero = friendlies.get("hero")
    if hero and hero["pos"] is not None:
        for coin in state["coins"]:
            if coin["at"] == hero["pos"]:
                return {"kind": "collect", "actor": "hero", "target": hero["pos"]}
    built = {tower["kind"] for tower in state["towers"]}
    if state["gold"] >= 3 and "archer" not in built and "gate_archer" in state["build_slots"]:
        return {"kind": "build", "tower": "archer", "target": "gate_archer"}
    if state["gold"] >= 4 and "magician" not in built and "aoe_gate" in state["build_slots"]:
        return {"kind": "build", "tower": "magician", "target": "aoe_gate"}
    if state["gold"] >= 5 and "knight" not in built and "knight_post" in state["build_slots"]:
        return {"kind": "build", "tower": "knight", "target": "knight_post"}
    if hero and hero["pos"] is not None:
        for coin in state["coins"]:
            target = coin["at"]
            dx = target[0] - hero["pos"][0]
            dy = target[1] - hero["pos"][1]
            if abs(dx) + abs(dy) == 1:
                return {"kind": "move", "actor": "hero", "target": target}
    return {"kind": "wait"}
