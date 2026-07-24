#!/usr/bin/env python3
"""Evaluate one Craftax-Coop joint code policy on a fixed seed suite."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import CraftaxCoopEnv


def _load_policy(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("craftax_coop_candidate", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load policy: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    act = getattr(module, "act", None)
    if not callable(act):
        raise ValueError("policy must export act(observation)")
    return act


def run_policy_sweep(
    *,
    policy_path: Path,
    suite_path: Path,
    output_path: Path,
    include_trace: bool = False,
) -> dict[str, Any]:
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    act = _load_policy(policy_path)
    episodes: list[dict[str, Any]] = []
    for seed in suite["seeds"]:
        env = CraftaxCoopEnv()
        observations, _ = env.reset(int(seed))
        total_reward = 0.0
        trace: list[dict[str, Any]] = []
        invalid_action_count = 0
        for step in range(int(suite["max_steps"])):
            joint = {agent: act(observations[agent]) for agent in env.agent_ids}
            observations, rewards, dones, info = env.step(joint)
            total_reward += float(rewards[env.agent_ids[0]])
            invalid_action_count += len(info.get("invalid_actions", []))
            if include_trace:
                trace.append({"step": step, "joint_action": joint, "info": info})
            if dones["__all__"]:
                break
        state = env._require_state()
        episode = {
            "seed": int(seed),
            "shared_reward": total_reward,
            "achievement_count": sum(1 for value in state.achievements.values() if value),
            "trade_count": int(state.trade_count),
            "steps": int(state.timestep),
            "invalid_action_count": invalid_action_count,
            "termination_reason": state.termination_reason,
        }
        if include_trace:
            episode["trace"] = trace
        episodes.append(episode)

    mean_reward = sum(row["shared_reward"] for row in episodes) / len(episodes)
    mean_achievements = sum(row["achievement_count"] for row in episodes) / len(episodes)
    mean_trades = sum(row["trade_count"] for row in episodes) / len(episodes)
    score = mean_reward + mean_achievements + (0.25 * mean_trades)
    report = {
        "schema": "gamebench.craftax_coop.policy_sweep.v1",
        "env_family": "craftax-multiplayer",
        "suite_id": suite["suite_id"],
        "agents": suite["agents"],
        "roles": suite["roles"],
        "reward_semantics": suite["reward_semantics"],
        "policy_path": str(policy_path),
        "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "score": score,
        "mean_reward": mean_reward,
        "mean_achievement_count": mean_achievements,
        "mean_trade_count": mean_trades,
        "invalid_action_count": sum(row["invalid_action_count"] for row in episodes),
        "success_rate": sum(row["achievement_count"] > 0 for row in episodes) / len(episodes),
        "failure_mode_counts": {},
        "episode_summaries": episodes,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report

