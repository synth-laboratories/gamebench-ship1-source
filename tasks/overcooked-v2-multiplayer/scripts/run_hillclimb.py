#!/usr/bin/env python3
"""Rank Overcooked v2 heuristic_policy candidates on a fixed suite."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
if str(TASK_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(TASK_DIR / "scripts"))

from run_policy_sweep import run_policy_sweep


def candidate_paths(candidate_root: Path) -> list[tuple[str, Path]]:
    if not candidate_root.exists():
        return []
    env_root = candidate_root / "overcooked_v2"
    search_root = env_root if env_root.is_dir() else candidate_root
    return [(path.parent.name, path) for path in sorted(search_root.glob("*/heuristic_policy.py"))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Overcooked v2 policy hillclimb leaderboard.")
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"))
    parser.add_argument("--baseline", default=str(TASK_DIR / "policies" / "heuristic_baseline.py"))
    parser.add_argument("--candidate-root", default=str(TASK_DIR / "candidates"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--include-trace", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    policies: list[tuple[str, Path]] = [("baseline", Path(args.baseline).expanduser().resolve())]
    policies.extend(candidate_paths(Path(args.candidate_root).expanduser().resolve()))
    rankings: list[dict[str, Any]] = []
    reports: dict[str, dict[str, Any]] = {}
    for candidate_id, policy_path in policies:
        candidate_dir = output / "candidates" / candidate_id
        report = run_policy_sweep(
            policy_path=policy_path,
            suite_path=Path(args.suite).expanduser().resolve(),
            output_path=candidate_dir / "summary.json",
            include_trace=bool(args.include_trace),
        )
        reports[candidate_id] = report
        rankings.append(
            {
                "candidate_id": candidate_id,
                "policy_path": str(policy_path),
                "policy_sha256": report["policy_sha256"],
                "score": report["score"],
                "success_rate": report["success_rate"],
                "mean_reward": report["mean_reward"],
                "invalid_action_count": report["invalid_action_count"],
                "failure_mode_counts": report["failure_mode_counts"],
            }
        )
    baseline_score = float(reports["baseline"]["score"])
    rankings.sort(key=lambda item: (float(item["score"]), float(item["mean_reward"])), reverse=True)
    best = rankings[0]
    best_dir = output / "best_policy"
    best_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(best["policy_path"]), best_dir / "heuristic_policy.py")
    leaderboard = {
        "schema": "gamebench.hillclimb.v1",
        "env_family": "overcooked-v2-multiplayer",
        "suite_id": reports["baseline"]["suite_id"],
        "baseline_score": baseline_score,
        "best_score": float(best["score"]),
        "best_candidate_id": best["candidate_id"],
        "evaluated_policy_count": len(rankings),
        "rankings": rankings,
    }
    output.joinpath("leaderboard.json").write_text(json.dumps(leaderboard, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"best_candidate_id": best["candidate_id"], "best_score": best["score"], "baseline_score": baseline_score}, indent=2))


if __name__ == "__main__":
    main()
