#!/usr/bin/env python3
"""Evaluate one Craftax-Coop policy on the fixed ALEM coordination suite."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable


TASK_DIR = Path(__file__).resolve().parents[1]
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import CraftaxCoopEnv


PolicyFn = Callable[[dict[str, Any]], Any]
MESSAGE_CODES = {"NEED_IRON", "MEET_AT", "ATTACK_MOB", "BUILD_HERE"}
COORD_REWARD_CAP = {"sync_2": 2.0, "sync_all": 3.0, "handover": 2.0}


def _load_policy(path: Path) -> PolicyFn:
    spec = importlib.util.spec_from_file_location("craftax_coop_candidate", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load policy: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    act = getattr(module, "act", None)
    if not callable(act):
        raise ValueError("policy must export act(observation)")
    return act


def _action_is_legal(action: Any, observation: dict[str, Any]) -> bool:
    """Validate the public action contract before a bad policy can abort a rollout."""
    normalized = {"kind": action} if isinstance(action, str) else action
    if not isinstance(normalized, dict) or not isinstance(normalized.get("kind"), str):
        return False
    if normalized["kind"] not in observation["legal_actions"]:
        return False
    if normalized["kind"] != "say":
        return True
    if set(normalized).difference({"kind", "to", "code", "site_id"}):
        return False
    sender = observation["agent_id"]
    if normalized.get("to") not in (*observation["legal_agent_ids"], "all"):
        return False
    if normalized.get("to") == sender or normalized.get("code") not in MESSAGE_CODES:
        return False
    return "site_id" not in normalized or isinstance(normalized["site_id"], str)


def _fallback_action(observation: dict[str, Any]) -> dict[str, str]:
    return {"kind": "rest" if "rest" in observation["legal_actions"] else "noop"}


def _episode(
    *,
    act: PolicyFn,
    entry: dict[str, Any],
    include_trace: bool,
) -> dict[str, Any]:
    env = CraftaxCoopEnv(
        max_timesteps=int(entry["max_steps"]),
        rules_profile="alem_coord_v0",
        coordination={"scenario": entry["scenario"], "alpha": entry["alpha"]},
    )
    observations, _ = env.reset(int(entry["seed"]))
    total_reward = 0.0
    invalid_action_count = 0
    failure_mode_counts: Counter[str] = Counter()
    trace: list[dict[str, Any]] = []
    decisions = 0
    for step in range(int(entry["max_steps"])):
        joint: dict[str, Any] = {}
        for agent_id in env.agent_ids:
            decisions += 1
            try:
                action = act(observations[agent_id])
            except Exception as exc:  # Candidate code is untrusted evaluation input.
                invalid_action_count += 1
                failure_mode_counts[f"policy_error:{type(exc).__name__}"] += 1
                action = _fallback_action(observations[agent_id])
            if not _action_is_legal(action, observations[agent_id]):
                invalid_action_count += 1
                failure_mode_counts["illegal_action"] += 1
                action = _fallback_action(observations[agent_id])
            joint[agent_id] = action
        observations, rewards, dones, info = env.step(joint)
        total_reward += float(rewards[env.agent_ids[0]])
        if include_trace:
            trace.append({"step": step, "joint_action": joint, "info": info})
        if dones["__all__"]:
            break

    metrics = env.alem_metrics()
    coord_success = metrics["coord_success_rate"][entry["scenario"]]
    reward_cap = COORD_REWARD_CAP[entry["scenario"]]
    reliability = (decisions - invalid_action_count) / decisions if decisions else 0.0
    result = {
        "scenario_id": entry["scenario_id"],
        "seed": int(entry["seed"]),
        "scenario": entry["scenario"],
        "alpha": float(entry["alpha"]),
        "steps": int(env._require_state().timestep),
        "shared_reward": total_reward,
        "base_reward": float(metrics["base_reward"]),
        "coord_reward": float(metrics["coord_reward"]),
        "coord_reward_cap": reward_cap,
        "coord_reward_ratio": float(metrics["coord_reward"]) / reward_cap,
        "coord_success_rate": float(coord_success["rate"]),
        "coord_success": int(coord_success["success"]),
        "coord_resolved": int(coord_success["resolved"]),
        "illegal_action_count": invalid_action_count,
        "illegal_action_reliability": reliability,
        "failure_mode_counts": dict(sorted(failure_mode_counts.items())),
        "termination_reason": env._require_state().termination_reason,
    }
    if include_trace:
        result["trace"] = trace
    return result


def run_policy_sweep(
    *,
    policy_path: Path,
    suite_path: Path,
    output_path: Path,
    include_trace: bool = False,
) -> dict[str, Any]:
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    if suite.get("rules_profile") != "alem_coord_v0":
        raise ValueError("Craftax-Coop DEO suite must select rules_profile=alem_coord_v0")
    episodes_config = suite.get("episodes")
    if not isinstance(episodes_config, list) or not episodes_config:
        raise ValueError("Craftax-Coop DEO suite must contain episodes")
    covered_kinds = {entry.get("scenario") for entry in episodes_config}
    covered_alphas = {entry.get("alpha") for entry in episodes_config}
    if covered_kinds != set(COORD_REWARD_CAP) or covered_alphas != {0.3, 0.6, 0.9}:
        raise ValueError("ALEM DEO suite must cover every coordination kind and alpha")

    act = _load_policy(policy_path)
    episodes = [
        _episode(act=act, entry=entry, include_trace=include_trace)
        for entry in episodes_config
    ]
    n = len(episodes)
    mean_coord_reward_ratio = sum(row["coord_reward_ratio"] for row in episodes) / n
    mean_coord_success_rate = sum(row["coord_success_rate"] for row in episodes) / n
    illegal_action_reliability = sum(row["illegal_action_reliability"] for row in episodes) / n
    weights = suite["score"]["weights"]
    score = (
        float(weights["coord_reward_ratio"]) * mean_coord_reward_ratio
        + float(weights["coord_success_rate"]) * mean_coord_success_rate
        + float(weights["illegal_action_reliability"]) * illegal_action_reliability
    )
    success_by_kind: dict[str, dict[str, float | int]] = {}
    for kind in sorted(COORD_REWARD_CAP):
        rows = [row for row in episodes if row["scenario"] == kind]
        success_by_kind[kind] = {
            "success": sum(row["coord_success"] for row in rows),
            "resolved": sum(row["coord_resolved"] for row in rows),
            "rate": sum(row["coord_success"] for row in rows)
            / sum(row["coord_resolved"] for row in rows)
            if sum(row["coord_resolved"] for row in rows)
            else 0.0,
        }
    failure_mode_counts: Counter[str] = Counter()
    for episode in episodes:
        failure_mode_counts.update(episode["failure_mode_counts"])
    report = {
        "schema": "gamebench.craftax_coop.alem_policy_sweep.v2",
        "env_family": "craftax-multiplayer",
        "rules_profile": "alem_coord_v0",
        "suite_id": suite["suite_id"],
        "agents": suite["agents"],
        "roles": suite["roles"],
        "reward_semantics": suite["reward_semantics"],
        "score_metric": suite["score"]["metric"],
        "score_weights": weights,
        "policy_path": str(policy_path),
        "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "score": score,
        "mean_coord_reward_ratio": mean_coord_reward_ratio,
        "mean_coord_success_rate": mean_coord_success_rate,
        "illegal_action_reliability": illegal_action_reliability,
        "mean_coord_reward": sum(row["coord_reward"] for row in episodes) / n,
        "mean_base_reward": sum(row["base_reward"] for row in episodes) / n,
        "success_rate": mean_coord_success_rate,
        "invalid_action_count": sum(row["illegal_action_count"] for row in episodes),
        "failure_mode_counts": dict(sorted(failure_mode_counts.items())),
        "coord_success_rate_by_kind": success_by_kind,
        "episode_summaries": episodes,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report
