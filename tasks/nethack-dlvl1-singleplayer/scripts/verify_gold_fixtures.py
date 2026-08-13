#!/usr/bin/env python3
"""Verify both own gold lanes against checked-in GameBench expectations."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario
from scripts.trap_outcome_assertions import authored_trap_death_report


def subset_difference(expected: Any, actual: Any, path: str = "$") -> str | None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return f"{path}: expected object, got {type(actual).__name__}"
        for key, value in expected.items():
            if key not in actual:
                return f"{path}.{key}: missing"
            difference = subset_difference(value, actual[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return f"{path}: expected list length {len(expected)}, got {len(actual) if isinstance(actual, list) else type(actual).__name__}"
        for index, value in enumerate(expected):
            difference = subset_difference(value, actual[index], f"{path}[{index}]")
            if difference:
                return difference
        return None
    return None if expected == actual else f"{path}: expected {expected!r}, got {actual!r}"


def rust_scenario(entry: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario"],
        input=json.dumps(entry),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def main() -> None:
    state_expectations = json.loads((TASK_DIR / "fixtures" / "gold" / "states" / "states.json").read_text())["scenarios"]
    event_expectations = json.loads((TASK_DIR / "fixtures" / "gold" / "eventlogs" / "eventlogs.json").read_text())["scenarios"]
    failures: list[str] = []
    scenarios = sorted((TASK_DIR / "fixtures" / "gold" / "scenarios").glob("*.json"))
    for path in scenarios:
        entry = json.loads(path.read_text())
        scenario_id = entry["scenario_id"]
        expected = state_expectations.get(scenario_id, entry.get("expected", {}))
        required_kinds = event_expectations.get(scenario_id, entry.get("required_nev_kinds", []))
        for lane, result in (("python", run_scenario(entry)), ("rust", rust_scenario(entry))):
            difference = subset_difference(expected, result["readout"])
            if difference:
                failures.append(f"{path.name} {lane} state: {difference}")
                continue
            if scenario_id == "bootstrap_trap_death":
                trap_report = authored_trap_death_report(result, trap_id="fatal-pit", damage=14)
                if trap_report.get("status") != "pass":
                    failures.append(f"{path.name} {lane} trap lifecycle: {trap_report}")
            kinds = {event["kind"] for event in result["nev"]}
            missing = [kind for kind in required_kinds if kind not in kinds]
            if missing:
                failures.append(f"{path.name} {lane} missing NEV kinds {missing}")
    if failures:
        raise SystemExit("NetHack gold fixture verification FAILED\n" + "\n".join(failures))
    print(json.dumps({"status": "pass", "scenarios": [path.stem for path in scenarios], "lanes": ["python", "rust"]}, sort_keys=True))


if __name__ == "__main__":
    main()
