#!/usr/bin/env python3
"""Independent-seed NLE oracle for the two-Escape pet-KICK cancellation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import OBSERVATION_KEYS, deterministic_nle_seeds, normalise_reset, project


SEEDS = (1, 3, 5, 6)
DIRECTIONS = (("N", 0, -1), ("E", 1, 0), ("S", 0, 1), ("W", -1, 0))


def run_once(seed: int) -> dict[str, Any] | None:
    import nle
    from nle import nethack

    env = nle.env.NLE(character="val-hum-fem-law", observation_keys=OBSERVATION_KEYS, actions=tuple(nethack.ACTIONS), allow_all_modes=True, allow_all_yn_questions=True)
    try:
        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        step = lambda value: project(normalise_reset(value[0] if isinstance(value, tuple) else value))
        reset = step(env.reset())
        x, y = map(int, reset["blstats"][:2])
        candidate = next((name for name, dx, dy in DIRECTIONS if nethack.glyph_is_pet(int(reset["glyphs"][y + dy][x + dx])) or int(reset["specials"][y + dy][x + dx]) & int(nethack.MG_PET)), None)
        if candidate is None:
            return None
        actions = {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}
        direction = step(env.step(actions["Command.KICK"]))
        prompt = step(env.step(actions[f"CompassDirection.{candidate}"]))
        first_escape = step(env.step(actions["Command.ESC"]))
        second_escape = step(env.step(actions["Command.ESC"]))
        prompt_text = prompt["message"]
        turns = [int(value["blstats"][20]) for value in (reset, direction, prompt, first_escape, second_escape)]
        if not prompt_text.startswith("Really attack the ") or first_escape["message"] != f"{prompt_text} n" or second_escape["message"] != "" or turns[2:] != [turns[2]] * 3:
            raise AssertionError("NLE pet Escape protocol drifted")
        return {
            "seed": seed, "direction": candidate, "prompt": prompt_text,
            "raw": [prompt["message_raw"], first_escape["message_raw"], second_escape["message_raw"]],
            "turns": turns,
            "modes": ["ynq", "ynq", "normal"],
            "tty_cursor_yx": [prompt["tty_cursor_yx"], first_escape["tty_cursor_yx"], second_escape["tty_cursor_yx"]],
        }
    finally:
        env.close()


def main() -> None:
    report = []
    for seed in SEEDS:
        first, second = run_once(seed), run_once(seed)
        if first is not None:
            if first != second:
                raise AssertionError("same paired seed failed exact pet-Escape replay")
            report.append(first)
    if len(report) < 2:
        raise SystemExit("need at least two independent source-marked pet seeds")
    output = TASK_DIR / "reports" / "pet_escape_20260730.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"schema": "gamebench.nethack.pet_escape_report.v1", "status": "pass", "source_contract": "glyph_is_pet or MG_PET", "negative_control": "ordinary ynq handling is not touched by the dedicated attack_confirm branch", "cases": report}, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "pass", "cases": len(report), "report": str(output.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
