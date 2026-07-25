#!/usr/bin/env python3
"""Rank Fog Duel Lite code-policy candidates on the fixed DEO suite."""

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
    """Accept either candidates/fogwar_duel/* or fogwar_duel/* directly."""
    if not candidate_root.exists():
        return []
    fogwar_root = candidate_root / "fogwar_duel"
    search_root = fogwar_root if fogwar_root.is_dir() else candidate_root
    return [
        (policy_path.parent.name, policy_path)
        for policy_path in sorted(search_root.glob("*/heuristic_policy.py"))
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Fog Duel Lite code-policy hillclimb.")
    parser.add_argument(
        "--suite",
        default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"),
    )
    parser.add_argument(
        "--baseline",
        default=str(TASK_DIR / "containers" / "codepolicy" / "heuristic_policy.py"),
    )
    parser.add_argument("--candidate-root", default=str(TASK_DIR / "candidates"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite).expanduser().resolve()
    policies: list[tuple[str, Path]] = [
        ("baseline", Path(args.baseline).expanduser().resolve())
    ]
    policies.extend(candidate_paths(Path(args.candidate_root).expanduser().resolve()))
    if len(policies) == 1:
        raise SystemExit("no Fogwar candidates found under candidate-root/fogwar_duel")

    rankings: list[dict[str, Any]] = []
    reports: dict[str, dict[str, Any]] = {}
    for candidate_id, policy_path in policies:
        report = run_policy_sweep(
            policy_path=policy_path,
            suite_path=suite_path,
            output_path=output / "candidates" / candidate_id / "summary.json",
        )
        reports[candidate_id] = report
        rankings.append(
            {
                "candidate_id": candidate_id,
                "policy_path": str(policy_path),
                "policy_sha256": report["policy_sha256"],
                "score": report["score"],
                "score_metric": report["score_metric"],
                "success_rate": report["success_rate"],
                "mean_terminal_reward": report["mean_terminal_reward"],
                "mean_reliability": report["mean_reliability"],
                "invalid_action_count": report["invalid_action_count"],
                "submitted_action_count": report["submitted_action_count"],
            }
        )

    baseline_score = float(reports["baseline"]["score"])
    rankings.sort(
        key=lambda item: (
            float(item["score"]),
            float(item["success_rate"]),
            float(item["mean_reliability"]),
        ),
        reverse=True,
    )
    best = rankings[0]
    best_dir = output / "best_policy"
    best_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(best["policy_path"]), best_dir / "heuristic_policy.py")
    leaderboard = {
        "schema": "gamebench.hillclimb.v1",
        "env_family": "fogwar-duel-multiplayer",
        "suite_id": reports["baseline"]["suite_id"],
        "score_metric": reports["baseline"]["score_metric"],
        "baseline_score": baseline_score,
        "best_score": float(best["score"]),
        "best_candidate_id": best["candidate_id"],
        "evaluated_policy_count": len(rankings),
        "rankings": [
            {
                **item,
                "delta_vs_baseline": round(float(item["score"]) - baseline_score, 6),
                "status": "accepted" if item["candidate_id"] == best["candidate_id"] else "rejected",
                "accepted": item["candidate_id"] == best["candidate_id"],
            }
            for item in rankings
        ],
    }
    (output / "leaderboard.json").write_text(
        json.dumps(leaderboard, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(leaderboard, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
