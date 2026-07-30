"""Hidden flawed policy — drops ready soup instead of delivering."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

TASK_ROOT = Path(__file__).resolve().parents[3]
if str(TASK_ROOT / "policies") not in sys.path:
    sys.path.insert(0, str(TASK_ROOT / "policies"))

from kitchen_nav import WAIT, choose_joint_actions_heuristic


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
    del observation_text, session, seed
    joint_valid = readout.get("joint_valid_actions") or (valid_actions if isinstance(valid_actions, dict) else {})
    result = choose_joint_actions_heuristic(readout, joint_valid, ply, engine=engine)
    joint = dict(result.get("joint_action") or {})
    observations = readout.get("observations") or {}
    for agent_id, obs in observations.items():
        if obs.get("held") in {"soup", "plated_soup"}:
            drop = {"kind": "interact"}
            if drop in joint_valid.get(agent_id, []):
                joint[agent_id] = drop
    return {"joint_action": joint, "policy_reason": "soup delivery dropper"}
