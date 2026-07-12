#!/usr/bin/env python3
"""Run one prototype Rogue code-policy candidate on a fixed suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from copy import deepcopy
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


def suite_tasks(suite: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(suite.get("tasks"), list):
        tasks: list[dict[str, Any]] = []
        for index, raw in enumerate(suite["tasks"]):
            if not isinstance(raw, dict):
                raise ValueError(f"suite task {index} must be an object")
            task = deepcopy(raw)
            task.setdefault("task_id", f"{suite['suite_id']}_task_{index}")
            task.setdefault("seed", index + 1)
            if "grid" not in task:
                raise ValueError(f"suite task {task['task_id']} missing grid")
            tasks.append(task)
        return tasks

    task_path = str(suite.get("task_template", "tasks/policy_dev_template.json"))
    max_steps = int(suite.get("max_steps", 40))
    return [
        {
            "task_id": f"{suite['suite_id']}_seed_{int(seed)}",
            "seed": int(seed),
            "task_path": task_path,
            "max_steps": max_steps,
        }
        for seed in suite["seeds"]
    ]


def task_payload_for(task: dict[str, Any]) -> dict[str, Any]:
    if "grid" in task:
        return deepcopy(task)
    task_path = Path(str(task.get("task_path", "tasks/policy_dev_template.json")))
    resolved = task_path if task_path.is_absolute() else TASK_DIR / task_path
    payload = json.loads(resolved.read_text())
    payload["task_id"] = str(task["task_id"])
    payload["seed"] = int(task["seed"])
    return payload


def failure_modes_for_result(result: dict[str, Any]) -> list[str]:
    details = result["reward_info"]["details"]
    state = result["state"]
    public = state["public"]
    private = state["private"]
    if details["outcome"] == "success":
        return []
    modes: list[str] = []
    if int(details.get("invalid_action_count", 0)) > 0:
        modes.append("invalid_command")
    if private.get("terminal_reason") == "death" or int(private.get("hp", 1)) <= 0:
        modes.append("death")
    if int(private.get("dungeon_level", 1)) <= 1 and not private.get("terminated"):
        modes.append("no_descent")
    if int(private.get("step_index", 0)) <= 1:
        modes.append("no_progress")
    if public.get("visible_items"):
        modes.append("missed_pickup")
    if details["outcome"] == "truncated":
        modes.append("truncated")
    return modes or ["failed"]


def policy_score(report: dict[str, Any], *, metric: str) -> float:
    if metric == "mean_synth_shaped_reward":
        return float(report["mean_synth_shaped_reward"])
    if metric == "mean_scout_score":
        return float(report["mean_scout_score"])
    if metric == "success_rate":
        return float(report["success_rate"])
    raise ValueError(f"unsupported Rogue policy score metric: {metric}")


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
    tasks = suite_tasks(suite)
    score_metric = str(suite.get("score_metric", "success_rate"))
    results = [
        rollout_code_policy(
            policy_path=policy_path,
            seed=int(task["seed"]),
            task_path=str(task.get("task_path", "tasks/policy_dev_template.json")),
            task_payload=task_payload_for(task),
            max_steps=int(task.get("max_steps", 40)),
            include_trace=include_trace,
            candidate_fn=policy_fn,
        )
        for task in tasks
    ]
    rewards = [float(item["reward_info"]["outcome_reward"]) for item in results]
    scout_scores = [float(item["reward_info"]["details"].get("scout_score", 0.0)) for item in results]
    shaped_rewards = [float(item["reward_info"]["details"].get("synth_shaped_reward", 0.0)) for item in results]
    achievement_counts = Counter(name for item in results for name in item["reward_info"]["details"].get("achievement_names", []))
    achievement_frequencies = {name: round(count / len(results), 4) for name, count in sorted(achievement_counts.items())} if results else {}
    successes = sum(1 for item in results if item["reward_info"]["details"]["outcome"] == "success")
    invalid_actions = sum(int(item["reward_info"]["details"].get("invalid_action_count", 0)) for item in results)
    failure_counts = Counter(mode for item in results for mode in failure_modes_for_result(item))
    final_private = [item["state"]["private"] for item in results]
    report = {
        "schema": "gamebench.rogue.policy_sweep_summary.v1",
        "env_family": "rogue-singleplayer",
        "source_witnessed": True,
        "claim_status": "source_witnessed_1to1_gamebench_lane",
        "suite_id": str(suite["suite_id"]),
        "suite_path": str(suite_path),
        "score_metric": score_metric,
        "policy_path": str(policy_path),
        "policy_sha256": policy_sha256(policy_path),
        "seeds": [int(task["seed"]) for task in tasks],
        "task_ids": [str(task["task_id"]) for task in tasks],
        "n_seeds": len(tasks),
        "successes": successes,
        "success_rate": round(successes / len(tasks), 4) if tasks else 0.0,
        "mean_reward": round(statistics.mean(rewards), 4) if rewards else 0.0,
        "mean_scout_score": round(statistics.mean(scout_scores), 4) if scout_scores else 0.0,
        "mean_synth_shaped_reward": round(statistics.mean(shaped_rewards), 4) if shaped_rewards else 0.0,
        "achievement_name_counts": dict(sorted(achievement_counts.items())),
        "achievement_name_frequency": achievement_frequencies,
        "mean_dungeon_level": round(statistics.mean(float(item.get("dungeon_level", 1)) for item in final_private), 4) if final_private else 0.0,
        "mean_purse": round(statistics.mean(float(item.get("purse", 0)) for item in final_private), 4) if final_private else 0.0,
        "survival_rate": round(sum(1 for item in final_private if int(item.get("hp", 0)) > 0) / len(final_private), 4) if final_private else 0.0,
        "invalid_action_count": invalid_actions,
        "failure_mode_counts": dict(sorted(failure_counts.items())),
        "elapsed_s": round(time.time() - started, 3),
        "episodes": results,
    }
    report["score"] = round(policy_score(report, metric=score_metric), 4)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a prototype Rogue code-policy sweep.")
    parser.add_argument("--policy", default=str(TASK_DIR / "policies" / "heuristic_baseline.py"))
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v2.json"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--include-trace", action="store_true")
    args = parser.parse_args()

    report = run_policy_sweep(
        policy_path=Path(args.policy).expanduser().resolve(),
        suite_path=Path(args.suite).expanduser().resolve(),
        output_path=Path(args.output).expanduser().resolve(),
        include_trace=bool(args.include_trace),
    )
    printable = {key: report[key] for key in ("suite_id", "score_metric", "score", "success_rate", "mean_reward", "mean_scout_score", "mean_synth_shaped_reward", "failure_mode_counts", "elapsed_s")}
    print(json.dumps(printable, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
