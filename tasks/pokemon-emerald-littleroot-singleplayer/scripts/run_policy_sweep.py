#!/usr/bin/env python3
"""Run one Emerald code-policy candidate on a fixed scenario suite (Rust gold)."""

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
for path in (TASK_DIR, TASK_DIR / "containers" / "codepolicy", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rollout_code_policy import compile_check_policy, load_policy_module, rollout_code_policy


def policy_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_suite(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def scenario_max_steps(suite: dict[str, Any], scenario: dict[str, Any]) -> int:
    if "max_steps" in scenario:
        return int(scenario["max_steps"])
    return int(suite.get("max_steps", 16))


def failure_modes_for_result(result: dict[str, Any]) -> list[str]:
    details = result["reward_info"]["details"]
    if result["reward_info"]["outcome"] == "success":
        return []
    modes: list[str] = []
    if int(details.get("invalid_action_count", 0)) > 0:
        modes.append("invalid_action")
    if int(details.get("moved_manhattan", 0)) <= 0:
        modes.append("no_movement")
    if details.get("require_target") and not details.get("reached_target"):
        modes.append("target_missed")
    return modes or ["goal_not_reached"]


def run_policy_sweep(
    *,
    policy_path: Path,
    suite_path: Path,
    output_path: Path,
    include_trace: bool = False,
    base_url: str | None = None,
) -> dict[str, Any]:
    started = time.time()
    compile_check_policy(policy_path, base_url=base_url)
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
            base_url=base_url,
        )
        for scenario in scenarios
    ]
    rewards = [float(item["reward_info"]["total_reward"]) for item in results]
    outcome_rewards = [float(item["reward_info"]["outcome_reward"]) for item in results]
    successes = sum(1 for item in results if item["reward_info"]["outcome"] == "success")
    failure_counts = Counter(mode for item in results for mode in failure_modes_for_result(item))
    report = {
        "schema": "gamebench.pokemon_emerald.policy_sweep_summary.v1",
        "env_family": "pokemon-emerald-littleroot-singleplayer",
        "suite_id": str(suite["suite_id"]),
        "suite_path": str(suite_path),
        "policy_path": str(policy_path),
        "policy_sha256": policy_sha256(policy_path),
        "n_scenarios": len(scenarios),
        "successes": successes,
        "success_rate": round(successes / len(scenarios), 4) if scenarios else 0.0,
        "score": round(successes / len(scenarios), 4) if scenarios else 0.0,
        "mean_reward": round(statistics.fmean(rewards), 4) if rewards else 0.0,
        "mean_outcome_reward": round(statistics.fmean(outcome_rewards), 4) if outcome_rewards else 0.0,
        "failure_mode_counts": dict(sorted(failure_counts.items())),
        "elapsed_s": round(time.time() - started, 3),
        "episodes": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an Emerald code-policy sweep.")
    parser.add_argument("--policy", default=str(TASK_DIR / "policies" / "heuristic_baseline.py"))
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--include-trace", action="store_true")
    parser.add_argument("--base-url", default="", help="Reuse an already-running emerald_gold URL")
    args = parser.parse_args()

    report = run_policy_sweep(
        policy_path=Path(args.policy).expanduser().resolve(),
        suite_path=Path(args.suite).expanduser().resolve(),
        output_path=Path(args.output).expanduser().resolve(),
        include_trace=bool(args.include_trace),
        base_url=args.base_url or None,
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "suite_id",
                    "success_rate",
                    "mean_reward",
                    "score",
                    "failure_mode_counts",
                    "elapsed_s",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
