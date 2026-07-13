"""Shallow joint search: refine helper action via engine.clone_for_sim()."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_TASK_ROOT = Path(__file__).resolve().parents[2]
_POLICIES = _TASK_ROOT / "policies"
if str(_POLICIES) not in sys.path:
    sys.path.insert(0, str(_POLICIES))

from kitchen_nav import choose_joint_actions_heuristic, score_sim_engine


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

    heuristic = choose_joint_actions_heuristic(readout, joint_valid, ply, engine=engine)
    joint_action = dict(heuristic["joint_action"])
    if engine is None:
        return heuristic

    agent_ids = sorted(joint_valid.keys())
    if len(agent_ids) < 2:
        return heuristic

    cook_agent_id = agent_ids[0]
    helper_agent_id = agent_ids[1]
    baseline_sim = engine.clone_for_sim()
    baseline_sim.step(joint_action)
    best_score = score_sim_engine(baseline_sim)
    best_joint = dict(joint_action)

    for helper_action in joint_valid.get(helper_agent_id, [{"kind": "wait"}]):
        candidate_joint = dict(joint_action)
        candidate_joint[helper_agent_id] = helper_action
        if candidate_joint == joint_action:
            continue
        sim = engine.clone_for_sim()
        sim.step(candidate_joint)
        score = score_sim_engine(sim)
        if score > best_score + 0.25:
            best_score = score
            best_joint = candidate_joint

    return {
        "joint_action": best_joint,
        "policy_reason": (
            f"bfs_joint_helper ply={ply} score={best_score:.2f} "
            f"deliveries={readout.get('public', {}).get('deliveries', 0)}"
        ),
    }
