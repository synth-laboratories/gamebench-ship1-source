#!/usr/bin/env python3
"""Run policy puzzle rollouts for tictactoe-multiplayer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ENV_ROOT = Path(__file__).resolve().parents[1]
GAMEBENCH_ROOT = Path(__file__).resolve().parents[3]
RUNNER = GAMEBENCH_ROOT / "shared" / "policy_puzzle" / "run_policy_puzzle_rollout.py"


def main() -> int:
    puzzle = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    puzzles = [puzzle] if puzzle else sorted((ENV_ROOT / "policy_puzzles" / "tasks").glob("puzzle_*_v1.json"))
    rc = 0
    for path in puzzles:
        proc = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--env-root",
                str(ENV_ROOT),
                "--env-kind",
                "tictactoe_mp",
                "--puzzle",
                str(path),
            ]
        )
        rc = rc or proc.returncode
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
