"""Search-enhanced shaped route candidate."""

from __future__ import annotations

from typing import Any


ROUTE = "slllljhhhhlllllllllk>"


def choose_actions(*, observation_text: str, session: dict[str, Any],
                   valid_actions: list[str], engine: Any = None,
                   readout: dict[str, Any], seed: int, ply: int) -> dict[str, Any]:
    del observation_text, session, engine, readout, seed
    action = ROUTE[ply] if ply < len(ROUTE) else "."
    if action not in valid_actions:
        action = valid_actions[0]
    return {"actions": [action], "policy_reason": f"search scout route chose {action}"}
