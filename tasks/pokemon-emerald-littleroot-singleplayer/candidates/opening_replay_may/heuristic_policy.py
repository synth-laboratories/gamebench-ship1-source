"""Open-loop May opening replay (title → met_rival). Weak on other checkpoints."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SHARED = Path(__file__).resolve().parents[2] / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from opening_tape import BEDROOM_CLOCK_TAPE_INDEX, may_opening_steps

CHUNK = 32


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[str],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    checkpoint = str(readout.get("checkpoint") or "")
    world = readout.get("world") or {}
    phase = str(world.get("phase") or "")
    if phase == "met_rival":
        return {"actions": [{"action": "noop", "frames": 1}], "policy_reason": "done"}

    mem = session.setdefault("opening_replay_may", {})
    if "cursor" not in mem:
        if checkpoint == "title_menu":
            mem["cursor"] = 0
        elif checkpoint == "bedroom_idle":
            mem["cursor"] = BEDROOM_CLOCK_TAPE_INDEX
            # walk to clock first via short prefix stored as pending
            mem["prefix"] = [
                {"action": "right", "frames": 16},
                {"action": "right", "frames": 16},
                {"action": "down", "frames": 16},
                {"action": "up", "frames": 1},
            ]
        else:
            mem["cursor"] = 0
            mem["prefix"] = [{"action": "a", "frames": 1}]

    prefix = list(mem.get("prefix") or [])
    if prefix:
        step = prefix.pop(0)
        mem["prefix"] = prefix
        return {"actions": [step], "policy_reason": "prefix"}

    steps = may_opening_steps()
    cursor = int(mem["cursor"])
    chunk = [dict(s) for s in steps[cursor : cursor + CHUNK]]
    mem["cursor"] = cursor + len(chunk)
    if not chunk:
        return {"actions": [{"action": "noop", "frames": 1}], "policy_reason": "tape end"}
    return {"actions": chunk, "policy_reason": f"tape@{cursor}"}
