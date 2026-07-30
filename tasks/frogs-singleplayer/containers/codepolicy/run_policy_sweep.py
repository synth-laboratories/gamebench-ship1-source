#!/usr/bin/env python3
"""Run FrogsGame code-policy seed sweeps in-process."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[2]
if str(TASK_ROOT) not in sys.path:
    sys.path.insert(0, str(TASK_ROOT))

from containers.codepolicy.rollout_code_policy import compile_check_policy, load_policy_module, rollout_code_policy, task_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seeds", default="1,2,3,4")
    parser.add_argument("--policy-path", default="")
    parser.add_argument("--candidate-root", default="")
    parser.add_argument("--task-path", default="tasks/policy_dev_template.json")
    parser.add_argument("--max-steps", type=int, default=16)
    parser.add_argument("--include-trace", action="store_true")
    args = parser.parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    seeds = [int(part.strip()) for part in args.seeds.split(",") if part.strip()]
    candidates = _candidate_paths(Path(args.candidate_root).expanduser().resolve() if args.candidate_root else None, Path(args.policy_path).expanduser().resolve() if args.policy_path else None)
    if not candidates:
        raise SystemExit("no candidate policies found")
    summaries = []
    all_results = []
    started = time.time()
    for candidate_id, policy_path in candidates:
        compile_check_policy(policy_path)
        fn = load_policy_module(policy_path)
        c_started = time.time()
        results = [
            rollout_code_policy(
                policy_path=policy_path,
                seed=seed,
                task_path=args.task_path,
                max_steps=args.max_steps,
                include_trace=args.include_trace,
                candidate_fn=fn,
            )
            for seed in seeds
        ]
        for result in results:
            result["candidate_id"] = candidate_id
        summary = _summarize(results, elapsed_s=time.time() - c_started)
        summary.update({"candidate_id": candidate_id, "policy_path": str(policy_path)})
        summaries.append(summary)
        all_results.extend(results)
        candidate_dir = output_dir / "candidates" / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        (candidate_dir / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
        (candidate_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    best = max(summaries, key=lambda item: (item["success_rate"], item["mean_reward"]))
    report = {
        "schema_version": "gamebench.frogs.codepolicy_sweep.v1",
        "seeds": seeds,
        "task_path": args.task_path,
        "candidates": summaries,
        "best_candidate_id": best["candidate_id"],
        "elapsed_s": round(time.time() - started, 3),
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output_dir / "results.json").write_text(json.dumps(all_results, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


def _candidate_paths(candidate_root: Path | None, explicit: Path | None) -> list[tuple[str, Path]]:
    if explicit is not None:
        return [("baseline", explicit)]
    if candidate_root is None:
        return [("baseline", task_root() / "containers" / "codepolicy" / "heuristic_policy.py")]
    env_root = candidate_root / "frogs"
    search_root = env_root if env_root.is_dir() else candidate_root
    return [(path.parent.name, path) for path in sorted(search_root.glob("*/heuristic_policy.py"))]


def _summarize(results: list[dict], *, elapsed_s: float) -> dict:
    outcomes = [item["reward_info"]["details"]["outcome"] for item in results]
    rewards = [float(item["reward_info"]["outcome_reward"]) for item in results]
    invalid = sum(int(item["reward_info"]["details"].get("invalid_action_count", 0)) for item in results)
    n = len(results)
    successes = sum(1 for outcome in outcomes if outcome == "success")
    return {
        "schema_version": "gamebench.frogs.codepolicy_sweep.v1",
        "n_seeds": n,
        "successes": successes,
        "success_rate": round(successes / n, 4) if n else 0.0,
        "mean_reward": round(statistics.mean(rewards), 4) if rewards else 0.0,
        "invalid_action_count": invalid,
        "elapsed_s": round(elapsed_s, 3),
    }


if __name__ == "__main__":
    main()
