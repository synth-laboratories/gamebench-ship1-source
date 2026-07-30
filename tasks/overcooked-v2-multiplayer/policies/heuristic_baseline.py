"""Greedy cooperative heuristic for Overcooked v2 symbolic MARL."""

from __future__ import annotations

from typing import Any

from kitchen_nav import choose_joint_actions_heuristic, WAIT


def choose_joint_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: dict[str, list[dict[str, Any]]] | list[dict[str, Any]],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    joint_valid = readout.get("joint_valid_actions") or {}
    if isinstance(valid_actions, dict):
        joint_valid = valid_actions
    return choose_joint_actions_heuristic(readout, joint_valid, ply, engine=engine)
