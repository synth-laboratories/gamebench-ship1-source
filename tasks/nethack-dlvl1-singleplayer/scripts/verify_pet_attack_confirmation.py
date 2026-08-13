#!/usr/bin/env python3
"""Probe source-marked NLE pets before implementing a KICK confirmation.

The deciding evidence is NLE's pet glyph predicate or the MG_PET specials
bit.  A character such as ``d``/``f`` is presentation only and is never used
as an identity or pet-status proxy.  Each case is repeated in a fresh NLE
process with the same paired seed; the report records exact message bytes,
TTY planes/cursors, and public transition outcomes for diagnosis.
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
from scripts.outcome_assertions import transition_outcome


DEFAULT_SEEDS = [*range(12), 20261040, 20260315, 20260316, 20260061]
CARDINALS = (("N", 0, -1), ("E", 1, 0), ("S", 0, 1), ("W", -1, 0))
RESPONSE_ACTIONS = {"y": "CompassDirection.NW", "n": "CompassDirection.SE"}


def expected_raw(text: str, width: int) -> list[int]:
    raw = list(text.encode("ascii"))
    return (raw + [0] * width)[:width]


def _step(value: Any) -> dict[str, Any]:
    return project(normalise_reset(value[0] if isinstance(value, tuple) else value))


def _actions(env: Any) -> dict[str, int]:
    return {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}


def _target(reset: dict[str, Any], *, want_pet: bool, nethack: Any) -> dict[str, Any] | None:
    x, y = (int(reset["blstats"][0]), int(reset["blstats"][1]))
    for direction, dx, dy in CARDINALS:
        glyph = int(reset["glyphs"][y + dy][x + dx])
        special = int(reset["specials"][y + dy][x + dx])
        source_pet = bool(nethack.glyph_is_pet(glyph) or special & int(nethack.MG_PET))
        if source_pet != want_pet:
            continue
        return {
            "direction": direction,
            "x": x + dx,
            "y": y + dy,
            "char": chr(int(reset["chars"][y + dy][x + dx])),
            "glyph": glyph,
            "special": special,
            "source_status": {
                "glyph_is_pet": bool(nethack.glyph_is_pet(glyph)),
                "specials_mg_pet": bool(special & int(nethack.MG_PET)),
            },
        }
    return None


def run_once(seed: int, *, command: str, response: str, want_pet: bool, character: str) -> dict[str, Any] | None:
    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:  # pragma: no cover - command-only guard
        raise RuntimeError("NLE 0.9.0 is required for the live pet confirmation probe") from error

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
        reset = _step(env.reset())
        target = _target(reset, want_pet=want_pet, nethack=nethack)
        if target is None:
            return None
        actions = _actions(env)
        command_snapshot = _step(env.step(actions[command]))
        directed = _step(env.step(actions[f"CompassDirection.{target['direction']}"]))
        response_snapshot = _step(env.step(actions[RESPONSE_ACTIONS[response]]))
        prompt = directed["message"]
        turns = [int(snapshot["blstats"][20]) for snapshot in (reset, command_snapshot, directed, response_snapshot)]
        return {
            "seed": seed,
            "command": command,
            "response": response,
            "target": target,
            "snapshots": [reset, command_snapshot, directed, response_snapshot],
            "messages": [command_snapshot["message"], directed["message"], response_snapshot["message"]],
            "raw_messages": [command_snapshot["message_raw"], directed["message_raw"], response_snapshot["message_raw"]],
            "tty": {
                "directed_chars": directed["tty_chars"],
                "directed_colors": directed["tty_colors"],
                "directed_cursor_yx": directed["tty_cursor_yx"],
                "response_chars": response_snapshot["tty_chars"],
                "response_colors": response_snapshot["tty_colors"],
                "response_cursor_yx": response_snapshot["tty_cursor_yx"],
            },
            "turns": turns,
            "response_outcome": transition_outcome(directed, response_snapshot),
        }
    finally:
        env.close()


def _assert_case(case: dict[str, Any], *, want_pet: bool) -> None:
    prompt = str(case["messages"][1])
    directed_raw = list(case["raw_messages"][1])
    width = len(directed_raw)
    if want_pet and case["command"] == "Command.KICK":
        if not prompt.startswith("Really attack the ") or not prompt.endswith("? [yn] (n)"):
            raise AssertionError(f"source-marked pet KICK did not open a confirmation: {prompt!r}")
        if directed_raw != expected_raw(f"{prompt} ", width):
            raise AssertionError("pet confirmation raw message bytes differ from its source prompt")
        if case["turns"][1] != case["turns"][0] or case["turns"][2] != case["turns"][0]:
            raise AssertionError(f"KICK command/direction prompt consumed a turn: {case['turns']!r}")
        if case["response"] == "n":
            expected = expected_raw(f"{prompt} n", len(case["raw_messages"][2]))
            if case["raw_messages"][2] != expected or case["turns"][3] != case["turns"][2]:
                raise AssertionError("declined pet KICK is not an exact zero-turn no response")
    else:
        # Negative control: force-fight and non-pet KICKs may have their own
        # outcome, but neither gets the pet safety prompt.
        if prompt.startswith("Really attack the "):
            raise AssertionError(f"non-pet/force control unexpectedly confirmed: {prompt!r}")


def _repeatable(first: dict[str, Any], second: dict[str, Any]) -> None:
    if first != second:
        raise AssertionError("fresh executions with the same paired seed disagreed on exact public/TTY evidence")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="append", type=int, default=[])
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    seeds = args.seed or DEFAULT_SEEDS
    if len(set(seeds)) < 2:
        raise SystemExit("pet confirmation probe requires two independent seeds")

    cases: list[dict[str, Any]] = []
    for command, want_pet in (("Command.KICK", True), ("Command.FIGHT", True), ("Command.KICK", False), ("Command.FIGHT", False)):
        responses = ("y", "n") if command == "Command.KICK" and want_pet else ("n",)
        for response in responses:
            for seed in seeds:
                first = run_once(seed, command=command, response=response, want_pet=want_pet, character=args.character)
                if first is None:
                    continue
                second = run_once(seed, command=command, response=response, want_pet=want_pet, character=args.character)
                if second is None:
                    raise AssertionError("source target disappeared in the identical repeated seed")
                _assert_case(first, want_pet=want_pet)
                _repeatable(first, second)
                cases.append({key: value for key, value in first.items() if key != "snapshots"})

    pet_kick_seeds = {case["seed"] for case in cases if case["command"] == "Command.KICK" and case["target"]["source_status"]["glyph_is_pet"] and case["response"] == "n"}
    pet_fight_seeds = {case["seed"] for case in cases if case["command"] == "Command.FIGHT" and case["target"]["source_status"]["glyph_is_pet"]}
    if len(pet_kick_seeds) < 2 or len(pet_fight_seeds) < 2:
        raise SystemExit("insufficient independent source-marked pet seeds for KICK/FIGHT evidence")
    report = {
        "schema": "gamebench.nethack.pet_attack_confirmation_report.v1",
        "status": "pass",
        "seeds": seeds,
        "source_contract": "nethack.glyph_is_pet(glyph) or specials & MG_PET; presentation chars are diagnostic only",
        "behavior_contract": {
            "kick": "source-marked pet KICK opens exact zero-turn [yn] prompt; n preserves prompt plus typed n with no turn",
            "fight": "FIGHT is a force-attack negative control and does not open the pet KICK confirmation",
        },
        "case_counts": {
            "pet_kick": sum(case["command"] == "Command.KICK" and case["target"]["source_status"]["glyph_is_pet"] for case in cases),
            "pet_fight": sum(case["command"] == "Command.FIGHT" and case["target"]["source_status"]["glyph_is_pet"] for case in cases),
            "negative_controls": sum(not case["target"]["source_status"]["glyph_is_pet"] for case in cases),
        },
        "cases": cases,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "pass", "cases": len(cases), "report": str(args.report.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
