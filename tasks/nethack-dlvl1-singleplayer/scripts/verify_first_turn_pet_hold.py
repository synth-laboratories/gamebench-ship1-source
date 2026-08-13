#!/usr/bin/env python3
"""Fast, replayable *rejection* probe for an unsafe reset-pet hypothesis.

The older dynamic-pet probe intentionally creates a fresh NLE process for
every action/seed pair.  This verifier reuses one pinned environment and
reseeds it before every case, which keeps the same reset boundary while making
the validity control practical for a larger split.  The hypothesis under test
is intentionally broader than the promoted gold contract: every cardinal
movement and stationary action would retain the reset pet pixel for one
consumed turn.  A successful run must reject that hypothesis with a concrete
time-boundary or presentation counterexample.  It never assigns a stable id,
destination, path, collision, or scheduler rule.
"""

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


CONSUMED_ACTIONS = (
    "CompassDirection.N",
    "CompassDirection.E",
    "CompassDirection.S",
    "CompassDirection.W",
    "MiscDirection.WAIT",
    "Command.SEARCH",
)
ZERO_TURN_ACTIONS = ("Command.INVENTORY", "Command.QUIT")


def pet_cells(snapshot: dict[str, Any], nethack: Any) -> list[dict[str, int | str]]:
    projected = project(snapshot)
    cells: list[dict[str, int | str]] = []
    glyphs = projected["glyphs"]
    chars = projected["chars"]
    colors = projected["colors"]
    specials = projected["specials"]
    for y, row in enumerate(glyphs):
        for x, raw in enumerate(row):
            glyph = int(raw)
            special = int(specials[y][x])
            if not (bool(nethack.glyph_is_pet(glyph)) or special & int(nethack.MG_PET)):
                continue
            cells.append({"x": x, "y": y, "char": chr(int(chars[y][x])), "glyph": glyph, "color": int(colors[y][x])})
    return cells


def action_ids(env: Any) -> dict[str, int]:
    return {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run(*, seeds: list[int], trials: int) -> dict[str, Any]:
    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:  # pragma: no cover
        raise RuntimeError("NLE 0.9.0 is required for this source probe") from error
    env = nle.env.NLE(
        character="val-hum-fem-law",
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    try:
        ids = action_ids(env)
        cases: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for trial in range(trials):
            for seed in seeds:
                core, display = deterministic_nle_seeds(seed)
                env.seed(core=core, disp=display, reseed=False)
                reset = normalise_reset(env.reset())
                before = project(reset)
                before_cells = pet_cells(reset, nethack)
                for action_name in CONSUMED_ACTIONS + ZERO_TURN_ACTIONS:
                    # Reset again before every action so the action is the
                    # named first input, never a suffix of another case.
                    env.seed(core=core, disp=display, reseed=False)
                    reset = normalise_reset(env.reset())
                    before = project(reset)
                    before_cells = pet_cells(reset, nethack)
                    result = env.step(ids[action_name])
                    after_raw = result[0] if isinstance(result, tuple) else result
                    after = normalise_reset(after_raw)
                    after_projected = project(after)
                    after_cells = pet_cells(after, nethack)
                    before_time = int(before["blstats"][20])
                    after_time = int(after_projected["blstats"][20])
                    expected_delta = 0 if action_name in ZERO_TURN_ACTIONS else 1
                    exact_hold = len(before_cells) == len(after_cells) == 1 and before_cells == after_cells
                    delta_ok = after_time - before_time == expected_delta
                    record = {
                        "trial": trial,
                        "seed": seed,
                        "action": action_name,
                        "before_pet": before_cells,
                        "after_pet": after_cells,
                        "time_delta": after_time - before_time,
                        "expected_time_delta": expected_delta,
                        "exact_hold": exact_hold,
                        "passes": exact_hold and delta_ok,
                    }
                    cases.append(record)
                    if not record["passes"]:
                        errors.append(record)
        return {
            "schema": "gamebench.nethack.first_turn_pet_hold_rejection.v1",
            "status": "not_rejected" if not errors else "hypothesis_rejected",
            "source_runtime": {"nle_version": getattr(nle, "__version__", "unknown"), "nethack_version": "3.6.6"},
            "seeds": seeds,
            "trials": trials,
            "consumed_actions": list(CONSUMED_ACTIONS),
            "zero_turn_actions": list(ZERO_TURN_ACTIONS),
            "case_count": len(cases),
            "error_count": len(errors),
            "case_digest": digest(cases),
            "cases": cases,
            "errors": errors,
            "contract": {
                "hypothesis": "all six listed consumed actions retain exactly one reset pet cell and blstats time delta 1",
                "zero_turn_prompt": "inventory/quit remain zero-turn controls and do not consume the hold",
                "promoted_gold_contract": "stationary WAIT/SEARCH only; this probe does not authorize movement holds",
                "forbidden_inference": ["stable entity id", "destination", "path", "collision", "combat", "later scheduler", "RNG chronology"],
            },
        }
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="append", type=int, default=[])
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    seeds = args.seed or list(range(20260725, 20260733))
    report = run(seeds=seeds, trials=max(1, int(args.trials)))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "case_count", "error_count", "case_digest", "report") if key in report} | {"report": str(args.report.resolve())}, sort_keys=True))
    if report["status"] != "hypothesis_rejected":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
