#!/usr/bin/env python3
"""Evaluate one public-observation TowerMind policy on the fixed L1/L2 DEO suite."""

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

from gold_python.engine import TowerMindEnv


PolicyFn = Callable[[dict[str, Any]], Any]
REQUIRED_LEVELS = {"L1", "L2"}


def _load_policy(path: Path) -> PolicyFn:
    spec = importlib.util.spec_from_file_location("towermind_code_policy", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load policy: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    act = getattr(module, "act", None)
    if not callable(act):
        raise ValueError("policy must export act(observation)")
    return act


def _episode(*, act: PolicyFn, entry: dict[str, Any], include_trace: bool) -> dict[str, Any]:
    env = TowerMindEnv()
    observation = env.reset(str(entry["level"]), seed=int(entry["seed"]))
    initial_base_hp = int(observation["structured"]["base_hp"])
    policy_errors: Counter[str] = Counter()
    trace: list[dict[str, Any]] = []
    decisions = 0
    while not env.state["terminated"] and decisions < int(entry["max_steps"]):
        try:
            action = act(observation)
        except Exception as exc:  # Candidate code is untrusted evaluation input.
            policy_errors[f"policy_error:{type(exc).__name__}"] += 1
            action = {"kind": "wait"}
        decisions += 1
        before_illegal = int(env.state["illegal_actions"])
        result = env.step(action)
        illegal_delta = int(env.state["illegal_actions"]) - before_illegal
        if illegal_delta:
            policy_errors["illegal_action"] += illegal_delta
        if include_trace:
            trace.append(
                {
                    "step": decisions - 1,
                    "action": action,
                    "illegal_action_delta": illegal_delta,
                    "reward": result["reward"],
                }
            )
        observation = result["observation"]

    state = env.state
    assert state is not None
    leaks = sum(1 for event in env.events if event["kind"] == "enemy_leaked")
    reward = float(state["total_reward"])
    base_hp = int(state["base_hp"])
    illegal_actions = int(state["illegal_actions"])
    policy_error_count = sum(
        count for kind, count in policy_errors.items() if kind.startswith("policy_error:")
    )
    reliability = max(0.0, (decisions - illegal_actions - policy_error_count) / decisions) if decisions else 0.0
    result = {
        "episode_id": entry["episode_id"],
        "level": entry["level"],
        "seed": int(entry["seed"]),
        "steps": decisions,
        "max_steps": int(entry["max_steps"]),
        "reward": reward,
        "reward_quality": max(0.0, min(1.0, 1.0 + reward / initial_base_hp)),
        "base_hp": base_hp,
        "initial_base_hp": initial_base_hp,
        "base_hp_fraction": max(0.0, base_hp / initial_base_hp),
        "leaks": leaks,
        "leak_pressure": leaks / initial_base_hp,
        "waves_cleared": state["termination_reason"] == "waves_cleared",
        "termination_reason": state["termination_reason"],
        "illegal_action_count": illegal_actions,
        "illegal_action_reliability": reliability,
        "failure_mode_counts": dict(sorted(policy_errors.items())),
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
    episodes_config = suite.get("episodes")
    if not isinstance(episodes_config, list) or not episodes_config:
        raise ValueError("TowerMind DEO suite must contain episodes")
    levels = {entry.get("level") for entry in episodes_config}
    if levels != REQUIRED_LEVELS:
        raise ValueError("TowerMind DEO suite must contain fixed L1 and L2 coverage")
    weights = suite.get("score", {}).get("weights")
    expected_weights = {
        "reward_quality",
        "base_hp_fraction",
        "waves_cleared_rate",
        "illegal_action_reliability",
    }
    if not isinstance(weights, dict) or set(weights) != expected_weights:
        raise ValueError("TowerMind DEO score weights must cover reward, base pressure, waves, and reliability")

    act = _load_policy(policy_path)
    episodes = [_episode(act=act, entry=entry, include_trace=include_trace) for entry in episodes_config]
    count = len(episodes)
    mean_reward = sum(row["reward"] for row in episodes) / count
    mean_reward_quality = sum(row["reward_quality"] for row in episodes) / count
    mean_base_hp_fraction = sum(row["base_hp_fraction"] for row in episodes) / count
    waves_cleared_rate = sum(1.0 for row in episodes if row["waves_cleared"]) / count
    illegal_action_reliability = sum(row["illegal_action_reliability"] for row in episodes) / count
    score = (
        float(weights["reward_quality"]) * mean_reward_quality
        + float(weights["base_hp_fraction"]) * mean_base_hp_fraction
        + float(weights["waves_cleared_rate"]) * waves_cleared_rate
        + float(weights["illegal_action_reliability"]) * illegal_action_reliability
    )
    failure_mode_counts: Counter[str] = Counter()
    for episode in episodes:
        failure_mode_counts.update(episode["failure_mode_counts"])
    report = {
        "schema": "gamebench.towermind.policy_sweep.v1",
        "env_family": "towermind-singleplayer",
        "suite_id": suite["suite_id"],
        "levels": sorted(levels),
        "score_metric": suite["score"]["metric"],
        "score_weights": weights,
        "policy_path": str(policy_path),
        "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "score": score,
        "mean_reward": mean_reward,
        "mean_reward_quality": mean_reward_quality,
        "mean_base_hp_fraction": mean_base_hp_fraction,
        "mean_leak_pressure": sum(row["leak_pressure"] for row in episodes) / count,
        "waves_cleared_rate": waves_cleared_rate,
        "illegal_action_reliability": illegal_action_reliability,
        "invalid_action_count": sum(row["illegal_action_count"] for row in episodes),
        "failure_mode_counts": dict(sorted(failure_mode_counts.items())),
        "episode_summaries": episodes,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
