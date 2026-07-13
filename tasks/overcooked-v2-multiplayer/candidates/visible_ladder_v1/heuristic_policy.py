"""Baseline Overcooked v2 code policy candidate — delegates to shipped heuristic."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_TASK_ROOT = Path(__file__).resolve().parents[2]
_POLICIES = _TASK_ROOT / "policies"
if str(_POLICIES) not in sys.path:
    sys.path.insert(0, str(_POLICIES))

from heuristic_baseline import choose_joint_actions as _choose_joint_actions


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
    return _choose_joint_actions(
        observation_text=observation_text,
        session=session,
        valid_actions=valid_actions,
        engine=engine,
        readout=readout,
        seed=seed,
        ply=ply,
    )
