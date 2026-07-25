#!/usr/bin/env python3
"""Run the checked-in ALEM DEO baseline and candidate without writing task reports."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"
DEFAULT_BASELINE = TASK_DIR / "containers" / "codepolicy" / "heuristic_policy.py"
DEFAULT_CANDIDATES = TASK_DIR / "examples" / "code_policy_deo" / "candidates"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the checked-in ALEM DEO example.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Directory for generated leaderboard artifacts; defaults to a new temporary directory.",
    )
    parser.add_argument("--pass-delta", type=float, default=0.01)
    args = parser.parse_args()

    output = args.output.expanduser().resolve() if args.output else Path(
        tempfile.mkdtemp(prefix="gamebench-alem-deo-")
    )
    command = [
        sys.executable,
        str(TASK_DIR / "scripts" / "run_hillclimb.py"),
        "--suite",
        str(DEFAULT_SUITE),
        "--baseline",
        str(DEFAULT_BASELINE),
        "--candidate-root",
        str(DEFAULT_CANDIDATES),
        "--output",
        str(output),
    ]
    subprocess.run(command, check=True, cwd=TASK_DIR)
    leaderboard = json.loads((output / "leaderboard.json").read_text(encoding="utf-8"))
    baseline = float(leaderboard["baseline_score"])
    best = float(leaderboard["best_score"])
    delta = best - baseline
    best_candidate_id = str(leaderboard["best_candidate_id"])
    if best_candidate_id == "baseline" or delta < args.pass_delta:
        raise SystemExit(
            f"ALEM DEO example did not beat baseline by {args.pass_delta:.2f}: "
            f"best={best:.6f} baseline={baseline:.6f} delta={delta:.6f}"
        )
    print(
        json.dumps(
            {
                "status": "pass",
                "output": str(output),
                "best_candidate_id": best_candidate_id,
                "baseline_score": baseline,
                "best_score": best,
                "delta_vs_baseline": delta,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
