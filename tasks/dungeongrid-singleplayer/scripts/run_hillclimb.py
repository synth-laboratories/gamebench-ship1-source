#!/usr/bin/env python3
"""Rank DungeonGrid heuristic_policy candidates with train/heldout separation."""

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

from run_policy_sweep import load_suite, resolve_heldout_suite_path, run_policy_sweep


def candidate_paths(candidate_root: Path) -> list[tuple[str, Path]]:
    if not candidate_root.exists():
        return []
    env_root = candidate_root / "dungeongrid_singleplayer"
    search_root = env_root if env_root.is_dir() else candidate_root
    return [(path.parent.name, path) for path in sorted(search_root.glob("*/heuristic_policy.py"))]


def _row_from_reports(
    *,
    candidate_id: str,
    policy_path: Path,
    train_report: dict[str, Any],
    heldout_report: dict[str, Any] | None,
) -> dict[str, Any]:
    primary = heldout_report or train_report
    return {
        "candidate_id": candidate_id,
        "policy_path": str(policy_path),
        "policy_sha256": train_report["policy_sha256"],
        "score": float(primary["score"]),
        "score_metric": primary.get("score_metric", "mean_composite_score"),
        "success_rate": float(primary["success_rate"]),
        "mean_composite_score": float(primary.get("mean_composite_score", primary["score"])),
        "mean_objective_score": float(primary.get("mean_objective_score", primary["score"])),
        "mean_reward": float(primary["mean_reward"]),
        "mean_gold": float(primary.get("mean_gold", 0.0)),
        "mean_armor": float(primary.get("mean_armor", 0.0)),
        "mean_spells": float(primary.get("mean_spells", 0.0)),
        "mean_achievements": float(primary.get("mean_achievements", 0.0)),
        "mean_train_score": float(train_report["score"]),
        "mean_heldout_score": float(heldout_report["score"]) if heldout_report else None,
        "train_success_rate": float(train_report["success_rate"]),
        "heldout_success_rate": float(heldout_report["success_rate"]) if heldout_report else None,
        "invalid_action_count": int(primary["invalid_action_count"]),
        "failure_mode_counts": primary["failure_mode_counts"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DungeonGrid policy hillclimb leaderboard.")
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"))
    parser.add_argument("--heldout-suite", default="")
    parser.add_argument("--baseline", default=str(TASK_DIR / "policies" / "heuristic_baseline.py"))
    parser.add_argument("--candidate-root", default=str(TASK_DIR / "candidates"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--include-trace", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite).expanduser().resolve()
    suite = load_suite(suite_path)
    heldout_path: Path | None = None
    if args.heldout_suite:
        heldout_path = Path(args.heldout_suite).expanduser().resolve()
    else:
        heldout_path = resolve_heldout_suite_path(suite, suite_path)

    baseline_path = Path(args.baseline).expanduser().resolve()
    policies: list[tuple[str, Path]] = [("baseline", baseline_path)]
    policies.extend(candidate_paths(Path(args.candidate_root).expanduser().resolve()))
    if not policies:
        raise SystemExit("no policies found")

    rankings: list[dict[str, Any]] = []
    reports: dict[str, dict[str, Any]] = {}
    for candidate_id, policy_path in policies:
        candidate_dir = output / "candidates" / candidate_id
        train_report = run_policy_sweep(
            policy_path=policy_path,
            suite_path=suite_path,
            output_path=candidate_dir / "train_summary.json",
            include_trace=bool(args.include_trace),
        )
        (candidate_dir / "summary.json").write_text(
            json.dumps(train_report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        heldout_report = None
        if heldout_path is not None:
            heldout_report = run_policy_sweep(
                policy_path=policy_path,
                suite_path=heldout_path,
                output_path=candidate_dir / "heldout_summary.json",
                include_trace=bool(args.include_trace),
            )
        reports[candidate_id] = {
            "train": train_report,
            "heldout": heldout_report,
            "primary": heldout_report or train_report,
        }
        rankings.append(
            _row_from_reports(
                candidate_id=candidate_id,
                policy_path=policy_path,
                train_report=train_report,
                heldout_report=heldout_report,
            )
        )

    baseline_score = float(rankings[0]["score"]) if rankings and rankings[0]["candidate_id"] == "baseline" else float(
        next(r["score"] for r in rankings if r["candidate_id"] == "baseline")
    )
    rankings.sort(
        key=lambda item: (
            float(item["score"]),
            float(item.get("mean_train_score") or 0.0),
            float(item["success_rate"]),
            float(item["mean_reward"]),
        ),
        reverse=True,
    )
    best = rankings[0]
    best_dir = output / "best_policy"
    best_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(best["policy_path"]), best_dir / "heuristic_policy.py")
    primary_metric = (
        "mean_composite_heldout"
        if heldout_path is not None
        else str(reports["baseline"]["primary"].get("score_metric", "mean_composite_score"))
    )
    leaderboard = {
        "schema": "gamebench.hillclimb.v1",
        "env_family": "dungeongrid-singleplayer",
        "suite_id": reports["baseline"]["train"]["suite_id"],
        "heldout_suite_id": (
            reports["baseline"]["heldout"]["suite_id"] if reports["baseline"]["heldout"] else None
        ),
        "score_metric": primary_metric,
        "baseline_score": baseline_score,
        "best_score": float(best["score"]),
        "best_candidate_id": best["candidate_id"],
        "evaluated_policy_count": len(rankings),
        "train_n_scenarios": int(reports["baseline"]["train"]["n_scenarios"]),
        "heldout_n_scenarios": (
            int(reports["baseline"]["heldout"]["n_scenarios"]) if reports["baseline"]["heldout"] else 0
        ),
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
    (output / "leaderboard.json").write_text(json.dumps(leaderboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(leaderboard, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
