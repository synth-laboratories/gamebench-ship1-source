#!/usr/bin/env python3
"""Measure the remaining reset-wall KICK portability blocker.

This verifier is deliberately source-only.  It binds a preselected wall KICK
to the reset player/RNG boundary, replays it twice, and records the hidden
exercise state plus the public stat/HP result.  The report is a validity
artifact: it never becomes a gold input and always remains ineligible for
promotion until a portable action-bound draw/attribute contract exists.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import OBSERVATION_KEYS, deterministic_nle_seeds, normalise_reset
from scripts.nle_native_player import PinnedNlePlayerReader
from scripts.nle_rng_state import PinnedNleRngReader
from scripts.oracle_tape import sha256_json


DIRECTIONS = (
    (0, -1, "N"),
    (1, -1, "NE"),
    (1, 0, "E"),
    (1, 1, "SE"),
    (0, 1, "S"),
    (-1, 1, "SW"),
    (-1, 0, "W"),
    (-1, -1, "NW"),
)


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


def _name(value: Any) -> str:
    raw = bytes(int(cell) for cell in value).split(b"\0", 1)[0]
    return raw.decode("utf-8", errors="replace")


def _player_summary(record: dict[str, Any]) -> dict[str, Any]:
    player = record["player"]
    attrs = player["attributes"]["effective"]
    resources = player["resources"]
    return {
        "source_turn": int(record["source_turn"]),
        "hp": int(resources["hp"]),
        "dexterity": int(attrs["dexterity"]),
        "constitution": int(attrs["constitution"]),
        "wounded_legs": copy.deepcopy(player["conditions"]["wounded_legs"]),
        "exercise_state": copy.deepcopy(player.get("exercise_state")),
    }


def _one(seed: int) -> dict[str, Any] | None:
    from nle import nethack

    env = _new_env()
    try:
        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        observation = normalise_reset(env.reset())
        player = PinnedNlePlayerReader(env.nethack)
        rng = PinnedNleRngReader(env.nethack)
        before = player.snapshot().public_record()
        reset_rng = rng.snapshot().public_record()
        x, y = int(observation["blstats"][0]), int(observation["blstats"][1])
        chars = observation["chars"]
        target: tuple[int, int, str] | None = None
        for dx, dy, direction in DIRECTIONS:
            tx, ty = x + dx, y + dy
            if 0 <= tx < 79 and 0 <= ty < 21 and chr(int(chars[ty][tx])) in "|-":
                target = tx, ty, direction
                break
        if target is None:
            return None
        ids = {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}
        env.step(ids["Command.KICK"])
        result = env.step(ids[f"CompassDirection.{target[2]}"])
        after_observation = normalise_reset(result[0] if isinstance(result, tuple) else result)
        after = player.snapshot().public_record()
        after_rng = rng.snapshot().public_record()
        before_summary = _player_summary(before)
        after_summary = _player_summary(after)
        return {
            "seed": int(seed),
            "target": {"x": target[0], "y": target[1], "direction": target[2], "surface": chr(int(chars[target[1]][target[0]]))},
            "message": _name(after_observation["message"]),
            "before": before_summary,
            "after": after_summary,
            "deltas": {
                "hp": after_summary["hp"] - before_summary["hp"],
                "dexterity": after_summary["dexterity"] - before_summary["dexterity"],
                "constitution": after_summary["constitution"] - before_summary["constitution"],
                "turn": after_summary["source_turn"] - before_summary["source_turn"],
            },
            "reset_rng": {lane: {"n": int(reset_rng[lane]["n"]), "state_sha256": reset_rng[lane]["state_sha256"]} for lane in ("core", "display")},
            "after_rng": {lane: {"n": int(after_rng[lane]["n"]), "state_sha256": after_rng[lane]["state_sha256"]} for lane in ("core", "display")},
        }
    finally:
        env.close()


def verify(seeds: list[int]) -> dict[str, Any]:
    first = [case for seed in seeds if (case := _one(seed)) is not None]
    second = [case for seed in seeds if (case := _one(seed)) is not None]
    replay_exact = first == second
    if not replay_exact:
        raise AssertionError("independent reset-wall KICK source replays differ")
    signatures = {
        (
            case["deltas"]["hp"],
            case["deltas"]["dexterity"],
            case["deltas"]["constitution"],
            bool(case["after"]["wounded_legs"]["active"]),
        )
        for case in first
    }
    exercise_states = {sha256_json(case["before"]["exercise_state"]) for case in first}
    after_exercise_states = {sha256_json(case["after"]["exercise_state"]) for case in first}
    exercise_changed = sum(case["before"]["exercise_state"] != case["after"]["exercise_state"] for case in first)
    return {
        "schema": "gamebench.nethack.reset_wall_kick_portability_blocker.v1",
        "status": "source_pass_gold_blocked" if replay_exact and first else "source_insufficient",
        "source_only": True,
        "gold_runtime_inputs": [],
        "seeds_requested": [int(seed) for seed in seeds],
        "cases": first,
        "case_count": len(first),
        "independent_replay_exact": replay_exact,
        "distinct_public_outcome_signatures": len(signatures),
        "distinct_reset_exercise_states": len(exercise_states),
        "distinct_post_kick_exercise_states": len(after_exercise_states),
        "post_kick_exercise_state_changes": exercise_changed,
        "blockers": [
            "exercise() consumes action-bound rn2(2) draws and mutates hidden aexe/atime state",
            "attribute-check timing is controlled by context.next_attrib_check, not public blstats",
            "whole-turn actor/scheduler draws are not assigned to the KICK branch",
            "no portable action-bound projection is authorized for either gold lane",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260725)
    parser.add_argument("--cases", type=int, default=20)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.cases < 3:
        raise SystemExit("--cases must be at least 3")
    report = verify([args.seed + offset for offset in range(args.cases)])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    summary = {
        key: report[key]
        for key in (
            "status",
            "case_count",
            "independent_replay_exact",
            "distinct_public_outcome_signatures",
            "distinct_reset_exercise_states",
            "distinct_post_kick_exercise_states",
            "post_kick_exercise_state_changes",
        )
    }
    summary["report"] = str(args.report.resolve())
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
