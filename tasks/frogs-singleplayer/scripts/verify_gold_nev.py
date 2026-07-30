#!/usr/bin/env python3
"""Verify FrogsGame gold NEV fixtures and lane parity."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scenarios import run_scenario


def run_rust(entry: dict[str, Any]) -> dict[str, Any]:
    proc = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--"],
        input=json.dumps(entry),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=["python", "rust", "both"], default="both")
    args = parser.parse_args()
    scenarios = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json").read_text())["scenarios"]
    failures: list[str] = []
    report: dict[str, Any] = {"schema": "gamebench.frogs.verify_nev.v1", "results": []}
    for entry in scenarios:
        expected: list[str] | None = None
        if args.lane in {"python", "both"}:
            py = run_scenario(entry)
            expected = py["events"]
            report["results"].append({"scenario_id": entry["scenario_id"], "lane": "python", "events": py["events"]})
        if args.lane in {"rust", "both"}:
            rs = run_rust(entry)
            report["results"].append({"scenario_id": entry["scenario_id"], "lane": "rust", "events": rs["events"]})
            if expected is not None and expected != rs["events"]:
                failures.append(entry["scenario_id"])
    print(json.dumps(report, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(f"NEV parity mismatch: {', '.join(failures)}")


if __name__ == "__main__":
    main()
