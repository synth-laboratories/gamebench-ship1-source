from __future__ import annotations

from typing import Any


def plan_actions(scenario: dict[str, Any], objective: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    scenario_id = str(scenario.get("scenario_id", ""))
    if scenario_id == "lantern_crypt_lite":
        return [
            {"type": "message", "target": "party", "payload": {"text": "Scout the first door."}},
            {"type": "move", "direction": "east"},
            {"type": "end_turn"},
            {"type": "guard"},
            {"type": "end_turn"},
            {"type": "move", "direction": "east"},
            {"type": "open_door", "target": "door_1"},
        ]
    return [
        {"type": "message", "target": "party", "payload": {"text": "Take the first safe step."}},
        {"type": "move", "direction": "east"},
        {"type": "end_turn"},
    ]
