#!/usr/bin/env python3
"""Run one MiniHack code-policy candidate on a fixed scenario suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from containers.codepolicy.rollout_code_policy import compile_check_policy, load_policy_module, rollout_code_policy


def policy_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_suite(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def scenario_max_steps(suite: dict[str, Any], scenario: dict[str, Any]) -> int:
    overrides = dict((scenario.get("rules") or {}).get("overrides", {}))
    if "max_steps" in overrides:
        return int(overrides["max_steps"])
    return int(suite.get("max_steps", 64))


def failure_modes_for_result(result: dict[str, Any]) -> list[str]:
    details = result["reward_info"]["details"]
    if details["outcome"] == "success":
        return []
    modes: list[str] = []
    if int(details.get("invalid_action_count", 0)) > 0:
        modes.append("invalid_action")
    if details["outcome"] == "truncated":
        modes.append("truncated")
    profile = str(details.get("profile", ""))
    if profile.startswith("boxoban") or "boxoban" in profile:
        modes.append("boxoban_incomplete")
    else:
        modes.append("goal_not_reached")
    return modes or ["failed"]


def run_policy_sweep(
    *,
    policy_path: Path,
    suite_path: Path,
    output_path: Path,
    include_trace: bool = False,
) -> dict[str, Any]:
    started = time.time()
    compile_check_policy(policy_path)
    policy_fn = load_policy_module(policy_path)
    suite = load_suite(suite_path)
    scenarios = list(suite.get("scenarios") or [])
    if not scenarios:
        raise ValueError(f"suite {suite_path} has no scenarios")
    results = [
        rollout_code_policy(
            policy_path=policy_path,
            scenario=scenario,
            max_steps=scenario_max_steps(suite, scenario),
            include_trace=include_trace,
            candidate_fn=policy_fn,
        )
        for scenario in scenarios
    ]
    rewards = [float(item["reward_info"]["outcome_reward"]) for item in results]
    successes = sum(1 for item in results if item["reward_info"]["details"]["outcome"] == "success")
    failure_counts = Counter(mode for item in results for mode in failure_modes_for_result(item))
    invalid_actions = sum(int(item["reward_info"]["details"].get("invalid_action_count", 0)) for item in results)
    report = {
        "schema": "gamebench.minihack.policy_sweep_summary.v1",
        "env_family": "minihack-singleplayer",
        "suite_id": str(suite["suite_id"]),
        "suite_path": str(suite_path),
        "policy_path": str(policy_path),
        "policy_sha256": policy_sha256(policy_path),
        "scenarios": scenarios,
        "n_scenarios": len(scenarios),
        "successes": successes,
        "success_rate": round(successes / len(scenarios), 4) if scenarios else 0.0,
        "score": round(successes / len(scenarios), 4) if scenarios else 0.0,
        "mean_reward": round(statistics.mean(rewards), 4) if rewards else 0.0,
        "invalid_action_count": invalid_actions,
        "failure_mode_counts": dict(sorted(failure_counts.items())),
        "elapsed_s": round(time.time() - started, 3),
        "episodes": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a MiniHack code-policy sweep.")
    parser.add_argument("--policy", default=str(TASK_DIR / "policies" / "heuristic_baseline.py"))
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--include-trace", action="store_true")
    args = parser.parse_args()

    report = run_policy_sweep(
        policy_path=Path(args.policy).expanduser().resolve(),
        suite_path=Path(args.suite).expanduser().resolve(),
        output_path=Path(args.output).expanduser().resolve(),
        include_trace=bool(args.include_trace),
    )
    printable = {
        key: report[key]
        for key in ("suite_id", "success_rate", "mean_reward", "failure_mode_counts", "elapsed_s")
    }
    print(json.dumps(printable, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
