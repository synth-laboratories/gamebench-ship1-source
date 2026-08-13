#!/usr/bin/env python3
"""Capture repeatable seeded KICK outcomes against raw-visible targets only.

This diagnostic never infers an NLE entity identity from a presentation glyph.
It records static floor/wall/door targets separately from a visible overlay,
and compares two fresh executions of the same seeded two-key interaction using
the observable-outcome schema.
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

from scripts.capture_nle_fixture import OBSERVATION_KEYS, STATIC_TERRAIN_CHARS, deterministic_nle_seeds, normalise_reset, project
from scripts.kick_rng_assertions import direct_wall_message_assertion, wall_kick_eligibility
from scripts.outcome_assertions import seeded_outcome_report, transition_outcome
from shared.task_resolve import BLSTATS_FIELDS


PROMPT_RAW_TEXT = "In what direction? "
CARDINALS = (("N", 0, -1), ("E", 1, 0), ("S", 0, 1), ("W", -1, 0))
DEFAULT_SEEDS = [*range(12), 20261040, 20260315, 20260316, 20260061]


def expected_raw(text: str, width: int) -> list[int]:
    bytes_ = list(text.encode("ascii"))
    if len(bytes_) > width:
        raise ValueError("text does not fit the NLE message buffer")
    return bytes_ + [0] * (width - len(bytes_))


def _cell(projection: dict[str, Any], x: int, y: int) -> tuple[str, int, int]:
    chars = projection.get("chars", [])
    glyphs = projection.get("glyphs", [])
    colors = projection.get("colors", [])
    if not (isinstance(chars, list) and 0 <= y < len(chars) and isinstance(chars[y], list) and 0 <= x < len(chars[y])):
        return "", 0, 0
    char = chr(int(chars[y][x]))
    glyph = int(glyphs[y][x]) if isinstance(glyphs, list) and y < len(glyphs) and isinstance(glyphs[y], list) and x < len(glyphs[y]) else 0
    color = int(colors[y][x]) if isinstance(colors, list) and y < len(colors) and isinstance(colors[y], list) and x < len(colors[y]) else 0
    return char, glyph, color


def target_class(char: str) -> str | None:
    """Classify only what the raw NLE presentation itself establishes."""

    if char == ".":
        return "empty_floor"
    if char in "|-":
        return "wall"
    if char == "+":
        return "door"
    if char and char not in STATIC_TERRAIN_CHARS and char not in " @":
        return "visible_entity_overlay"
    return None


def _step_observation(value: Any) -> dict[str, Any]:
    return normalise_reset(value[0] if isinstance(value, tuple) else value)


def _actions(env: Any) -> dict[str, int]:
    return {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}


def probe_public_seed_api(*, character: str) -> dict[str, Any]:
    """Show whether NLE exposes an evolving RNG state rather than its seed.

    ``get_seeds`` is intentionally sampled before and after history plus the
    two KICK inputs.  If a future NLE version changes this API contract, this
    verifier stops rather than silently treating a configuration seed as a
    state snapshot.
    """

    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:  # pragma: no cover - CLI dependency guard
        raise RuntimeError("NLE 0.9.0 is required for the public RNG API probe") from error
    env = nle.env.NLE(
        character=character,
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    try:
        configured = tuple(int(value) for value in env.seed(core=123, disp=456, reseed=False))
        env.reset()
        actions = _actions(env)
        observations = [{"boundary": "reset", "get_seeds": list(env.get_seeds())}]
        for action_name in ("Command.SEARCH", "Command.SEARCH", "Command.KICK", "CompassDirection.W"):
            env.step(actions[action_name])
            observations.append({"boundary": action_name, "get_seeds": list(env.get_seeds())})
        if any(tuple(entry["get_seeds"]) != configured for entry in observations):
            raise AssertionError("NLE get_seeds changed during execution; re-audit RNG authority before judging injury")
        return {
            "status": "configuration_only",
            "configured": list(configured),
            "observations": observations,
            "conclusion": "get_seeds returns the configured seeds unchanged, not the advancing internal RNG state",
        }
    finally:
        env.close()


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _tty_evidence(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Record terminal planes by exact content hash, not a lossy text scrape."""

    before_planes = {key: before.get(key, []) for key in ("tty_chars", "tty_colors", "tty_cursor_yx")}
    after_planes = {key: after.get(key, []) for key in ("tty_chars", "tty_colors", "tty_cursor_yx")}
    return {
        "before": {key: _digest(value) for key, value in before_planes.items()},
        "after": {key: _digest(value) for key, value in after_planes.items()},
        "exact_replay": False,
    }


def _named_stat_deltas(outcome: dict[str, Any]) -> list[dict[str, int | str]]:
    result: list[dict[str, int | str]] = []
    for entry in outcome.get("blstats_deltas", []):
        if not isinstance(entry, dict):
            continue
        slot = int(entry.get("slot", -1))
        result.append({
            "field": BLSTATS_FIELDS[slot] if 0 <= slot < len(BLSTATS_FIELDS) else f"slot_{slot}",
            "before": int(entry.get("before", 0)),
            "after": int(entry.get("after", 0)),
            "delta": int(entry.get("delta", 0)),
        })
    return result


