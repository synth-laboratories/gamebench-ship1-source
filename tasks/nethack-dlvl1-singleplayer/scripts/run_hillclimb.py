#!/usr/bin/env python3
"""Small deterministic baseline runner; not a reduced action API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=Path, default=TASK_DIR / "fixtures" / "gold" / "scenarios" / "bootstrap_descend.json")
    args = parser.parse_args()
    from gold_python.scenarios import run_scenario

    entry = json.loads(args.scenario.read_text())
    # Scenario tapes remain wire-level NLE actions.  A future policy optimizer may
    # replace this tape, but does not get a separate toy movement interface.
    print(json.dumps({"policy": "tape_baseline", "result": run_scenario(entry)}, sort_keys=True))


if __name__ == "__main__":
    main()
