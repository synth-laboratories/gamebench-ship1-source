#!/usr/bin/env python3
"""Verify pickup semantics only after the reset hero's terrain is observed.

The NLE ``chars`` plane renders ``@`` at reset, so it cannot itself tell us
whether the hero begins on ordinary floor or a fixed stair.  This campaign
moves to an already-visible adjacent floor square, observes the vacated reset
cell, returns, and only then sends ``PICKUP``.  It is deliberately diagnostic:
it writes a report and never promotes a fixture or changes the gold state.
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
from scripts.compare_nle_discrepancies import compare_fixture


FIXED_STAIR_MESSAGE = "The stairs are solidly fixed to the floor."
STATIC_STAIRS = frozenset(("<", ">"))
CARDINALS = (("E", 1, 0, "W"), ("W", -1, 0, "E"), ("N", 0, -1, "S"), ("S", 0, 1, "N"))


def _raw_message(projection: dict[str, Any]) -> list[int]:
    raw = projection.get("message_raw", [])
    return [int(value) for value in raw] if isinstance(raw, list) else []


def expected_message_raw(text: str, width: int) -> list[int]:
    encoded = list(text.encode("ascii"))
    if len(encoded) > width:
        raise ValueError("expected message does not fit the observed NLE message buffer")
    return encoded + [0] * (width - len(encoded))


def _observation_from_step(result: Any) -> dict[str, Any]:
    return normalise_reset(result[0] if isinstance(result, tuple) else result)


def _action_ids(env: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, action in enumerate(env.actions):
        result[f"{action.__class__.__name__}.{action.name}"] = index
    return result


def _cell(chars: Any, x: int, y: int) -> str:
    if not isinstance(chars, list) or not (0 <= y < len(chars)):
        return ""
    row = chars[y]
    if not isinstance(row, list) or not (0 <= x < len(row)):
        return ""
    return chr(int(row[x]))


def verify_seed(seed: int, *, character: str) -> dict[str, Any]:
    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:  # pragma: no cover - command-only guard
        raise RuntimeError("NLE 0.9.0 is required for the live known-underlay campaign") from error

    env = nle.env.NLE(
        character=character,
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    try:
        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        observation = normalise_reset(env.reset())
        reset = project(observation)
        origin_x, origin_y = (int(reset["blstats"][0]), int(reset["blstats"][1]))
        action_ids = _action_ids(env)

        departure: tuple[str, int, int, str] | None = None
        for direction, dx, dy, reverse in CARDINALS:
            if _cell(reset["chars"], origin_x + dx, origin_y + dy) == ".":
                departure = (direction, dx, dy, reverse)
                break
        if departure is None:
            raise AssertionError("no adjacent raw visible floor cell is available for a safe underlay observation")
        direction, dx, dy, reverse = departure

        left = project(_observation_from_step(env.step(action_ids[f"CompassDirection.{direction}"])))
        if left["blstats"][:2] != [origin_x + dx, origin_y + dy]:
            raise AssertionError("departure did not move onto the selected raw floor cell")
        observed_underlay = _cell(left["chars"], origin_x, origin_y)
        if observed_underlay not in STATIC_STAIRS:
            raise AssertionError(f"vacated reset cell is {observed_underlay!r}, not a raw visible stair")

        returned = project(_observation_from_step(env.step(action_ids[f"CompassDirection.{reverse}"])))
        if returned["blstats"][:2] != [origin_x, origin_y]:
            raise AssertionError("return did not restore the hero to the observed-underlay cell")

        picked = project(_observation_from_step(env.step(action_ids["Command.PICKUP"])))
        message_raw = _raw_message(picked)
        expected_raw = expected_message_raw(FIXED_STAIR_MESSAGE, len(message_raw))
        if message_raw != expected_raw:
            raise AssertionError("PICKUP after an observed stair underlay has unexpected exact raw message bytes")
        turns = [int(reset["blstats"][20]), int(left["blstats"][20]), int(returned["blstats"][20]), int(picked["blstats"][20])]
        if turns[1] != turns[0] + 1 or turns[2] != turns[1] + 1 or turns[3] != turns[2]:
            raise AssertionError(f"unexpected turn consumption {turns!r}")
        return {
            "seed": seed,
            "origin": {"x": origin_x, "y": origin_y},
            "departure": direction,
            "observed_underlay": observed_underlay,
            "message": picked["message"],
            "message_raw": message_raw,
            "turns": turns,
        }
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, action="append", default=[], help="Repeatable core seed; defaults to five fixed seeds.")
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    seeds = args.seed or [0, 1, 2, 3, 4]
    if len(set(seeds)) < 2:
        raise SystemExit("known-underlay campaign requires at least two distinct seeds")

    cases = [verify_seed(seed, character=args.character) for seed in seeds]
    # The two frozen tapes cover the same exact responses in both independent
    # implementation lanes.  Keep live NLE evidence and replay parity separate.
    parity = {
        fixture: {lane: compare_fixture(TASK_DIR / "fixtures" / "nle_oracle" / fixture, lane) for lane in ("python", "rust")}
        for fixture in ("val-stair-pickup-seed-10", "val-east-pickup-seed-20260725")
    }
    if any(failures for lanes in parity.values() for failures in lanes.values()):
        raise SystemExit("known-underlay campaign found Python/Rust replay divergence")
    report = {
        "schema": "gamebench.nethack.known_underlay_pickup_report.v1",
        "status": "pass",
        "seeds": seeds,
        "cases": cases,
        "fixed_stair_message": FIXED_STAIR_MESSAGE,
        "frozen_parity": parity,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "pass", "seeds": len(cases), "report": str(args.report.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
