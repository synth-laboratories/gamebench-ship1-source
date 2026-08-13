#!/usr/bin/env python3
"""Record exact, repeatable FIGHT and movement-attack evidence from NLE.

This is deliberately an oracle probe, not a combat implementation.  A normal
monster glyph plus ``glyph_to_mon`` establishes only a visible species surface.
It does *not* establish one persistent entity, its hostility, HP, to-hit roll,
damage roll, movement policy, or a later position.  Consequently every case
records public observations and repeatability, while ``implementation_eligible``
remains false unless a future capture supplies those missing source fields.
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


PROMPT_RAW_TEXT = "In what direction? "
CARDINALS = (("N", 0, -1), ("E", 1, 0), ("S", 0, 1), ("W", -1, 0))
DEFAULT_SEEDS = [*range(48), 20261040, 20260315, 20260316, 20260061]


def expected_raw(text: str, width: int) -> list[int]:
    raw = list(text.encode("ascii"))
    if len(raw) > width:
        raise ValueError("text does not fit the NLE message buffer")
    return raw + [0] * (width - len(raw))


def _step(value: Any) -> dict[str, Any]:
    return project(normalise_reset(value[0] if isinstance(value, tuple) else value))


def _actions(env: Any) -> dict[str, int]:
    return {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}


def source_combat_target(reset: dict[str, Any], nethack: Any) -> dict[str, Any] | None:
    """Return only a source-visible, non-pet normal-monster surface.

    ``glyph_is_monster`` is intentionally not treated as an identity.  Pet
    surfaces are a separate, source-pinned prompt protocol and therefore a
    negative control for this hostile-combat experiment.
    """

    x, y = (int(reset["blstats"][0]), int(reset["blstats"][1]))
    for direction, dx, dy in CARDINALS:
        glyph = int(reset["glyphs"][y + dy][x + dx])
        special = int(reset["specials"][y + dy][x + dx])
        is_monster = bool(nethack.glyph_is_monster(glyph))
        is_pet = bool(nethack.glyph_is_pet(glyph) or special & int(nethack.MG_PET))
        if not is_monster or is_pet:
            continue
        monster_id = int(nethack.glyph_to_mon(glyph))
        species = nethack.permonst(monster_id)
        return {
            "direction": direction,
            "x": x + dx,
            "y": y + dy,
            "char": chr(int(reset["chars"][y + dy][x + dx])),
            "glyph": glyph,
            "color": int(reset["colors"][y + dy][x + dx]),
            "special": special,
            "species_id": monster_id,
            "species_name": str(species.mname),
            "provenance": "glyph_is_monster+glyph_to_mon_permonst",
            "entity_identity": "unavailable_from_nle_presentation",
            "hostility": "unavailable_from_nle_presentation",
            "hp": "unavailable_from_nle_presentation",
            "implementation_eligible": False,
            "ineligibility": [
                "no_source_entity_identity",
                "no_source_hostility",
                "no_source_hp_or_combat_rng_state",
            ],
        }
    return None


def _new_env(character: str) -> Any:
    import nle
    from nle import nethack

    return nle.env.NLE(
        character=character,
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )


def _reset(env: Any, seed: int) -> dict[str, Any]:
    core, display = deterministic_nle_seeds(seed)
    env.seed(core=core, disp=display, reseed=False)
    return _step(env.reset())


def _configured_seeds(env: Any) -> list[int | bool]:
    """Expose NLE's public configured-seed API without mislabeling it RNG state."""

    return [value if isinstance(value, bool) else int(value) for value in env.get_seeds()]


