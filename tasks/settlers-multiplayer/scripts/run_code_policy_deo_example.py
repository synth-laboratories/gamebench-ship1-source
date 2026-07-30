#!/usr/bin/env python3
"""Run the checked-in Settlers DEO candidate without retaining report artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
CANDIDATE_ID = "vp_development_race_v1"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="gamebench-settlers-deo-") as temp_dir:
        output = Path(temp_dir)
        command = [
            sys.executable,
            str(TASK_DIR / "scripts" / "run_hillclimb.py"),
            "--suite",
            str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"),
            "--baseline",
            str(TASK_DIR / "containers" / "codepolicy" / "heuristic_policy.py"),
            "--candidate-root",
            str(TASK_DIR / "examples" / "code_policy_deo" / "candidates"),
            "--output",
            str(output),
        ]
        subprocess.run(command, check=True, cwd=TASK_DIR)
        leaderboard = json.loads((output / "leaderboard.json").read_text(encoding="utf-8"))

    baseline = float(leaderboard["baseline_score"])
    best = float(leaderboard["best_score"])
    delta = best - baseline
    if leaderboard["best_candidate_id"] != CANDIDATE_ID or delta < 0.01:
        raise SystemExit(
            f"expected {CANDIDATE_ID} to lead baseline by >= 0.01; "
            f"best={leaderboard['best_candidate_id']} delta={delta:.6f}"
        )
    print(
        json.dumps(
            {
                "baseline_score": baseline,
                "best_candidate_id": leaderboard["best_candidate_id"],
                "best_score": best,
                "delta_vs_baseline": round(delta, 6),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
