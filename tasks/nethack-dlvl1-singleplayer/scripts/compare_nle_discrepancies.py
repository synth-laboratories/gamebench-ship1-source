#!/usr/bin/env python3
"""Replay frozen NLE tapes against own gold and report the first divergence.

This script deliberately has no `nle` import: committed captures are sufficient
for minimal CI.  A live twin-step extension can be layered on top of this stable
frozen-corpus comparator.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from shared.task_resolve import resolve_task


def first_difference(expected: Any, actual: Any, path: str = "$") -> str | None:
    if type(expected) is not type(actual):
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)) and expected == actual:
            return None
        return f"{path}: expected {type(expected).__name__} {expected!r}, got {type(actual).__name__} {actual!r}"
    if isinstance(expected, dict):
        for key in sorted(expected):
            if key not in actual:
                return f"{path}.{key}: missing from gold"
            difference = first_difference(expected[key], actual[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: expected length {len(expected)}, got {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            difference = first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
        return None
    return None if expected == actual else f"{path}: expected {expected!r}, got {actual!r}"


def decode_chars(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    output: list[str] = []
    for row in rows:
        if isinstance(row, str):
            output.append(row)
        elif isinstance(row, list):
            output.append("".join(chr(int(cell)) for cell in row))
        else:
            output.append("")
    return output


def decode_inventory_strings(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    result: list[str] = []
    for row in rows:
        if isinstance(row, str):
            result.append(row)
        elif isinstance(row, list):
            result.append(bytes(int(cell) for cell in row).split(b"\0", 1)[0].decode("utf-8", errors="replace"))
        else:
            result.append("")
    return result


def expected_public(snapshot: dict[str, Any]) -> dict[str, Any]:
    projection = dict(snapshot.get("projection", {}))
    inventory = dict(projection.get("inventory", {}))
    expected = {
        "chars": decode_chars(projection.get("chars", [])),
        "colors": projection.get("colors", []),
        "glyphs": projection.get("glyphs", []),
        "blstats": projection.get("blstats", []),
        "message": str(projection.get("message", "")),
        "message_raw": list(projection.get("message_raw", [])),
        "inventory": {
            "inv_letters": inventory.get("inv_letters", []),
            "inv_glyphs": inventory.get("inv_glyphs", []),
            "inv_oclasses": inventory.get("inv_oclasses", []),
            "inv_strs": decode_inventory_strings(inventory.get("inv_strs", [])),
        },
        "done": bool(snapshot.get("done", False)),
        "terminal_reason": str(snapshot.get("terminal_reason", "")),
    }
    return expected


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fixture_task(fixture_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    meta = json.loads((fixture_dir / "meta.json").read_text())
    level_dump = json.loads((fixture_dir / "level_dump.json").read_text())
    actions = load_jsonl(fixture_dir / "actions.jsonl")
    snapshots = load_jsonl(fixture_dir / "snapshots.jsonl")
    task = {
        "task_id": str(meta.get("fixture_id", fixture_dir.name)),
        "seed": int(meta.get("seed", 0)),
        "character": dict(meta.get("character", {})),
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": str(meta.get("auto_more", "raw_explicit")), "vision_radius": 4},
        "level_dump": level_dump,
    }
    return task, actions, snapshots


def python_step_projections(task: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    engine = NethackDlvl1Engine()
    engine.reset(resolve_task(task))
    projections = [engine.public_projection()]
    for record in actions:
        if engine.state["terminated"] or engine.state["truncated"]:
            break
        engine.step(int(record["action_id"]))
        projections.append(engine.public_projection())
    return projections


def rust_projection(task: dict[str, Any], action_prefix: list[int]) -> dict[str, Any]:
    entry = {**task, "actions": action_prefix}
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario"],
        input=json.dumps(entry),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)["readout"]["public"]


def compare_fixture(fixture_dir: Path, lane: str) -> list[str]:
    task, actions, snapshots = fixture_task(fixture_dir)
    by_step = {int(snapshot["step"]): snapshot for snapshot in snapshots}
    failures: list[str] = []
    if lane == "python":
        projections = python_step_projections(task, actions)
        for step, actual in enumerate(projections):
            if step not in by_step:
                continue
            difference = first_difference(expected_public(by_step[step]), actual)
            if difference:
                failures.append(f"{fixture_dir.name} python step {step}: {difference}")
                break
    else:
        prefix: list[int] = []
        for step in range(len(actions) + 1):
            if step in by_step:
                actual = rust_projection(task, prefix)
                difference = first_difference(expected_public(by_step[step]), actual)
                if difference:
                    failures.append(f"{fixture_dir.name} rust step {step}: {difference}")
                    break
            if step < len(actions):
                prefix.append(int(actions[step]["action_id"]))
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=("python", "rust", "both"), default="both")
    parser.add_argument("--fixture", action="append", default=[])
    parser.add_argument("--require-fixtures", action="store_true")
    args = parser.parse_args()
    root = TASK_DIR / "fixtures" / "nle_oracle"
    fixture_dirs = [root / fixture_id for fixture_id in args.fixture] if args.fixture else sorted(path.parent for path in root.glob("*/meta.json"))
    if not fixture_dirs:
        if args.require_fixtures:
            raise SystemExit("No authentic frozen NLE captures are present. Run capture_nle_fixture.py in an nle==0.9.0 dev environment.")
        print(json.dumps({"status": "no_fixtures", "oracle": str(root)}, sort_keys=True))
        return
    failures: list[str] = []
    lanes = ("python", "rust") if args.lane == "both" else (args.lane,)
    for fixture_dir in fixture_dirs:
        for lane in lanes:
            failures.extend(compare_fixture(fixture_dir, lane))
    if failures:
        raise SystemExit("NLE discrepancy FAILED\n" + "\n".join(failures))
    print(json.dumps({"status": "pass", "fixtures": [path.name for path in fixture_dirs], "lanes": lanes}, sort_keys=True))


if __name__ == "__main__":
    main()
