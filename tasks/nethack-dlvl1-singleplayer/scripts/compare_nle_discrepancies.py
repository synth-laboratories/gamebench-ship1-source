#!/usr/bin/env python3
"""Replay frozen NLE tapes against own gold and report the first divergence.

This script deliberately has no `nle` import: committed captures are sufficient
for minimal CI.  A live twin-step extension can be layered on top of this stable
frozen-corpus comparator.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from scripts.rust_scenario import run_scenario
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


def expected_nle_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Decode the raw public observation captured from NLE.

    Capture lifecycle fields live alongside ``projection`` in snapshots.  They
    normally describe the same point in the tape, except for the frozen
    ``dlvl1_descend`` boundary: that snapshot is intentionally the last
    dlvl-1 observation *before* NLE enters dlvl-2.
    """

    projection = dict(snapshot.get("projection", {}))
    inventory = dict(projection.get("inventory", {}))
    result = {
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
    }
    # Some pure own-engine property fixtures predate the public NLE specials
    # plane.  Its absence is not an all-zero NLE observation and must not
    # create a vacuous/incorrect comparison.
    if "specials" in projection:
        result["specials"] = projection["specials"]
    return result


def expected_public(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        **expected_nle_projection(snapshot),
        "done": bool(snapshot.get("done", False)),
        "terminal_reason": str(snapshot.get("terminal_reason", "")),
    }


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
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": str(meta.get("auto_more", "raw_explicit")), "vision_radius": 5},
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


def python_step_semantic_snapshots(task: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replay the full private gold state for cross-lane validity checks.

    The frozen NLE tape judges only the public observation against the oracle.
    This companion trace is deliberately gold-to-gold: it catches a Python /
    Rust hidden-state split even when both lanes happen to render identical
    chars, glyphs, and blstats at the same prefix.  It never consumes native
    state and it is not part of the public environment contract.
    """

    engine = NethackDlvl1Engine()
    engine.reset(resolve_task(task))
    snapshots = [engine.private_projection()]
    for record in actions:
        if engine.state["terminated"] or engine.state["truncated"]:
            break
        engine.step(int(record["action_id"]))
        snapshots.append(engine.private_projection())
    return snapshots


def rust_step_projections(task: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entry = {**task, "actions": [int(record["action_id"]) for record in actions]}
    return list(run_scenario(entry, ("--trace-stdin",))["snapshots"])


def rust_step_semantic_snapshots(task: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return Rust's private state trace emitted by the validity-only adapter."""

    entry = {**task, "actions": [int(record["action_id"]) for record in actions]}
    result = run_scenario(entry, ("--trace-stdin",))
    snapshots = result.get("semantic_snapshots")
    if not isinstance(snapshots, list):
        raise RuntimeError("Rust trace omitted semantic_snapshots")
    return snapshots


def is_dlvl1_descend(record: dict[str, Any]) -> bool:
    return str(record.get("boundary", "")) == "dlvl1_descend"


def descent_terminal_contract(projection: dict[str, Any]) -> dict[str, Any]:
    """The post-DOWN contract the dlvl-1 gold owns without an NLE dlvl-2 view."""

    return {
        "done": bool(projection.get("done", False)),
        "terminated": bool(projection.get("terminated", False)),
        "terminal_reason": str(projection.get("terminal_reason", "")),
    }


def compare_lane(
    fixture_dir: Path,
    lane: str,
    actions: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    projections: list[dict[str, Any]],
) -> list[str]:
    """Compare one replay lane, honoring the frozen pre-dlvl2 boundary.

    The trace contains reset followed by the public state after each applied
    action.  A frozen ``dlvl1_descend`` snapshot instead records NLE's state
    before the DOWN action, because the oracle is forbidden from entering
    dlvl-2.  Compare that snapshot at the pre-action trace index, then apply
    the gold DOWN action solely to check its owned terminal contract.
    """

    by_step = {int(snapshot["step"]): snapshot for snapshot in snapshots}
    failures: list[str] = []
    compared_steps: set[int] = set()

    initial = by_step.get(0)
    if initial is not None:
        if not projections:
            failures.append(f"{fixture_dir.name} {lane} step 0: gold trace is empty")
            return failures
        difference = first_difference(expected_public(initial), projections[0])
        if difference:
            failures.append(f"{fixture_dir.name} {lane} step 0: {difference}")
            return failures
        compared_steps.add(0)

    for action_index, record in enumerate(actions, start=1):
        step = int(record.get("step", action_index))
        snapshot = by_step.get(step)
        if snapshot is None:
            if is_dlvl1_descend(record):
                failures.append(f"{fixture_dir.name} {lane} step {step}: missing pre-descend NLE snapshot")
                break
            continue
        compared_steps.add(step)

        if is_dlvl1_descend(record):
            pre_action_index = action_index - 1
            if pre_action_index >= len(projections):
                failures.append(
                    f"{fixture_dir.name} {lane} step {step}: gold trace ended before the pre-descend state"
                )
                break
            difference = first_difference(expected_nle_projection(snapshot), projections[pre_action_index])
            if difference:
                failures.append(f"{fixture_dir.name} {lane} step {step} pre-descend: {difference}")
                break

            post_action_index = action_index
            if post_action_index >= len(projections):
                failures.append(
                    f"{fixture_dir.name} {lane} step {step}: gold trace ended before applying dlvl1 descent"
                )
                break
            difference = first_difference(
                {"done": True, "terminated": True, "terminal_reason": "descended"},
                descent_terminal_contract(projections[post_action_index]),
            )
            if difference:
                failures.append(f"{fixture_dir.name} {lane} step {step} descent terminal contract: {difference}")
                break
            continue

        projection_index = action_index
        if projection_index >= len(projections):
            failures.append(f"{fixture_dir.name} {lane} step {step}: gold trace ended after step {projection_index - 1}")
            break
        difference = first_difference(expected_public(snapshot), projections[projection_index])
        if difference:
            failures.append(f"{fixture_dir.name} {lane} step {step}: {difference}")
            break

    # Preserve comparison of any legacy snapshot that was not paired with an
    # action record.  Canonical capture tapes pair every post-reset snapshot.
    if not failures:
        for step in sorted(set(by_step) - compared_steps):
            if step >= len(projections):
                failures.append(f"{fixture_dir.name} {lane} step {step}: gold trace ended after step {len(projections) - 1}")
                break
            difference = first_difference(expected_public(by_step[step]), projections[step])
            if difference:
                failures.append(f"{fixture_dir.name} {lane} step {step}: {difference}")
                break
    return failures


def compare_fixture(fixture_dir: Path, lane: str) -> list[str]:
    task, actions, snapshots = fixture_task(fixture_dir)
    if lane == "python":
        projections = python_step_projections(task, actions)
    elif lane == "rust":
        projections = rust_step_projections(task, actions)
    else:
        raise ValueError(f"unsupported replay lane {lane!r}")
    return compare_lane(fixture_dir, lane, actions, snapshots, projections)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=("python", "rust", "both"), default="both")
    parser.add_argument("--fixture", action="append", default=[])
    parser.add_argument(
        "--root",
        type=Path,
        default=TASK_DIR / "fixtures" / "nle_oracle",
        help="Capture-root directory; permits replaying an out-of-tree fuzz artifact without copying it into the checked-in corpus.",
    )
    parser.add_argument("--require-fixtures", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    fixture_dirs = [root / fixture_id for fixture_id in args.fixture] if args.fixture else sorted(path.parent for path in root.rglob("meta.json"))
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
