"""Hidden flawed policy — ignores upstairs when surrounded."""

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
    del observation_text, session, engine, seed, ply
    ascii_map = (readout.get("ascii") if isinstance(readout, dict) else observation_text) or ""
    if "<" in ascii_map:
        return {"actions": ["."], "policy_reason": "upstairs escape blind wait"}
    return {"actions": ["l"], "policy_reason": "upstairs escape blind wander"}
