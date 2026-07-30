#!/usr/bin/env python3
"""Run one FrogsGame code-policy candidate on a fixed suite."""

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
from scoring import validate_frogs


def policy_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_suite(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def failure_modes_for_result(result: dict[str, Any]) -> list[str]:
    details = result["reward_info"]["details"]
    if details["outcome"] == "success":
        return []
    modes: list[str] = []
    if int(details.get("invalid_action_count", 0)) > 0:
        modes.append("invalid_action")
    if details["outcome"] == "truncated":
        modes.append("truncated")
    public = result["state"]["public"]
    private = result["state"]["private"]
    if not public.get("submitted"):
        modes.append("not_submitted")
    board_n = len(public.get("board") or [])
    if len(public.get("frogs") or []) < board_n:
        modes.append("incomplete_board")
    if private.get("terminated") and float(private.get("total_reward", 0.0)) <= 0.0:
        modes.append("submitted_incorrect")
    for violation in public.get("violations") or []:
        code = str(violation.get("code", "violation"))
        modes.append(f"violation:{code}")
    return modes or ["failed"]


def _episode_layout_quality(result: dict[str, Any]) -> float:
    """Score valid Frogs solutions by placement quality, not just success."""

    public = result["state"]["public"]
    board = public.get("board") or []
    frogs = [tuple(cell) for cell in public.get("frogs") or []]
    invalid_actions = int(result["reward_info"]["details"].get("invalid_action_count", 0))
    if validate_frogs(board, frogs, require_complete=True):
        n = max(1, len(board))
        partial = len(frogs) / n
        return round(max(0.0, 0.05 * partial - 0.01 * invalid_actions), 6)
    weighted_cells = sum((row + 1) * (col + 1) for row, col in frogs)
    rightward_tiebreak = sum(col for _, col in frogs) / 100.0
    return round(max(0.0, (weighted_cells + rightward_tiebreak) / 100.0 - 0.01 * invalid_actions), 6)


def _suite_tasks(suite: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(suite.get("tasks"), list):
        tasks: list[dict[str, Any]] = []
        for index, item in enumerate(suite["tasks"]):
            if not isinstance(item, dict):
                raise ValueError(f"suite task {index} must be an object")
            tasks.append(
                {
                    "task_path": str(item.get("task_path", suite.get("task_template", "tasks/policy_dev_template.json"))),
                    "seed": int(item.get("seed", index + 1)),
                    "max_steps": int(item.get("max_steps", suite.get("max_steps", 16))),
                }
            )
        return tasks
    task_path = str(suite.get("task_template", "tasks/policy_dev_template.json"))
    max_steps = int(suite.get("max_steps", 16))
    return [{"task_path": task_path, "seed": int(seed), "max_steps": max_steps} for seed in suite["seeds"]]


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
    suite_tasks = _suite_tasks(suite)
    score_metric = str(suite.get("score_metric", "success_rate"))
    results = [
        rollout_code_policy(
            policy_path=policy_path,
            seed=int(item["seed"]),
            task_path=str(item["task_path"]),
            max_steps=int(item["max_steps"]),
            include_trace=include_trace,
            candidate_fn=policy_fn,
        )
        for item in suite_tasks
    ]
    for result in results:
        result["policy_score"] = _episode_layout_quality(result)
    rewards = [float(item["reward_info"]["outcome_reward"]) for item in results]
    quality_scores = [float(item["policy_score"]) for item in results]
    successes = sum(1 for item in results if item["reward_info"]["details"]["outcome"] == "success")
    failure_counts = Counter(mode for item in results for mode in failure_modes_for_result(item))
    invalid_actions = sum(int(item["reward_info"]["details"].get("invalid_action_count", 0)) for item in results)
    if score_metric == "mean_layout_quality":
        score = round(statistics.mean(quality_scores), 6) if quality_scores else 0.0
    elif score_metric == "success_rate":
        score = round(successes / len(suite_tasks), 4) if suite_tasks else 0.0
    else:
        raise ValueError(f"unsupported Frogs policy score_metric: {score_metric}")
    report = {
        "schema": "gamebench.frogs.policy_sweep_summary.v1",
        "env_family": "frogs-singleplayer",
        "suite_id": str(suite["suite_id"]),
        "suite_path": str(suite_path),
        "policy_path": str(policy_path),
        "policy_sha256": policy_sha256(policy_path),
        "score_metric": score_metric,
        "seeds": [int(item["seed"]) for item in suite_tasks],
        "n_seeds": len(suite_tasks),
        "successes": successes,
        "success_rate": round(successes / len(suite_tasks), 4) if suite_tasks else 0.0,
        "score": score,
        "mean_layout_quality": round(statistics.mean(quality_scores), 6) if quality_scores else 0.0,
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
    parser = argparse.ArgumentParser(description="Run a FrogsGame code-policy sweep.")
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
    printable = {key: report[key] for key in ("suite_id", "success_rate", "mean_reward", "failure_mode_counts", "elapsed_s")}
    print(json.dumps(printable, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
