#!/usr/bin/env python3
"""Generate Overcooked v2 NEV fixture logs from scripted scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scenarios import run_scenario


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios",
        default=str(TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json"),
    )
    parser.add_argument(
        "--output",
        default=str(TASK_DIR / "fixtures" / "gold" / "eventlogs" / "eventlogs.json"),
    )
    args = parser.parse_args()
    scenarios = json.loads(Path(args.scenarios).read_text())["scenarios"]
    games = []
    for entry in scenarios:
        result = run_scenario(entry)
        games.append(
            {
                "scenario_id": entry["scenario_id"],
                "events": result["events"],
                "nev": result["nev"],
                "checkpoint_cursor": result["checkpoint_cursor"],
            }
        )
    output = {"schema": "gamebench.overcooked_v2.eventlogs.v1", "games": games}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(games)} Overcooked v2 eventlogs to {args.output}")


if __name__ == "__main__":
    main()
