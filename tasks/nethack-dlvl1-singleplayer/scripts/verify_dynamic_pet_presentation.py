#!/usr/bin/env python3
"""Probe the bounded source-visible part of NLE's starting-pet cadence.

This is intentionally not a monster tracker. NLE exposes a pet predicate and
the ``MG_PET`` presentation bit, but not an entity id, private speed counter,
inventory, target selection, or path. A same-pixel glyph in adjacent frames
is consequently called *presentation continuity* only. The sole positive gold
contract this tool may establish is the exact stationary WAIT/SEARCH hold of
the reset pet pixel. Later transitions are evidence about what must remain
unmodelled until a causal source is available.
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


DEFAULT_SEEDS = list(range(24))
STATIONARY_ACTIONS = ("Command.SEARCH", "MiscDirection.WAIT")
PASSABLE_CMAP_CHARS = frozenset(".#<>_{}~")


def source_pet_cells(snapshot: dict[str, Any], nethack: Any) -> list[dict[str, Any]]:
    """Return exactly the public NLE pet-predicate/MG_PET surface subset."""

    cells: list[dict[str, Any]] = []
    glyphs = snapshot.get("glyphs", [])
    chars = snapshot.get("chars", [])
    colors = snapshot.get("colors", [])
    specials = snapshot.get("specials", [])
    for y, row in enumerate(glyphs if isinstance(glyphs, list) else []):
        if not isinstance(row, list):
            continue
        for x, raw_glyph in enumerate(row):
            glyph = int(raw_glyph)
            special = int(specials[y][x]) if y < len(specials) and isinstance(specials[y], list) and x < len(specials[y]) else 0
            if not (bool(nethack.glyph_is_pet(glyph)) or special & int(nethack.MG_PET)):
                continue
            char = chr(int(chars[y][x])) if y < len(chars) and isinstance(chars[y], list) and x < len(chars[y]) else "\0"
            color = int(colors[y][x]) if y < len(colors) and isinstance(colors[y], list) and x < len(colors[y]) else 0
            cells.append({
                "x": x, "y": y, "char": char, "glyph": glyph, "color": color, "special": special,
                "source_status": {
                    "glyph_is_pet": bool(nethack.glyph_is_pet(glyph)),
                    "specials_mg_pet": bool(special & int(nethack.MG_PET)),
                },
                "identity_status": "unavailable_from_nle_presentation",
            })
    return sorted(cells, key=lambda cell: (cell["y"], cell["x"], cell["glyph"]))


def _hero(snapshot: dict[str, Any]) -> tuple[int, int] | None:
    stats = snapshot.get("blstats", [])
    return (int(stats[0]), int(stats[1])) if isinstance(stats, list) and len(stats) >= 2 else None


def _prior_destination_surface(snapshot: dict[str, Any], x: int, y: int, nethack: Any) -> dict[str, Any]:
    """Classify only a directly rendered prior destination; otherwise unknown."""

    glyphs, chars = snapshot.get("glyphs", []), snapshot.get("chars", [])
    if not (isinstance(glyphs, list) and 0 <= y < len(glyphs) and isinstance(glyphs[y], list) and 0 <= x < len(glyphs[y])):
        return {"status": "unjudgeable", "reason": "outside_observed_plane"}
    glyph = int(glyphs[y][x])
    char = chr(int(chars[y][x])) if isinstance(chars, list) and y < len(chars) and isinstance(chars[y], list) and x < len(chars[y]) else "\0"
    if bool(nethack.glyph_is_cmap(glyph)):
        return {
            "status": "direct_static_surface",
            "char": char,
            "glyph": glyph,
            "passable_by_visible_cmap": char in PASSABLE_CMAP_CHARS,
        }
    return {"status": "unjudgeable", "reason": "prior_destination_is_presentation_or_hero_overlay"}


def classify_transition(before: dict[str, Any], after: dict[str, Any], *, nethack: Any) -> dict[str, Any]:
    """Describe a source presentation transition without assigning entity ids."""

    prior = source_pet_cells(before, nethack)
    current = source_pet_cells(after, nethack)
    result: dict[str, Any] = {
        "before_source_pet_cells": prior,
        "after_source_pet_cells": current,
        "time_delta": (
            int(after["blstats"][20]) - int(before["blstats"][20])
            if isinstance(before.get("blstats"), list) and isinstance(after.get("blstats"), list)
            and len(before["blstats"]) > 20 and len(after["blstats"]) > 20
            else None
        ),
        "identity_contract": "presentation continuity only; NLE supplies no stable entity id",
    }
    if len(prior) != 1 or len(current) != 1:
        result["status"] = "unjudgeable"
        result["reason"] = "zero_or_multiple_source_pet_pixels"
        return result
    source, target = prior[0], current[0]
    same_presentation = (source["char"], source["glyph"], source["color"]) == (target["char"], target["glyph"], target["color"])
    if not same_presentation:
        result["status"] = "unjudgeable"
        result["reason"] = "source_pet_presentation_changed"
        return result
    dx, dy = int(target["x"]) - int(source["x"]), int(target["y"]) - int(source["y"])
    result.update({
        "status": "presentation_continuity_only",
        "from": source,
        "to": target,
        "displacement": {"dx": dx, "dy": dy, "chebyshev": max(abs(dx), abs(dy))},
        "prior_destination_surface": _prior_destination_surface(before, int(target["x"]), int(target["y"]), nethack),
        "destination_is_hero": _hero(after) == (int(target["x"]), int(target["y"])),
    })
    return result


def _actions(env: Any) -> dict[str, int]:
    return {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}


def _projected_input_mode(snapshot: dict[str, Any]) -> str:
    """Fail closed on a source screen that no longer accepts SEARCH/WAIT."""

    tty = "\n".join(
        "".join(chr(int(cell)) for cell in row if isinstance(cell, int))
        for row in snapshot.get("tty_chars", [])
        if isinstance(row, list)
    ).lower()
    text = f"{tty}\n{snapshot.get('message', '')}".lower()
    if "--more--" in text:
        return "more"
    if "in what direction" in text or "what direction" in text:
        return "direction"
    if "[yn" in text or "(y/n" in text:
        return "ynq"
    if "(end)" in text:
        return "inventory_display"
    return "normal"


def _run_once(seed: int, action_name: str, *, steps: int) -> dict[str, Any]:
    try:
        import nle
        from nle import nethack
    except ModuleNotFoundError as error:  # pragma: no cover - CLI dependency guard
        raise RuntimeError("NLE 0.9.0 is required for the live dynamic-pet probe") from error
    env = nle.env.NLE(
        character="val-hum-fem-law", observation_keys=OBSERVATION_KEYS, actions=tuple(nethack.ACTIONS),
        allow_all_modes=True, allow_all_yn_questions=True,
    )
    try:
        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        current = project(normalise_reset(env.reset()))
        actions = _actions(env)
        transitions: list[dict[str, Any]] = []
        for index in range(steps):
            mode = _projected_input_mode(current)
            if mode != "normal":
                transitions.append({"primary_step": index + 1, "status": "unjudgeable", "reason": f"input_mode_{mode}_before_first_turn_action"})
                break
            next_snapshot = project(env.step(actions[action_name])[0])
            transitions.append({"primary_step": index + 1, **classify_transition(current, next_snapshot, nethack=nethack)})
            current = next_snapshot
        return {"seed": seed, "action": action_name, "transitions": transitions}
    finally:
        env.close()


def build_report(*, seeds: list[int], steps: int) -> dict[str, Any]:
    if len(set(seeds)) < 8:
        raise ValueError("dynamic pet probe requires at least eight independent seeds")
    if steps < 2:
        raise ValueError("dynamic pet probe requires at least two stationary turns")
    cases: list[dict[str, Any]] = []
    for action_name in STATIONARY_ACTIONS:
        for seed in seeds:
            first = _run_once(seed, action_name, steps=steps)
            second = _run_once(seed, action_name, steps=steps)
            if first != second:
                raise AssertionError(f"same paired NLE seed was not repeatable for {action_name} seed {seed}")
            cases.append(first)
    first_turns = [case["transitions"][0] for case in cases if case["transitions"]]
    retained = [
        transition for transition in first_turns
        if transition.get("status") == "presentation_continuity_only" and transition.get("displacement", {}).get("chebyshev") == 0
        and transition.get("time_delta") == 1
    ]
    later = [transition for case in cases for transition in case["transitions"][1:] if transition.get("status") == "presentation_continuity_only"]
    moved = [transition for transition in later if int(transition.get("displacement", {}).get("chebyshev", 0)) > 0]
    movement_signatures = sorted({(entry["displacement"]["dx"], entry["displacement"]["dy"]) for entry in moved})
    movement_seeds = sorted({case["seed"] for case in cases for entry in case["transitions"][1:] if entry in moved})
    source_legal = [entry for entry in moved if not entry["destination_is_hero"] and entry["prior_destination_surface"].get("status") == "direct_static_surface"]
    first_turn_contract = len(retained) == len(cases)
    # The later variability is a negative guard: a fixed source-coordinate or
    # future-tape schedule would be an invalid inference, even if it happened
    # to improve a handful of fuzz cases.
    variable_later_motion = len(movement_signatures) >= 2 and len(movement_seeds) >= 4
    status = "pass" if first_turn_contract and variable_later_motion else "insufficient_or_contradictory_source_evidence"
    return {
        "schema": "gamebench.nethack.dynamic_pet_presentation_probe.v1",
        "status": status,
        "source_contract": {
            "positive": "glyph_is_pet(glyph) or specials & MG_PET; exact stationary WAIT/SEARCH screen pixel hold",
            "negative": "no stable id, path, speed counter, blocking state, inventory, combat target, injury RNG, or future coordinate is inferred",
        },
        "seeds": seeds,
        "stationary_actions": list(STATIONARY_ACTIONS),
        "steps_per_case": steps,
        "case_count": len(cases),
        "stationary_first_turn": {"cases": len(cases), "retained_exactly": len(retained), "all_retained": first_turn_contract},
        "later_presentation_motion": {
            "continuity_candidates": len(later), "moved_candidates": len(moved), "distinct_displacements": movement_signatures,
            "distinct_seeds": movement_seeds, "direct_visible_destination_candidates": len(source_legal),
            "variable_across_seeds": variable_later_motion,
        },
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="append", type=int, default=[])
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(seeds=args.seed or DEFAULT_SEEDS, steps=args.steps)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "cases": report["case_count"], "report": str(args.report.resolve())}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
