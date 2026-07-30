#!/usr/bin/env python3
"""Compare Python and Rust FrogsGame gold lanes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared", TASK_DIR / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from bench_checkpoint import bench_python, bench_rust
from engine import FrogsEngine
from scenarios import run_scenario, scenario_to_task
from task_resolve import resolve_task


def run_rust(entry: dict[str, Any]) -> dict[str, Any]:
    proc = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--"],
        input=json.dumps(entry),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def checkpoint_semantics_match() -> bool:
    entry = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json").read_text())["scenarios"][0]
    engine = FrogsEngine()
    engine.reset(resolve_task(scenario_to_task(entry)))
    for action in entry["actions"][:3]:
        engine.step(action)
    blob = engine.checkpoint_bytes()
    events_at_checkpoint = list(engine.nev.legacy_strings())
    engine.step({"kind": "place_frog", "row": 3, "col": 2})
    engine.restore_checkpoint(blob)
    if engine.nev.legacy_strings() != events_at_checkpoint:
        return False
    engine.step({"kind": "place_frog", "row": 3, "col": 2})
    restored_tail = list(engine.nev.legacy_strings())
    reference = FrogsEngine()
    reference.reset(resolve_task(scenario_to_task(entry)))
    for action in [*entry["actions"][:3], {"kind": "place_frog", "row": 3, "col": 2}]:
        reference.step(action)
    return restored_tail == reference.nev.legacy_strings()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parity-only", action="store_true")
    parser.add_argument("--checkpoint-iterations", type=int, default=300)
    parser.add_argument("--output", default=str(TASK_DIR / "reports" / "lane_compare.json"))
    args = parser.parse_args()
    scenarios = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json").read_text())["scenarios"]
    nev_mismatches = []
    symbolic_mismatches = []
    for entry in scenarios:
        py = run_scenario(entry)
        rs = run_rust(entry)
        if py["events"] != rs["events"]:
            nev_mismatches.append(entry["scenario_id"])
        if py["readout"]["grid_hash"] != rs["readout"]["grid_hash"] or py["readout"]["public"] != rs["readout"]["public"]:
            symbolic_mismatches.append(entry["scenario_id"])
    report: dict[str, Any] = {
        "schema": "gamebench.frogs.lane_compare.v1",
        "scenarios": [entry["scenario_id"] for entry in scenarios],
        "parity": {
            "nev_match": not nev_mismatches,
            "symbolic_match": not symbolic_mismatches,
            "checkpoint_semantics_match": checkpoint_semantics_match(),
            "nev_mismatches": nev_mismatches,
            "symbolic_mismatches": symbolic_mismatches,
        },
    }
    if not args.parity_only:
        report["python"] = bench_python(args.checkpoint_iterations)
        report["rust"] = bench_rust(args.checkpoint_iterations)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if nev_mismatches or symbolic_mismatches or not report["parity"]["checkpoint_semantics_match"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