def run_once(seed: int, *, character: str) -> dict[str, Any] | None:
    try:
        from nle import nethack
    except ModuleNotFoundError as error:  # pragma: no cover - live command guard
        raise RuntimeError("NLE 0.9.0 is required for the visible-target combat campaign") from error

    fight_env = _new_env(character)
    move_env = _new_env(character)
    try:
        fight_reset = _reset(fight_env, seed)
        fight_seeds_at_reset = _configured_seeds(fight_env)
        target = source_combat_target(fight_reset, nethack)
        if target is None:
            return None
        actions = _actions(fight_env)
        fight_prompt = _step(fight_env.step(actions["Command.FIGHT"]))
        fight_seeds_after_prompt = _configured_seeds(fight_env)
        fight_result = _step(fight_env.step(actions[f"CompassDirection.{target['direction']}"]))
        fight_seeds_after_result = _configured_seeds(fight_env)

        move_reset = _reset(move_env, seed)
        move_seeds_at_reset = _configured_seeds(move_env)
        move_target = source_combat_target(move_reset, nethack)
        if move_target != target:
            raise AssertionError("same paired seed selected a different visible combat surface")
        move_result = _step(move_env.step(_actions(move_env)[f"CompassDirection.{target['direction']}"]))
        move_seeds_after_result = _configured_seeds(move_env)

        if not (
            fight_seeds_at_reset == fight_seeds_after_prompt == fight_seeds_after_result
            and move_seeds_at_reset == move_seeds_after_result == fight_seeds_at_reset
        ):
            raise AssertionError("NLE get_seeds changed shape/value; re-audit RNG-state eligibility")

        fight_outcome = transition_outcome(fight_prompt, fight_result)
        move_outcome = transition_outcome(move_reset, move_result)
        # This is an observable equivalence assertion, not a claim that the
        # two syntaxes share a cloneable internal combat implementation.
        if fight_outcome != move_outcome:
            raise AssertionError("source-visible FIGHT and movement attack diverged in public outcome")

        prompt_raw = [int(value) for value in fight_prompt["message_raw"]]
        # The first action can be overpainted by an NLE startup announcement
        # (notably the full-moon message).  The command is nevertheless
        # accepted and the following direction resolves it.  Preserve the
        # exact raw observation and say whether the prompt was visible; do
        # not replace a source announcement with an invented prompt.
        prompt_visible = prompt_raw == expected_raw(PROMPT_RAW_TEXT, len(prompt_raw))
        fight_turns = [int(snapshot["blstats"][20]) for snapshot in (fight_reset, fight_prompt, fight_result)]
        if fight_turns[1] != fight_turns[0]:
            raise AssertionError(f"FIGHT prompt consumed a turn: {fight_turns!r}")
        move_turns = [int(snapshot["blstats"][20]) for snapshot in (move_reset, move_result)]
        return {
            "seed": seed,
            "target": target,
            "fight": {
                "prompt": {
                    "message": fight_prompt["message"],
                    "message_raw": prompt_raw,
                    "expected_direction_prompt_raw": expected_raw(PROMPT_RAW_TEXT, len(prompt_raw)),
                    "direction_prompt_visible": prompt_visible,
                    "visibility_status": "visible" if prompt_visible else "masked_by_source_message",
                },
                "turns": fight_turns,
                "outcome": fight_outcome,
            },
            "movement": {
                "turns": move_turns,
                "outcome": move_outcome,
                "exact_public_outcome_equal_to_fight": True,
            },
            "death_probe": {
                "status": "not_run",
                "reason": "source does not disclose target HP, combat RNG state, or safe bounded kill horizon",
            },
            "rng_eligibility": {
                "get_seeds": {
                    "fight_reset": fight_seeds_at_reset,
                    "fight_after_prompt": fight_seeds_after_prompt,
                    "fight_after_result": fight_seeds_after_result,
                    "movement_reset": move_seeds_at_reset,
                    "movement_after_result": move_seeds_after_result,
                },
                "finding": "NLE get_seeds is a pinned configuration marker across combat, not an exposed evolving PRNG state",
                "implementation_eligible": False,
            },
        }
    finally:
        fight_env.close()
        move_env.close()


def _repeatable(first: dict[str, Any], second: dict[str, Any]) -> None:
    if first != second:
        raise AssertionError("fresh paired NLE executions disagreed on exact public combat evidence")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, action="append", default=[])
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    seeds = args.seed or DEFAULT_SEEDS
    if len(set(seeds)) < 2:
        raise SystemExit("visible-target combat campaign requires at least two independent seeds")

    cases: list[dict[str, Any]] = []
    for seed in seeds:
        first = run_once(seed, character=args.character)
        if first is None:
            continue
        second = run_once(seed, character=args.character)
        if second is None:
            raise AssertionError("repeat execution lost a selected visible combat surface")
        _repeatable(first, second)
        cases.append(first)
    if len(cases) < 2:
        raise SystemExit("fewer than two source-visible non-pet combat cases; no multi-seed assertion")

    report = {
        "schema": "gamebench.nethack.visible_target_combat_report.v1",
        "status": "pass",
        "seeds": seeds,
        "cases": cases,
        "case_count": len(cases),
        "validity": {
            "repeatability": "same paired core/display seed exactly repeats public combat observations",
            "source_target_contract": "normal monster glyph plus glyph_to_mon/permonst; pet surfaces excluded",
            "implementation_eligible_cases": 0,
            "blocked": [
                "dynamic entity identity and pathing are not observable",
                "hostility is not observable",
                "target HP and NLE combat RNG state are not observable",
                "NLE get_seeds remains a configured seed marker after combat rather than exposing evolving PRNG state",
                "death horizon is therefore intentionally not explored",
            ],
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "pass", "cases": len(cases), "eligible": 0, "report": str(args.report.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
