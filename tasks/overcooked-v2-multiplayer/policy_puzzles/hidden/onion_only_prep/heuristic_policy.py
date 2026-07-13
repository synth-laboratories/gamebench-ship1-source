"""Hidden flawed policy — chops onions but never starts the pot."""

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
    del observation_text, session, seed, ply
    joint_valid = readout.get("joint_valid_actions") or (valid_actions if isinstance(valid_actions, dict) else {})
    agent_ids = tuple(sorted(joint_valid.keys()))
    map_model = parse_kitchen_map(readout)
    positions = {agent_id: tuple(obs.get("position", [0, 0])) for agent_id, obs in (readout.get("observations") or {}).items()}
    joint: dict[str, dict[str, Any]] = {agent_id: WAIT for agent_id in agent_ids}
    for agent_id in agent_ids:
        valid = list(joint_valid.get(agent_id, [WAIT]))
        pos = positions.get(agent_id, (0, 0))
        blocked = {p for aid, p in positions.items() if aid != agent_id}
        if map_model.onions:
            action = move_toward_fixture(pos, map_model.onions, valid, map_model, blocked)
            if action != WAIT:
                joint[agent_id] = action
                continue
        pick = {"kind": "interact"}
        if pick in valid:
            joint[agent_id] = pick
        else:
            joint[agent_id] = valid[0] if valid else WAIT
    return {"joint_action": joint, "policy_reason": "onion only prep"}
