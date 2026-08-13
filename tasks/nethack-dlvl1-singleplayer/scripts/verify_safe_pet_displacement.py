#!/usr/bin/env python3
"""Validate the bounded ``hack.c`` safepet displacement contract.

This is a read-only source oracle.  It selects the first action uniformly as
the direction from the hero to the one native tame entity adjacent at reset,
then proves that the reset core ISAAC64 ``rn2(7)`` value predicts the observed
``attack()`` stop/swap branch.  No gold lane or future tape is consulted.
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
from scripts.nle_native_entities import PinnedNleEntityReader
from scripts.nle_rng_state import PinnedNleRngReader
from scripts.portable_reset_rng import portable_reset_rng_projection, replay_projection


DIRECTIONS = {
    (-1, -1): "CompassDirection.NW",
    (0, -1): "CompassDirection.N",
    (1, -1): "CompassDirection.NE",
    (-1, 0): "CompassDirection.W",
    (1, 0): "CompassDirection.E",
    (-1, 1): "CompassDirection.SW",
    (0, 1): "CompassDirection.S",
    (1, 1): "CompassDirection.SE",
}


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


def _one_run(seed: int) -> dict[str, Any]:
    import nle
    from nle import nethack

    env = _new_env()
    try:
        core, display = deterministic_nle_seeds(seed)
        configured = tuple(int(value) for value in env.seed(core=core, disp=display, reseed=False))
        if configured != (core, display, False):
            raise RuntimeError("NLE declined the deterministic reset seed")
        before_raw = normalise_reset(env.reset())
        before = project(before_raw)
        entity_reader = PinnedNleEntityReader(env.nethack)
        rng_reader = PinnedNleRngReader(env.nethack)
        before_entities = entity_reader.snapshot().public_record()
        before_rng = rng_reader.snapshot()
        hero_x, hero_y = int(before["blstats"][0]), int(before["blstats"][1])
        adjacent = [
            entity for entity in before_entities["entities"]
            if entity.get("allegiance") == "tame"
            and max(abs(int(entity.get("x", -999)) - hero_x), abs(int(entity.get("y", -999)) - hero_y)) == 1
        ]
        if len(adjacent) != 1:
            raise RuntimeError(f"seed {seed} does not have exactly one adjacent tame entity")
        pet = adjacent[0]
        dx, dy = int(pet["x"]) - hero_x, int(pet["y"]) - hero_y
        action_name = DIRECTIONS.get((dx, dy))
        if action_name is None:
            raise RuntimeError(f"seed {seed} tame entity is not one-step adjacent: {(dx, dy)}")
        glyph = int(before["glyphs"][int(pet["y"])][int(pet["x"])])
        special = int(before["specials"][int(pet["y"])][int(pet["x"])])
        if not (bool(nethack.glyph_is_pet(glyph)) or special & int(nethack.MG_PET)):
            raise RuntimeError("native tame entity is not source-visible as a pet at reset")
        reset_rng = portable_reset_rng_projection(before_rng.public_record())
        draws, _ = replay_projection(reset_rng, "core", 1)
        roll = int(draws[0] % 7)
        stepped = env.step(_action_ids(env)[action_name])
        after = project(normalise_reset(stepped[0] if isinstance(stepped, tuple) else stepped))
        after_entities = entity_reader.snapshot().public_record()
        after_pet = next((entity for entity in after_entities["entities"] if entity.get("entity_id") == pet.get("entity_id")), None)
        if after_pet is None:
            raise RuntimeError("adjacent tame entity disappeared from the immediate source boundary")
        expected_swap = roll != 0
        expected_hero = [int(pet["x"]), int(pet["y"])] if expected_swap else [hero_x, hero_y]
        expected_pet = [hero_x, hero_y] if expected_swap else [int(pet["x"]), int(pet["y"])]
        actual_hero = [int(after["blstats"][0]), int(after["blstats"][1])]
        actual_pet = [int(after_pet["x"]), int(after_pet["y"])]
        name = str(before.get("chars", [[" "]])[int(pet["y"])][int(pet["x"])])
        message = str(after.get("message", ""))
        return {
            "seed": int(seed),
            "action": action_name,
            "entity_id": int(pet["entity_id"]),
            "species_id": int(pet["species_id"]),
            "pet_name_source": str(pet.get("path_state", {}).get("species_name", "unavailable")),
            "reset_core_n": int(before_rng.core_n),
            "first_core_draw_mod_7": roll,
            "expected_branch": "swap" if expected_swap else "stop",
            "actual_hero": actual_hero,
            "expected_hero": expected_hero,
            "actual_pet": actual_pet,
            "expected_pet": expected_pet,
            "message": message,
            "hero_match": actual_hero == expected_hero,
            "pet_match": actual_pet == expected_pet,
            "branch_match": ("swap places with" in message) == expected_swap,
            "source_native_exact": actual_hero == expected_hero and actual_pet == expected_pet,
            "identity": {"source_commit": before_entities["source_commit"], "binary_sha256": before_entities["binary_sha256"]},
        }
    finally:
        env.close()


def verify(seeds: list[int]) -> dict[str, Any]:
    first = [_one_run(seed) for seed in seeds]
    second = [_one_run(seed) for seed in seeds]
    if first != second:
        raise AssertionError("independent source replays differ")
    failures = [case for case in first if not case["source_native_exact"] or not case["branch_match"]]
    return {
        "schema": "gamebench.nethack.safe_pet_displacement_source_gate.v1",
        "status": "pass" if not failures else "fail",
        "seeds": [int(seed) for seed in seeds],
        "case_count": len(first),
        "failure_count": len(failures),
        "independent_replay_exact": True,
        "source_only": True,
        "gold_runtime_inputs": [],
        "contract": {
            "source": "hack.c attack(): is_safepet; rn2(7)==0 stops, otherwise hero/pet swap",
            "rng_lane": "reset-bound core ISAAC64, first draw at the adjacent-pet action boundary",
            "scope": "one reset-visible tame entity adjacent to hero; no later pet scheduler/path policy",
        },
        "cases": first,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="append", type=int, default=[])
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    seeds = args.seed or list(range(20260725, 20260745))
    report = verify(seeds)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "cases": report["case_count"], "report": str(args.report.resolve())}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
