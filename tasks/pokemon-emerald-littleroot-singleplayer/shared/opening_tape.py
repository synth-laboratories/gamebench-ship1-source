"""Expand the committed title→met_rival May opening replay into flat steps."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

TASK_ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = TASK_ROOT / "fixtures" / "gold" / "replays" / "title_to_met_rival_may.json"

# First flat step index at bedroom clock tile (3,2) on May 2F (clock A presses).
BEDROOM_CLOCK_TAPE_INDEX = 123


def expand_program(program: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in program:
        if "repeat" in item:
            for _ in range(int(item["repeat"])):
                out.extend(expand_program(list(item.get("steps") or [])))
        else:
            out.append({"action": str(item["action"]), "frames": int(item["frames"])})
    return out


@lru_cache(maxsize=1)
def may_opening_steps() -> tuple[dict[str, Any], ...]:
    payload = json.loads(REPLAY_PATH.read_text())
    return tuple(expand_program(list(payload.get("program") or [])))


def remaining_tape(cursor: int, *, start: int = 0) -> list[dict[str, Any]]:
    steps = may_opening_steps()
    idx = max(int(cursor), int(start))
    return [dict(step) for step in steps[idx:]]
