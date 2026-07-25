#!/usr/bin/env python3
"""Generate FrogsGame golden eventlog fixtures from scenarios."""

from __future__ import annotations

import json
import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scenarios import run_scenario


def main() -> None:
    scenarios = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json").read_text())["scenarios"]
    payload = {
        "schema": "gamebench.frogs.gold_eventlogs.v1",
        "scenarios": {
            entry["scenario_id"]: {
                "events": run_scenario(entry)["events"],
                "state": run_scenario(entry)["state"],
            }
            for entry in scenarios
        },
    }
    output = TASK_DIR / "fixtures" / "gold" / "eventlogs" / "eventlogs.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"written": str(output), "scenarios": len(scenarios)}, sort_keys=True))


if __name__ == "__main__":
    main()
