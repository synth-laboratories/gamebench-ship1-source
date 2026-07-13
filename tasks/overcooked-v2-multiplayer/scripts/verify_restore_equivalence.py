#!/usr/bin/env python3
"""Verify checkpoint restore preserves Overcooked v2 runtime state."""

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

from engine import OvercookedV2Engine
from scenarios import scenario_to_task
from task_resolve import resolve_task


def _runtime_snapshot(engine: OvercookedV2Engine) -> dict[str, Any]:
    readout = engine.symbolic_readout()
    return {
        "public": engine.public.to_dict(),
        "private": engine.private.to_dict(),
        "grid_hash": readout["grid_hash"],
        "joint_valid_actions": readout["joint_valid_actions"],
        "nev_cursor": engine.nev.cursor(),
    }


def _assert_equivalent(label: str, left: dict[str, Any], right: dict[str, Any]) -> None:
    if left != right:
        for key in sorted(set(left) | set(right)):
            if left.get(key) != right.get(key):
                raise AssertionError(f"{label}: mismatch at {key}: {left.get(key)!r} != {right.get(key)!r}")


def verify_immediate_restore(engine: OvercookedV2Engine) -> None:
    reference = _runtime_snapshot(engine)
    blob = engine.checkpoint_bytes()
    restored = OvercookedV2Engine()
    restored.restore_checkpoint(blob)
    _assert_equivalent("immediate_restore", reference, _runtime_snapshot(restored))


def verify_split_rollout(entry: dict[str, Any], *, split_after: int) -> None:
    joint_actions = list(entry.get("joint_actions", []))
    if split_after <= 0 or split_after > len(joint_actions):
        return
    reference = OvercookedV2Engine()
    reference.reset(resolve_task(scenario_to_task(entry), seed_override=entry.get("seed")))
    for joint in joint_actions:
        if reference.private.terminated or reference.private.truncated:
            break
        reference.step(joint)
    reference_snapshot = _runtime_snapshot(reference)

    split_engine = OvercookedV2Engine()
    split_engine.reset(resolve_task(scenario_to_task(entry), seed_override=entry.get("seed")))
    for joint in joint_actions[:split_after]:
        if split_engine.private.terminated or split_engine.private.truncated:
            break
        split_engine.step(joint)
    blob = split_engine.checkpoint_bytes()
    split_engine.restore_checkpoint(blob)
    for joint in joint_actions[split_after:]:
        if split_engine.private.terminated or split_engine.private.truncated:
            break
        split_engine.step(joint)
    _assert_equivalent(f"split_restore:{entry['scenario_id']}", reference_snapshot, _runtime_snapshot(split_engine))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios",
        default=str(TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json"),
    )
    args = parser.parse_args()
    scenarios = json.loads(Path(args.scenarios).read_text())["scenarios"]
    smoke = next(item for item in scenarios if item["scenario_id"] == "full_delivery_simple_soup")
    engine = OvercookedV2Engine()
    engine.reset(resolve_task(scenario_to_task(smoke), seed_override=smoke.get("seed")))
    for joint in smoke.get("joint_actions", []):
        if engine.private.terminated or engine.private.truncated:
            break
        engine.step(joint)
    verify_immediate_restore(engine)
    for entry in scenarios:
        if entry.get("joint_actions"):
            verify_split_rollout(entry, split_after=max(1, len(entry["joint_actions"]) // 2))
    print(f"Overcooked v2 restore verification OK ({len(scenarios)} scenarios)")


if __name__ == "__main__":
    main()
