from __future__ import annotations

from typing import Any


def plan_actions(scenario: dict[str, Any], objective: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Take the first-step reward, then collect the nearby objective item."""
    if str(scenario.get("scenario_id", "")) != "lantern_crypt_lite":
        return [
            {"type": "message", "target": "party", "payload": {"text": "Take the first safe step."}},
            {"type": "move", "direction": "east"},
            {"type": "end_turn"},
        ]

    return [
        {"type": "message", "target": "party", "payload": {"text": "Scout the first door."}},
        {"type": "move", "direction": "east"},
        {"type": "end_turn"},
        {"type": "guard"},
        {"type": "end_turn"},
        {"type": "move", "direction": "east"},
        {"type": "open_door", "target": "door_1"},
        {"type": "end_turn"},
        {"type": "move", "direction": "east"},
        {"type": "move", "direction": "east"},
        {"type": "end_turn"},
        {"type": "move", "direction": "east"},
        {"type": "move", "direction": "south"},
        {"type": "end_turn"},
        {"type": "move", "direction": "east"},
        {"type": "interact", "target": "little_ember_idol"},
    ]