def run_once(
    seed: int,
    *,
    wanted_class: str,
    character: str,
    action_history: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:  # pragma: no cover - command-only guard
        raise RuntimeError("NLE 0.9.0 is required for the live visible-target KICK campaign") from error

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
        x, y = (int(reset["blstats"][0]), int(reset["blstats"][1]))
        candidate: tuple[str, int, int, str, int, int] | None = None
        for direction, dx, dy in CARDINALS:
            char, glyph, color = _cell(reset, x + dx, y + dy)
            if target_class(char) == wanted_class:
                candidate = (direction, dx, dy, char, glyph, color)
                break
        if candidate is None:
            return None
        direction, dx, dy, char, glyph, color = candidate
        actions = _actions(env)
        history_snapshots: list[dict[str, Any]] = []
        current = reset
        for action_name in action_history:
            if action_name not in actions:
                raise AssertionError(f"history action is absent from pinned NLE action table: {action_name}")
            current = project(_step_observation(env.step(actions[action_name])))
            history_snapshots.append(current)
        history_x, history_y = (int(current["blstats"][0]), int(current["blstats"][1]))
        current_char, current_glyph, current_color = _cell(current, history_x + dx, history_y + dy)
        if (history_x, history_y) != (x, y) or target_class(current_char) != wanted_class:
            # The action history has changed the causal target.  Do not reuse
            # its original label as evidence about a different source state.
            return None
        prompt = project(_step_observation(env.step(actions["Command.KICK"])))
        prompt_raw = [int(value) for value in prompt["message_raw"]]
        if prompt_raw != expected_raw(PROMPT_RAW_TEXT, len(prompt_raw)):
            raise AssertionError("KICK prompt raw bytes differ from the pinned NLE prompt")
        if prompt["blstats"] != current["blstats"]:
            raise AssertionError("KICK direction prompt consumed a turn or changed stats")
        result = project(_step_observation(env.step(actions[f"CompassDirection.{direction}"])))
        turns = [int(reset["blstats"][20]), *(int(snapshot["blstats"][20]) for snapshot in history_snapshots), int(prompt["blstats"][20]), int(result["blstats"][20])]
        if int(prompt["blstats"][20]) != int(current["blstats"][20]):
            raise AssertionError(f"KICK direction prompt consumed a turn {turns!r}")
        target = {
            "class": wanted_class,
            "x": history_x + dx,
            "y": history_y + dy,
            "direction": direction,
            "char": current_char,
            "glyph": current_glyph,
            "color": current_color,
            "provenance": "observed_surface_static" if wanted_class != "visible_entity_overlay" else "observed_surface_overlay",
            "identity_status": "not_applicable" if wanted_class != "visible_entity_overlay" else "unavailable_from_nle_presentation",
        }
        outcome = transition_outcome(prompt, result)
        tty = _tty_evidence(prompt, result)
        return {
            "seed": seed,
            "target": target,
            "action_history": list(action_history),
            "pre_kick_turn": int(current["blstats"][20]),
            "reset_turn": int(reset["blstats"][20]),
            "prompt": {"message": prompt["message"], "message_raw": prompt_raw},
            "turns": turns,
            "outcome": outcome,
            "named_stat_deltas": _named_stat_deltas(outcome),
            "tty": tty,
            "eligibility": wall_kick_eligibility(
                target=target,
                reset_turn=int(reset["blstats"][20]),
                pre_kick_turn=int(current["blstats"][20]),
                action_history=list(action_history),
            ),
            "snapshots": [reset, *history_snapshots, prompt, result],
            "actions": [
                *({"step": index + 1, "input_mode": "normal", "action_name": action_name} for index, action_name in enumerate(action_history)),
                {"step": len(action_history) + 1, "input_mode": "normal", "action_name": "Command.KICK"},
                {"step": len(action_history) + 2, "input_mode": "direction", "action_name": f"CompassDirection.{direction}"},
            ],
        }
    finally:
        env.close()


def _repeatable(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    prompt_equal = first["prompt"] == second["prompt"]
    outcome_report = seeded_outcome_report(
        first["snapshots"], second["snapshots"], first["actions"], through_step=len(first["actions"])
    )
    tty_equal = first["tty"] == second["tty"]
    if not prompt_equal or outcome_report["status"] != "pass" or not tty_equal:
        raise AssertionError("fresh NLE runs with identical seeds did not reproduce the exact KICK observation")
    first["tty"]["exact_replay"] = True
    return {"prompt_equal": prompt_equal, "tty_equal": tty_equal, "outcome": outcome_report}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, action="append", default=[])
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    seeds = args.seed or DEFAULT_SEEDS
    if len(set(seeds)) < 2:
        raise SystemExit("visible-target KICK campaign requires at least two distinct seeds")

    cases: list[dict[str, Any]] = []
    for wanted_class in ("empty_floor", "wall", "door", "visible_entity_overlay"):
        for seed in seeds:
            first = run_once(seed, wanted_class=wanted_class, character=args.character)
            if first is None:
                continue
            second = run_once(seed, wanted_class=wanted_class, character=args.character)
            if second is None:
                raise AssertionError("the same seeded raw-visible target disappeared before a repeated run")
            repeatability = _repeatable(first, second)
            cases.append({
                "seed": seed,
                "target": first["target"],
                "action_history": first["action_history"],
                "reset_turn": first["reset_turn"],
                "pre_kick_turn": first["pre_kick_turn"],
                "prompt": first["prompt"],
                "turns": first["turns"],
                "outcome": first["outcome"],
                "named_stat_deltas": first["named_stat_deltas"],
                "tty": first["tty"],
                "eligibility": first["eligibility"],
                "repeatability": repeatability,
            })
    history_cases: list[dict[str, Any]] = []
    # WAIT is a deliberately minimal consumed-turn perturbation.  It preserves
    # the hero's location and wall target, while proving that dynamic actions
    # and random-call chronology can change the later KICK result.
    for seed in seeds:
        first = run_once(seed, wanted_class="wall", character=args.character, action_history=("MiscDirection.WAIT",))
        if first is None:
            continue
        second = run_once(seed, wanted_class="wall", character=args.character, action_history=("MiscDirection.WAIT",))
        if second is None:
            raise AssertionError("the same seeded history changed its wall target before repeat")
        repeatability = _repeatable(first, second)
        history_cases.append({
            "seed": seed,
            "target": first["target"],
            "action_history": first["action_history"],
            "reset_turn": first["reset_turn"],
            "pre_kick_turn": first["pre_kick_turn"],
            "prompt": first["prompt"],
            "turns": first["turns"],
            "outcome": first["outcome"],
            "named_stat_deltas": first["named_stat_deltas"],
            "tty": first["tty"],
            "eligibility": first["eligibility"],
            "repeatability": repeatability,
        })
    by_class = {name: sum(case["target"]["class"] == name for case in cases) for name in ("empty_floor", "wall", "door", "visible_entity_overlay")}
    if by_class["wall"] < 2:
        raise SystemExit("fewer than two raw-visible wall KICK cases; no multi-seed wall assertion")
    direct_wall_assertions = [direct_wall_message_assertion(case) for case in cases if case["target"]["class"] == "wall"]
    if any(assertion["status"] != "pass" for assertion in direct_wall_assertions):
        raise AssertionError("immediate source-eligible wall KICK did not satisfy its exact message/TTY/turn contract")
    if len(history_cases) < 2:
        raise SystemExit("fewer than two repeatable WAIT-before-wall-KICK cases; cannot establish action-history boundary")
    direct_by_seed = {int(case["seed"]): case for case in cases if case["target"]["class"] == "wall"}
    history_differences = []
    for case in history_cases:
        direct = direct_by_seed.get(int(case["seed"]))
        if direct is None:
            continue
        history_differences.append({
            "seed": case["seed"],
            "outcome_changed": direct["outcome"] != case["outcome"],
            "direct_named_stat_deltas": direct["named_stat_deltas"],
            "history_named_stat_deltas": case["named_stat_deltas"],
            "direct_message_raw": direct["outcome"]["message_raw"],
            "history_message_raw": case["outcome"]["message_raw"],
        })
    if not any(entry["outcome_changed"] for entry in history_differences):
        raise AssertionError("WAIT history did not change any source wall-KICK outcome; insufficient causal-boundary evidence")
    public_seed_api = probe_public_seed_api(character=args.character)
    report = {
        "schema": "gamebench.nethack.visible_target_kick_report.v2",
        "status": "pass",
        "seeds": seeds,
        "cases_by_target_class": by_class,
        "cases": cases,
        "action_history_cases": history_cases,
        "direct_wall_assertions": direct_wall_assertions,
        "action_history_dependence": {
            "status": "observed",
            "history": ["MiscDirection.WAIT"],
            "changed_case_count": sum(bool(entry["outcome_changed"]) for entry in history_differences),
            "cases": history_differences,
            "conclusion": "a prior consumed turn can change injury/stat deltas and append dynamic-actor output; do not extrapolate the reset-wall exact message to later histories",
        },
        "rng_authority": {
            "oracle_capture_inputs": ["seeded core/display values passed to env.seed", "exact action tape", "exact public observations"],
            "public_task_runtime": ["materialized reset level state", "task seed", "action history", "public observations"],
            "public_seed_api_probe": public_seed_api,
            "not_available": ["NLE internal RNG state", "random-call chronology", "dynamic actor scheduler state"],
            "conclusion": "injury/stat behavior is unjudgeable; an LCG or seed table would not be source-authoritative",
        },
        "implementation_scope": "only source-eligible immediate static-wall raw/message/TTY/turn behavior is deterministic; injury/stat and dynamic output remain unjudgeable",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "pass", "cases": len(cases), "cases_by_target_class": by_class, "report": str(args.report.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
