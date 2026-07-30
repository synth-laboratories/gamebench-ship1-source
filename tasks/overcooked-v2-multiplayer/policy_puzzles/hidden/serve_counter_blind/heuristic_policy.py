"""Hidden flawed policy — loops kitchen and never reaches serve tile."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

TASK_ROOT = Path(__file__).resolve().parents[3]
if str(TASK_ROOT / "policies") not in sys.path:
    sys.path.insert(0, str(TASK_ROOT / "policies"))

from kitchen_nav import WAIT, move_toward_fixture, parse_kitchen_map


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
    map_model = parse_kitchen_map(readout)
    observations = readout.get("observations") or {}
    joint: dict[str, dict[str, Any]] = {}
    pot_goals = map_model.pots or map_model.counters
    for agent_id, valid in joint_valid.items():
        pos = tuple((observations.get(agent_id) or {}).get("position", [0, 0]))
        blocked = set()
        if pot_goals:
            joint[agent_id] = move_toward_fixture(pos, pot_goals, list(valid), map_model, blocked)
        else:
            joint[agent_id] = WAIT if WAIT in valid else valid[0]
    return {"joint_action": joint, "policy_reason": "serve counter blind"}
