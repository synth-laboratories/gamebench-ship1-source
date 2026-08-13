"""Bedroom-focused explorer: prefer down/right holds from May's room."""

from __future__ import annotations

from typing import Any


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[str],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    world = readout.get("world") or {}
    if world.get("dialogue") or world.get("menu_open"):
        return {"actions": [{"action": "a", "frames": 1}], "policy_reason": "clear UI"}
    checkpoint = str(readout.get("checkpoint") or "")
    if "bedroom" in checkpoint or str(world.get("map") or "").endswith("2_f"):
        plan = ("down", "down", "right", "right", "down", "left")
        action = plan[ply % len(plan)]
        return {"actions": [{"action": action, "frames": 16}], "policy_reason": f"bedroom {action}"}
    # Outside bedrooms: short right then down.
    action = "right" if ply % 2 == 0 else "down"
    return {"actions": [{"action": action, "frames": 16}], "policy_reason": f"field {action}"}
