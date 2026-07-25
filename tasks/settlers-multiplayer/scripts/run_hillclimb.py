#!/usr/bin/env python3
"""Rank Settlers code-policy candidates on the fixed four-player DEO suite."""

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
    """Resolve Harbor's candidates/settlers/<id>/heuristic_policy.py contract."""

    if not candidate_root.exists():
        return []
    settlers_root = candidate_root / "settlers"
    search_root = settlers_root if settlers_root.is_dir() else candidate_root
    return [(path.parent.name, path) for path in sorted(search_root.glob("*/heuristic_policy.py"))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Settlers code-policy DEO hillclimb leaderboard.")
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"))
    parser.add_argument("--baseline", default=str(TASK_DIR / "containers" / "codepolicy" / "heuristic_policy.py"))
    parser.add_argument("--candidate-root", default=str(TASK_DIR / "candidates"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--include-trace", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite).expanduser().resolve()
    baseline_path = Path(args.baseline).expanduser().resolve()
    policies: list[tuple[str, Path]] = [("baseline", baseline_path)]
    policies.extend(candidate_paths(Path(args.candidate_root).expanduser().resolve()))

    rankings: list[dict[str, Any]] = []
    reports: dict[str, dict[str, Any]] = {}
    for candidate_id, policy_path in policies:
        report = run_policy_sweep(
            policy_path=policy_path,
            suite_path=suite_path,
            output_path=output / "candidates" / candidate_id / "summary.json",
            include_trace=bool(args.include_trace),
        )
        reports[candidate_id] = report
        rankings.append(
            {
                "candidate_id": candidate_id,
                "policy_path": str(policy_path),
                "policy_sha256": report["policy_sha256"],
                "score": report["score"],
                "win_rate": report["win_rate"],
                "mean_candidate_vp": report["mean_candidate_vp"],
                "mean_best_opponent_vp": report["mean_best_opponent_vp"],
                "invalid_action_count": report["invalid_action_count"],
                "policy_failure_count": report["policy_failure_count"],
            }
        )

    baseline_score = float(reports["baseline"]["score"])
    rankings.sort(
        key=lambda row: (float(row["score"]), float(row["win_rate"]), float(row["mean_candidate_vp"])),
        reverse=True,
    )
    best = rankings[0]
    best_dir = output / "best_policy"
    best_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(best["policy_path"]), best_dir / "heuristic_policy.py")
    leaderboard = {
        "schema": "gamebench.hillclimb.v1",
        "env_family": "settlers-multiplayer",
        "suite_id": reports["baseline"]["suite_id"],
        "candidate_agent": reports["baseline"]["candidate_agent"],
        "opponent_policy": reports["baseline"]["opponent_policy"],
        "turn_model": reports["baseline"]["turn_model"],
        "score_metric": reports["baseline"]["score_metric"],
        "baseline_score": baseline_score,
        "best_score": float(best["score"]),
        "best_candidate_id": best["candidate_id"],
        "evaluated_policy_count": len(rankings),
        "rankings": [
            {
                **row,
                "delta_vs_baseline": round(float(row["score"]) - baseline_score, 6),
                "status": "accepted" if row["candidate_id"] == best["candidate_id"] else "rejected",
                "accepted": row["candidate_id"] == best["candidate_id"],
            }
            for row in rankings
        ],
    }
    (output / "leaderboard.json").write_text(
        json.dumps(leaderboard, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(leaderboard, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
