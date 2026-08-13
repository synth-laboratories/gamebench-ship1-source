#!/usr/bin/env python3
"""Verify read-only evolving RNG-state evidence from the pinned NLE runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import (
    OBSERVATION_KEYS,
    deterministic_nle_seeds,
    normalise_reset,
    project,
)
from scripts.nle_rng_state import PINNED_SOURCE_COMMIT, PinnedNleRngReader, bounded_call_count


CARDINALS = (("N", 0, -1), ("E", 1, 0), ("S", 0, 1), ("W", -1, 0))
WALL_SCAN_SEEDS = [*range(12), 20261040, 20260315, 20260316, 20260061]


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _actions(env: Any) -> dict[str, int]:
    return {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}


def _run(seed: int, character: str) -> dict[str, Any]:
    import nle
    from nle import nethack

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
        reset = project(normalise_reset(env.reset()))
        reader = PinnedNleRngReader(env.nethack)
        before = reader.snapshot()
        second_read = reader.snapshot()
        if before != second_read:
            raise AssertionError("RNG snapshot capture mutated the oracle")

        actions = _actions(env)
        search = project(normalise_reset(env.step(actions["Command.SEARCH"])[0]))
        after = reader.snapshot()
        public_seed = tuple(int(value) for value in env.get_seeds())
        return {
            "seed": seed,
            "configured_seeds": [core, display, False],
            "public_get_seeds_after_search": list(public_seed),
            "reset_public_sha256": _digest(reset),
            "search_public_sha256": _digest(search),
            "before": before.public_record(),
            "after": after.public_record(),
            "draws": {
                "core": bounded_call_count(before, after, "core"),
                "display": bounded_call_count(before, after, "display"),
            },
            "exact_call_chronology": {
                "core": reader.exact_call_count(before, after, "core"),
                "display": reader.exact_call_count(before, after, "display"),
                "contract": "full raw ISAAC64 pre-state replayed with the pinned native next-value routine equals the full raw post-state",
            },
            "read_only_double_capture": True,
        }
    finally:
        env.close()


def _run_wall_kick(seed: int, character: str) -> dict[str, Any] | None:
    import nle
    from nle import nethack

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
        reset = project(normalise_reset(env.reset()))
        x, y = int(reset["blstats"][0]), int(reset["blstats"][1])
        direction = None
        for name, dx, dy in CARDINALS:
            char = chr(int(reset["chars"][y + dy][x + dx]))
            if char in "|-":
                direction = name
                break
        if direction is None:
            return None

        reader = PinnedNleRngReader(env.nethack)
        actions = _actions(env)
        reset_rng = reader.snapshot()
        prompt = project(normalise_reset(env.step(actions["Command.KICK"])[0]))
        prompt_rng = reader.snapshot()
        result = project(normalise_reset(env.step(actions[f"CompassDirection.{direction}"])[0]))
        result_rng = reader.snapshot()
        deltas = {}
        for slot, name in ((4, "dexterity"), (10, "hp"), (20, "time")):
            before, after = int(reset["blstats"][slot]), int(result["blstats"][slot])
            deltas[name] = after - before
        return {
            "seed": seed,
            "direction": direction,
            "reset": reset_rng.public_record(),
            "after_prompt": prompt_rng.public_record(),
            "after_result": result_rng.public_record(),
            "draws": {
                "prompt_core": bounded_call_count(reset_rng, prompt_rng, "core"),
                "prompt_display": bounded_call_count(reset_rng, prompt_rng, "display"),
                "result_core": bounded_call_count(prompt_rng, result_rng, "core"),
                "result_display": bounded_call_count(prompt_rng, result_rng, "display"),
            },
            "exact_call_chronology": {
                "prompt_core": reader.exact_call_count(reset_rng, prompt_rng, "core"),
                "prompt_display": reader.exact_call_count(reset_rng, prompt_rng, "display"),
                "result_core": reader.exact_call_count(prompt_rng, result_rng, "core"),
                "result_display": reader.exact_call_count(prompt_rng, result_rng, "display"),
                "contract": "full raw ISAAC64 boundary replay; this counts draws but does not assign individual source branch ownership",
            },
            "message": result["message"],
            "blstats_deltas": deltas,
            "prompt_public_sha256": _digest(prompt),
            "result_public_sha256": _digest(result),
        }
    finally:
        env.close()


def build_report(seeds: list[int], character: str) -> dict[str, Any]:
    cases = []
    for seed in seeds:
        first = _run(seed, character)
        second = _run(seed, character)
        if first != second:
            raise AssertionError(f"seed {seed}: independent authoritative RNG replay differs")
        if first["public_get_seeds_after_search"] != first["configured_seeds"]:
            raise AssertionError(f"seed {seed}: public seed API contract changed")
        if first["draws"]["core"] <= 0:
            raise AssertionError(f"seed {seed}: SEARCH unexpectedly consumed no core RNG")
        if first["draws"]["core"] != first["exact_call_chronology"]["core"]:
            raise AssertionError(f"seed {seed}: index delta and exact raw-state chronology disagree")
        cases.append(first)

    binary_hashes = sorted({case["before"]["binary_sha256"] for case in cases})
    if len(binary_hashes) != 1:
        raise AssertionError("copied NLE libraries do not have one exact binary identity")
    wall_kicks = []
    for seed in WALL_SCAN_SEEDS:
        first = _run_wall_kick(seed, character)
        if first is None:
            continue
        second = _run_wall_kick(seed, character)
        if first != second:
            raise AssertionError(f"wall seed {seed}: authoritative KICK replay differs")
        wall_kicks.append(first)
    if len(wall_kicks) < 3:
        raise AssertionError("fewer than three reset-visible wall KICK authority cases")

    return {
        "schema": "gamebench.nethack.authoritative_rng_report.v1",
        "status": "pass",
        "source_identity": {
            "nle": "0.9.0",
            "nethack": "3.6.6",
            "source_commit": PINNED_SOURCE_COMMIT,
            "binary_sha256": binary_hashes[0],
            "runtime_surface": "verified local Mach-O rnglist symbol in the per-instance copied libnethack",
        },
        "cases": cases,
        "wall_kick_cases": wall_kicks,
        "summary": {
            "independent_replays": len(cases) * 2,
            "read_only_snapshots": len(cases) * 4,
            "core_draw_counts": sorted({case["draws"]["core"] for case in cases}),
            "display_draw_counts": sorted({case["draws"]["display"] for case in cases}),
            "configured_seed_api_unchanged": True,
            "wall_kick_cases": len(wall_kicks),
            "wall_kick_result_core_draw_counts": sorted({case["draws"]["result_core"] for case in wall_kicks}),
            "wall_kick_result_display_draw_counts": sorted({case["draws"]["result_display"] for case in wall_kicks}),
            "exact_raw_state_call_chronology": True,
        },
        "validity": {
            "source_rng_observable": True,
            "source_assertion_eligible": True,
            "gold_rng_or_branch_implementation_eligible": False,
            "accepted": [
                "exact evolving pre/post-action core and display ISAAC64 state hashes",
                "bounded per-action draw counts when no more than one ISAAC64 block is crossed",
                "read-only capture with exact independent same-seed replay",
                "exact reset-wall KICK prompt/result RNG boundaries and public injury deltas",
                "exact per-lane call count only when every non-target RNG lane is byte-identical",
            ],
            "not_yet_authorized": [
                "mapping draws to combat or KICK branches",
                "dynamic actor call chronology",
                "portable capture outside the pinned macOS wheel ABI",
                "gold RNG simulation or source-state restore",
            ],
            "call_ownership_ambiguities": [
                "dokick.c:1227-1244 conditionally consumes rn2(3)/rnd(5) then always consumes rnd(CON...) on the wall-injury path",
                "the whole action boundary also includes wake_nearby, engraving state, timeout work, and post-player movemon processing",
                "uhitm.c and monmove.c expose many conditional rn2 call sites whose predicate state is not a gold-runtime input",
            ],
            "gold_implementation_eligible": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--seed-base", type=int, default=20260725)
    parser.add_argument("--character", default="Agent-val-hum-neu-fem")
    parser.add_argument("--report", type=Path, default=TASK_DIR / "reports" / "authoritative_rng_20260730.json")
    args = parser.parse_args()
    if args.seeds < 3:
        parser.error("--seeds must be at least 3 for independent evidence")
    report = build_report(list(range(args.seed_base, args.seed_base + args.seeds)), args.character)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "cases": len(report["cases"]),
        "core_draw_counts": report["summary"]["core_draw_counts"],
        "wall_kick_cases": report["summary"]["wall_kick_cases"],
        "wall_kick_core_draw_counts": report["summary"]["wall_kick_result_core_draw_counts"],
        "report": str(args.report.resolve()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
