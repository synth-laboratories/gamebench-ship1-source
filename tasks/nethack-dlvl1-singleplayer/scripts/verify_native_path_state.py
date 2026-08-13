#!/usr/bin/env python3
"""Replay-checked read-only audit of native target/path-state sidecar fields."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import OBSERVATION_KEYS, deterministic_nle_seeds, normalise_reset
from scripts.native_path_state_contract import validate_native_path_state
from scripts.nle_native_entities import PinnedNleEntityReader, validate_native_presentation


def _new_env() -> Any:
    import nle
    from nle import nethack

    return nle.env.NLE(
        character="val-hum-fem-law",
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )


def _action_id(env: Any, name: str) -> int:
    for index, action in enumerate(env.actions):
        if f"{action.__class__.__name__}.{action.name}" == name:
            return index
    raise AssertionError(f"pinned NLE action table lacks {name}")


def _run(seed: int) -> dict[str, Any]:
    import nle

    env = _new_env()
    try:
        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        reset = normalise_reset(env.reset())
        reader = PinnedNleEntityReader(env.nethack)
        before = reader.snapshot().public_record()
        # An immediate second copy is a noninterference check before input.
        if before != reader.snapshot().public_record():
            raise AssertionError("read-only target/path-state snapshot changed the native source")
        presentation = validate_native_presentation(reader.snapshot(), reset, nle.nethack)
        before_contract = validate_native_path_state(before)
        if before_contract["status"] != "pass":
            raise AssertionError(before_contract["issues"])
        env.step(_action_id(env, "Command.SEARCH"))
        after = reader.snapshot().public_record()
        after_contract = validate_native_path_state(after)
        if after_contract["status"] != "pass":
            raise AssertionError(after_contract["issues"])
        return {
            "seed": seed,
            "presentation_crosscheck": presentation,
            "before": before,
            "after_search": after,
            "before_contract": before_contract,
            "after_contract": after_contract,
            "read_only_noninterference": True,
        }
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20261201)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.cases < 3:
        raise SystemExit("native path-state audit needs at least three held-out seeds")
    first = [_run(args.seed + offset) for offset in range(args.cases)]
    second = [_run(args.seed + offset) for offset in range(args.cases)]
    if first != second:
        raise AssertionError("target/path-state sidecar was not exactly repeatable across independent same-seed runs")
    comparison_count = sum(
        case["before_contract"]["comparison_count"] + case["after_contract"]["comparison_count"]
        for case in first
    )
    if comparison_count <= 0:
        raise AssertionError("target/path-state audit has zero positive source comparisons")
    report = {
        "schema": "gamebench.nethack.native_path_state_probe.v1",
        "status": "pass_source_assertion_only",
        "heldout_seed_count": len(first),
        "two_independent_runs_exact": True,
        "comparison_count": comparison_count,
        "source_assertion_eligible": True,
        "gold_scheduler_pathing_eligible": False,
        "cases": first,
        "completeness_matrix": first[0]["before_contract"]["completeness_matrix"],
        "blocker": first[0]["before_contract"]["blocker"],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "cases": len(first),
                "comparison_count": comparison_count,
                "report": str(args.report.resolve()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
