#!/usr/bin/env python3
"""Replay one scenario through a selected own gold lane."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=("python", "rust"), default="python")
    parser.add_argument("--scenario", type=Path, required=True)
    args = parser.parse_args()
    entry = json.loads(args.scenario.read_text())
    if args.lane == "python":
        from gold_python.scenarios import run_scenario

        result = run_scenario(entry)
    else:
        result = json.loads(
            subprocess.run(
                ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario"],
                input=json.dumps(entry),
                text=True,
                check=True,
                capture_output=True,
            ).stdout
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
