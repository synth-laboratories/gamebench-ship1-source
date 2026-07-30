"""Stable prototype Rogue code-policy baseline."""

from __future__ import annotations

from typing import Any

from policies.registry import stairs_policy


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
    action = stairs_policy(readout, seed=seed, ply=ply)
    if action not in valid_actions:
        action = valid_actions[0]
    return {"actions": [action], "policy_reason": f"stairs policy chose {action}"}
