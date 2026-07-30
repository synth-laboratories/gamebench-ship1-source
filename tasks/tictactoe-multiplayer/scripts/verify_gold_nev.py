#!/usr/bin/env python3
"""Verify multiplayer gold NEV sequences against fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
SCENARIOS_PATH = TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json"
EVENTLOGS_PATH = TASK_DIR / "fixtures" / "gold" / "eventlogs" / "eventlogs.json"

if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from gold.scenarios import run_scenario, scenario_from_legacy


def main() -> None:
    scenarios_doc = json.loads(SCENARIOS_PATH.read_text())
    gold_doc = json.loads(EVENTLOGS_PATH.read_text())
    gold_by_id = {game["scenario_id"]: game["events"] for game in gold_doc["games"]}

    failures: list[str] = []
    for entry in scenarios_doc["scenarios"]:
        task = scenario_from_legacy(entry)
        result = run_scenario(task)
        expected = gold_by_id.get(entry["scenario_id"])
        if expected is None:
            failures.append(f"{entry['scenario_id']}: missing gold events")
            continue
        if result["events"] != expected:
            actual = result["events"]
            lines = []
            max_len = max(len(expected), len(actual))
            for index in range(max_len):
                exp = expected[index] if index < len(expected) else None
                act = actual[index] if index < len(actual) else None
                if exp != act:
                    lines.append(f"  [{index}] expected={exp!r} actual={act!r}")
            failures.append(f"{entry['scenario_id']}:\n" + "\n".join(lines))

    if failures:
        print("NEV gold verification FAILED")
        for failure in failures:
            print(failure)
        raise SystemExit(1)

    print(f"NEV gold verification OK ({len(scenarios_doc['scenarios'])} scenarios)")


if __name__ == "__main__":
    main()
