#!/usr/bin/env python3
"""Stage the checked-in Fogwar candidate and run Harbor DEO end to end.

All generated candidates, reports, and verifier output are placed under the
caller-supplied output root.  The tracked candidate source is never modified.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_DIR.parents[1]
GENERIC_RUNNER = (
    REPO_ROOT
    / "adapters"
    / "harbor"
    / "bundles"
    / "code_policy_deo_hillclimb"
    / "files"
    / "run_gamebench_hillclimb_task.py"
)
CANDIDATE_SOURCE = (
    TASK_DIR
    / "examples"
    / "code_policy_deo"
    / "candidates"
    / "fogwar_duel"
    / "tactical_observation_v1"
    / "heuristic_policy.py"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Fogwar Harbor DEO example.")
    parser.add_argument(
        "--output-root",
        required=True,
        help="External output directory; do not point it at the tracked checkout.",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root).expanduser().resolve()
    if output_root == REPO_ROOT or REPO_ROOT in output_root.parents:
        raise SystemExit("--output-root must be outside the tracked gamebench checkout")
    staged_policy = (
        output_root
        / "candidates"
        / "fogwar_duel"
        / "tactical_observation_v1"
        / "heuristic_policy.py"
    )
    staged_policy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CANDIDATE_SOURCE, staged_policy)

    env = dict(os.environ)
    env.update(
        {
            "GAMEBENCH_ROOT": str(REPO_ROOT),
            "GAMEBENCH_TASK": "fogwar-duel-multiplayer",
            "CANDIDATE_SUBDIR": "fogwar_duel",
        }
    )
    commands = (
        (
            "run",
            "--output-root",
            str(output_root),
            "--candidate-root",
            "candidates",
        ),
        ("score", "--output-root", str(output_root)),
    )
    for command in commands:
        subprocess.run(
            [
                sys.executable,
                str(GENERIC_RUNNER),
                *command,
            ],
            check=True,
            cwd=str(REPO_ROOT),
            env=env,
        )

    leaderboard_path = output_root / "artifacts" / "gamebench_hillclimb" / "leaderboard.json"
    leaderboard = json.loads(leaderboard_path.read_text(encoding="utf-8"))
    delta = float(leaderboard["best_score"]) - float(leaderboard["baseline_score"])
    if leaderboard["best_candidate_id"] == "baseline" or delta < 0.01:
        raise SystemExit("Fogwar candidate did not beat the baseline by >= 0.01")
    print(
        json.dumps(
            {
                "baseline_score": leaderboard["baseline_score"],
                "best_candidate_id": leaderboard["best_candidate_id"],
                "best_score": leaderboard["best_score"],
                "delta_vs_baseline": delta,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
