"""Baseline Sokoban code policy."""

from __future__ import annotations

from typing import Any

from policies.registry import choose_action


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[str],
    engine: Any = None,
    seed: int = 0,
    **_: Any,
) -> dict[str, Any]:
    del observation_text, session, engine
    readout = _readout_from_kwargs(_, valid_actions)
    action = choose_action("greedy_distance_v1", readout, seed=seed, ply=int(_.get("ply", 0)))
    return {"actions": [action], "policy_reason": f"greedy_distance_v1:{action}"}


def _readout_from_kwargs(kwargs: dict[str, Any], valid_actions: list[str]) -> dict[str, Any]:
    readout = dict(kwargs.get("readout") or {})
    readout.setdefault("valid_actions", valid_actions)
    return readout
