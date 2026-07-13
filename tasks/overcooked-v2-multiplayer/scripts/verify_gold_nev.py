#!/usr/bin/env python3
"""Verify Overcooked v2 gold NEV fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


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
        "--eventlogs",
        default=str(TASK_DIR / "fixtures" / "gold" / "eventlogs" / "eventlogs.json"),
    )
    args = parser.parse_args()
    scenarios = json.loads(Path(args.scenarios).read_text())["scenarios"]
    gold_doc = json.loads(Path(args.eventlogs).read_text())
    gold_by_id = {item["scenario_id"]: item for item in gold_doc["games"]}
    failures: list[str] = []
    for entry in scenarios:
        result = run_scenario(entry)
        expected = gold_by_id.get(entry["scenario_id"])
        if expected is None:
            failures.append(f"{entry['scenario_id']}: missing gold events")
            continue
        if result["events"] != expected.get("events"):
            failures.append(_diff(entry["scenario_id"], expected.get("events", []), result["events"], "events"))
        if result["nev"] != expected.get("nev"):
            failures.append(_diff(entry["scenario_id"], expected.get("nev", []), result["nev"], "nev"))
    if failures:
        print("Overcooked v2 NEV verification FAILED")
        print("\n".join(failures))
        raise SystemExit(1)
    print(f"Overcooked v2 NEV verification OK ({len(scenarios)} scenarios)")


def _diff(scenario_id: str, expected: list[Any], actual: list[Any], label: str) -> str:
    lines = [f"{scenario_id} {label}:"]
    for index in range(max(len(expected), len(actual))):
        exp = expected[index] if index < len(expected) else None
        act = actual[index] if index < len(actual) else None
        if exp != act:
            lines.append(f"  [{index}] expected={exp!r} actual={act!r}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
