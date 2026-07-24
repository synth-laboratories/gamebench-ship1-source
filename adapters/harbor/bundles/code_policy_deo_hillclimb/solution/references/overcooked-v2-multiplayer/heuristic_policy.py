"""Fix recipe cardinality when the readout's legacy onion field is misleading."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

_TASK_ROOT = Path(__file__).resolve().parents[3] / "gamebench" / "tasks" / "overcooked-v2-multiplayer"
_POLICIES = _TASK_ROOT / "policies"
if str(_POLICIES) not in sys.path:
    sys.path.insert(0, str(_POLICIES))

from kitchen_nav import choose_joint_actions_heuristic


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

    adjusted = copy.deepcopy(readout)
    public = adjusted.get("public") or {}
    # Some mixed/trio recipes retain required_onions=1 for compatibility,
    # while recipe_ingredients is the authoritative ingredient list.
    recipe = public.get("recipe_ingredients") or []
    if len(recipe) > 1:
        public.pop("required_onions", None)
        for obs in (adjusted.get("observations") or {}).values():
            obs.pop("required_onions", None)
    return choose_joint_actions_heuristic(adjusted, joint_valid, ply, engine=engine)
