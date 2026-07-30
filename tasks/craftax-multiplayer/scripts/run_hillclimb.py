#!/usr/bin/env python3
"""Rank Craftax-Coop ALEM coordination code-policy candidates on a fixed suite."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
CANDIDATE_SUBDIR = "craftax_coop"
sys.path.insert(0, str(TASK_DIR / "scripts"))

from run_policy_sweep import run_policy_sweep


def candidate_paths(candidate_root: Path) -> list[tuple[str, Path]]:
    """Discover only the Harbor ``craftax_coop`` candidate namespace.

    Harbor normally passes ``.../candidates/craftax_coop`` directly. Local
    examples can instead pass its parent directory. Keeping both forms makes
    the task runner useful locally without ever scoring another task's files.
    """
    if candidate_root.name == CANDIDATE_SUBDIR:
        search_root = candidate_root
    else:
        search_root = candidate_root / CANDIDATE_SUBDIR
    if not search_root.is_dir():
        return []
    return [
        (path.parent.name, path)
        for path in sorted(search_root.glob("*/heuristic_policy.py"))
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Craftax-Coop ALEM code-policy hillclimb.")
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
    parser.add_argument("--include-trace", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite).expanduser().resolve()
    policies: list[tuple[str, Path]] = [
        ("baseline", Path(args.baseline).expanduser().resolve())
    ]
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
                "mean_coord_reward": report["mean_coord_reward"],
                "mean_coord_reward_ratio": report["mean_coord_reward_ratio"],
                "coord_success_rate": report["mean_coord_success_rate"],
                "illegal_action_reliability": report["illegal_action_reliability"],
                "invalid_action_count": report["invalid_action_count"],
                "failure_mode_counts": report["failure_mode_counts"],
            }
        )

    baseline_score = float(reports["baseline"]["score"])
    rankings.sort(
        key=lambda row: (
            float(row["score"]),
            float(row["mean_coord_reward"]),
            float(row["coord_success_rate"]),
        ),
        reverse=True,
    )
    best = rankings[0]
    best_dir = output / "best_policy"
    best_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(best["policy_path"]), best_dir / "heuristic_policy.py")
    leaderboard = {
        "schema": "gamebench.hillclimb.v1",
        "env_family": "craftax-multiplayer",
        "rules_profile": "alem_coord_v0",
        "candidate_subdir": CANDIDATE_SUBDIR,
        "agents": reports["baseline"]["agents"],
        "roles": reports["baseline"]["roles"],
        "reward_semantics": reports["baseline"]["reward_semantics"],
        "suite_id": reports["baseline"]["suite_id"],
        "score_metric": reports["baseline"]["score_metric"],
        "score_weights": reports["baseline"]["score_weights"],
        "baseline_score": baseline_score,
        "best_score": float(best["score"]),
        "best_candidate_id": best["candidate_id"],
        "evaluated_policy_count": len(rankings),
        "rankings": [
            {
                **item,
                "delta_vs_baseline": float(item["score"]) - baseline_score,
                "status": "accepted" if item["candidate_id"] == best["candidate_id"] else "rejected",
                "accepted": item["candidate_id"] == best["candidate_id"],
            }
            for item in rankings
        ],
    }
    (output / "leaderboard.json").write_text(
        json.dumps(leaderboard, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(leaderboard, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
