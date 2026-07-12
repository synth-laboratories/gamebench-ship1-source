"""Hidden flawed policy — wall-follows and skips door tiles."""

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
    del observation_text, session, engine, readout, seed
    route = [".", ".", "h", "h", "l", "l", "j", "j", "k", "k"]
    action = route[ply % len(route)]
    return {"actions": [action], "policy_reason": "door blind scout"}
