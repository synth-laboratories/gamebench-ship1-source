"""Hidden flawed policy — ignores food when HP is low."""

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
    del observation_text, session, engine, readout, seed, ply
    return {"actions": ["."], "policy_reason": "food blind scavenger ignores food while hp low and hunger rises"}
