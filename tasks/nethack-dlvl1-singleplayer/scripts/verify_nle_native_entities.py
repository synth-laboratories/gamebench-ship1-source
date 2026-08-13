#!/usr/bin/env python3
"""Held-out repeatability/noninterference probe for native NLE entity state."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import OBSERVATION_KEYS, deterministic_nle_seeds, normalise_reset, project
from scripts.nle_native_entities import PinnedNleEntityReader, validate_native_presentation


def _digest(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _new_env() -> Any:
    import nle
    from nle import nethack

    return nle.env.NLE(character="val-hum-fem-law", observation_keys=OBSERVATION_KEYS, actions=tuple(nethack.ACTIONS), allow_all_modes=True, allow_all_yn_questions=True)


def _run(seed: int) -> dict[str, Any]:
    env = _new_env()
    try:
        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        raw_reset = normalise_reset(env.reset())
        reset = project(raw_reset)
        reader = PinnedNleEntityReader(env.nethack)
        first = reader.snapshot().public_record()
        second = reader.snapshot().public_record()
        if first != second:
            raise AssertionError("read-only native entity export changed source state")
        # WAIT is intentionally an ordinary consumed turn: compare exact source
        # snapshots across independent identical source executions, never
        # infer a schedule from a single trace.
        wait_id = next(index for index, action in enumerate(env.actions) if action.__class__.__name__ == "MiscDirection" and action.name == "WAIT")
        presentation = validate_native_presentation(reader.snapshot(), raw_reset, __import__("nle").nethack)
        stepped, _, _, _ = env.step(wait_id)
        after = reader.snapshot().public_record()
        return {
            "seed": seed,
            "reset_public_sha256": _digest(reset),
            "before": first,
            "after_wait": after,
            "presentation_crosscheck": presentation,
            "noninterference": True,
        }
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20260725)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.cases < 3:
        raise SystemExit("native entity probe requires at least three held-out seeds")
    if sys.platform != "darwin":
        raise SystemExit("native entity probe requires the pinned macOS NLE wheel")
    first = [_run(args.seed + offset) for offset in range(args.cases)]
    second = [_run(args.seed + offset) for offset in range(args.cases)]
    if first != second:
        raise AssertionError("held-out native entity exports were not exactly repeatable across independent source runs")
    report = {
        "schema": "gamebench.nethack.native_entity_probe.v1",
        "status": "pass",
        "cases": first,
        "heldout_seed_count": len(first),
        "two_independent_runs_exact": True,
        "read_only_noninterference": True,
        "contract": "Native source snapshots are oracle evidence. They may not be replaced by glyph continuity, seed/coordinate schedules, or post-action state.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "pass", "cases": len(first), "report": str(args.report.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
