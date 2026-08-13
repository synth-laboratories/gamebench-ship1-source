#!/usr/bin/env python3
"""Verify the narrow reset actor stationary presentation contract.

The pinned native ``movemon`` boundary exposes a useful, deliberately small
fact: a visible monster whose reset ``movement_points`` is below
``NORMAL_SPEED`` does not move across the first consumed stationary
``SEARCH``/``WAIT``/``TAKEOFF`` action.  This verifier records only reset state and the
immediate post-action native state.  It does not export a destination,
pathing decision, combat result, or later scheduler state to gold.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import OBSERVATION_KEYS, deterministic_nle_seeds, normalise_reset, project
from scripts.fuzz_nle_differential import glyph_presentation_class
from scripts.nle_native_entities import PinnedNleEntityReader, SOURCE_COMMIT


NORMAL_SPEED = 12
MONSTER_PRESENTATION_CLASSES = frozenset(
    {
        "normal_monster_presentation",
        "monster_presentation",
        "pet_presentation",
        "detected_monster_presentation",
        "ridden_monster_presentation",
    }
)
DEFAULT_ACTIONS = ("MiscDirection.WAIT", "Command.SEARCH", "Command.TAKEOFF")


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


def _action_ids(env: Any) -> dict[str, int]:
    return {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}


def _eligible(reset: dict[str, Any], frame: dict[str, Any]) -> list[dict[str, Any]]:
    projection = project(reset)
    hero = (int(projection["blstats"][0]), int(projection["blstats"][1]))
    by_position = {(int(entity["x"]), int(entity["y"])): entity for entity in frame["entities"]}
    eligible: list[dict[str, Any]] = []
    for y, row in enumerate(projection["chars"]):
        for x, raw_char in enumerate(row):
            if (x, y) == hero:
                continue
            char = chr(int(raw_char))
            glyph = int(projection["glyphs"][y][x])
            if char in " .#|-+<>_{}~@\0" or glyph_presentation_class(glyph) not in MONSTER_PRESENTATION_CLASSES:
                continue
            entity = by_position.get((x, y))
            if entity is None:
                continue
            points = entity.get("scheduler", {}).get("movement_points")
            if type(points) is int and points < NORMAL_SPEED:
                eligible.append({"entity_id": int(entity["entity_id"]), "x": x, "y": y, "presentation_class": glyph_presentation_class(glyph), "movement_points": points})
    return eligible


def _run(seed: int, action_name: str) -> dict[str, Any]:
    env = _new_env()
    try:
        import nle

        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        reset = normalise_reset(env.reset())
        reader = PinnedNleEntityReader(env.nethack)
        before = reader.snapshot().public_record()
        eligible = _eligible(reset, before)
        before_moves = int(before["source_turn"]["moves"])
        action_id = _action_ids(env)[action_name]
        raw_after = env.step(action_id)[0]
        after = reader.snapshot().public_record()
        if int(after["source_turn"]["moves"]) <= before_moves:
            raise AssertionError(f"{seed} {action_name}: action did not consume a source turn")
        after_by_id = {int(entity["entity_id"]): entity for entity in after["entities"]}
        mismatches = []
        for item in eligible:
            entity = after_by_id.get(item["entity_id"])
            if entity is None or (int(entity["x"]), int(entity["y"])) != (item["x"], item["y"]):
                mismatches.append({"before": item, "after": entity})
        # Keep a public hash as a non-interference/control signal without
        # treating post-action pixels as a gold input.
        public_after = project(normalise_reset(raw_after))
        return {
            "seed": seed,
            "action": action_name,
            "captured_before_action": True,
            "eligible_entities": eligible,
            "eligible_count": len(eligible),
            "source_turn_before": before["source_turn"],
            "source_turn_after": after["source_turn"],
            "post_public_chars_shape": [len(public_after["chars"]), len(public_after["chars"][0])],
            "mismatches": mismatches,
            "status": "pass" if not mismatches else "fail",
        }
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260725)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.cases < 6:
        raise SystemExit("stationary-entity verifier needs at least six held-out seeds")

    first = [_run(args.seed + offset, action) for action in DEFAULT_ACTIONS for offset in range(args.cases)]
    second = [_run(args.seed + offset, action) for action in DEFAULT_ACTIONS for offset in range(args.cases)]
    if first != second:
        raise AssertionError("independent native stationary-entity runs were not exactly repeatable")
    mismatches = [record for record in first if record["mismatches"]]
    positive = [record for record in first if record["eligible_count"]]
    if not positive:
        raise AssertionError("stationary-entity verifier found no positive visible reset actors")
    if mismatches:
        raise AssertionError(f"stationary-entity source mismatches: {mismatches[:2]}")
    report = {
        "schema": "gamebench.nethack.native_first_turn_stationary_entities.v1",
        "status": "pass_source_assertion_only",
        "source_commit": SOURCE_COMMIT,
        "nethack_version": "3.6.6",
        "action_set": list(DEFAULT_ACTIONS),
        "heldout_seed_count": args.cases,
        "boundary": "reset_before_action_to_immediate_post_action",
        "comparison_count": sum(record["eligible_count"] for record in first),
        "positive_boundary_count": len(positive),
        "two_independent_runs_exact": True,
        "gold_implementation_eligible": False,
        "rule": "visible reset monster-class actor with movement_points < NORMAL_SPEED remains at its reset cell across first consumed SEARCH/WAIT/TAKEOFF; destination and later schedule are unmodeled",
        "cases": first,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "cases": args.cases, "comparisons": report["comparison_count"], "report": str(args.report.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
