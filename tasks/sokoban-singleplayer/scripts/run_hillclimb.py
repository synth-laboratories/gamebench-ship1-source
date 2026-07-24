#!/usr/bin/env python3
"""Rank Sokoban heuristic_policy candidates on a fixed suite (python or rust lane)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared", TASK_DIR / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_policy_sweep import run_policy_sweep


def candidate_paths(candidate_root: Path) -> list[tuple[str, Path]]:
    if not candidate_root.exists():
        return []
    env_root = candidate_root / "sokoban"
    search_root = env_root if env_root.is_dir() else candidate_root
    return [(path.parent.name, path) for path in sorted(search_root.glob("*/heuristic_policy.py"))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Sokoban policy hillclimb leaderboard.")
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"))
    parser.add_argument("--baseline", default=str(TASK_DIR / "containers" / "codepolicy" / "heuristic_policy.py"))
    parser.add_argument("--candidate-root", default=str(TASK_DIR / "candidates"))
    parser.add_argument("--engine-lane", choices=["python", "rust"], default="python")
    parser.add_argument("--service-url", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--include-trace", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite).expanduser().resolve()
    baseline_path = Path(args.baseline).expanduser().resolve()
    candidates: list[tuple[str, Path]] = [("baseline", baseline_path)]
    candidates.extend(candidate_paths(Path(args.candidate_root).expanduser().resolve()))
    if not candidates:
        raise SystemExit("no policies found")

    rankings: list[dict[str, Any]] = []
    reports: dict[str, dict[str, Any]] = {}
    for candidate_id, policy_path in candidates:
        candidate_dir = output / "candidates" / candidate_id
        report = run_policy_sweep(
            policy_path=policy_path,
            suite_path=suite_path,
            output_path=candidate_dir / "summary.json",
            engine_lane=args.engine_lane,
            service_url=args.service_url or None,
            workers=max(1, int(args.workers)),
            include_trace=bool(args.include_trace),
        )
        reports[candidate_id] = report
        rankings.append(
            {
                "candidate_id": candidate_id,
                "policy_path": str(policy_path),
                "policy_sha256": report["policy_sha256"],
                "engine_lane": report["engine_lane"],
                "score": report["score"],
                "success_rate": report["success_rate"],
                "mean_reward": report["mean_reward"],
                "milestone_frequency": report["milestone_frequency"],
                "failure_mode_counts": report["failure_mode_counts"],
            }
        )

    baseline_score = reports["baseline"]["score"]
    rankings.sort(key=lambda item: (float(item["score"]), float(item["success_rate"]), float(item["mean_reward"])), reverse=True)
    best = rankings[0]
    best_dir = output / "best_policy"
    best_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(best["policy_path"]), best_dir / "heuristic_policy.py")
    leaderboard = {
        "schema": "gamebench.hillclimb.v1",
        "env_family": "sokoban-singleplayer",
        "engine_lane": args.engine_lane,
        "suite_id": reports["baseline"]["suite_id"],
        "baseline_score": baseline_score,
        "best_score": best["score"],
        "best_candidate_id": best["candidate_id"],
        "evaluated_policy_count": len(rankings),
        "rankings": [
            {
                **item,
                "delta_vs_baseline": float(item["score"]) - float(baseline_score),
                "status": "accepted" if item["candidate_id"] == best["candidate_id"] else "rejected",
                "accepted": item["candidate_id"] == best["candidate_id"],
            }
            for item in rankings
        ],
    }
    (output / "leaderboard.json").write_text(json.dumps(leaderboard, indent=2, sort_keys=True) + "\n")
    print(json.dumps(leaderboard, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
