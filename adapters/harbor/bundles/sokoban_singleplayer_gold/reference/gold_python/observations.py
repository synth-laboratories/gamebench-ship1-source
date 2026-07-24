"""Sokoban observations and symbolic readouts."""

from __future__ import annotations

import hashlib
from typing import Any

from task_resolve import grid_to_ascii


ACTIONS = ["up", "down", "left", "right"]


def ascii_board(room_fixed: list[list[int]], player: tuple[int, int], boxes: set[tuple[int, int]]) -> str:
    return "\n".join(grid_to_ascii(room_fixed, player, boxes))


def grid_hash(room_state: list[list[int]]) -> str:
    payload = "|".join(",".join(str(cell) for cell in row) for row in room_state)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def project_readout(engine: Any) -> dict[str, Any]:
    private = engine.private.to_dict()
    if engine.resolved is not None:
        private["max_steps"] = engine.resolved.max_steps
    return {
        "ascii": ascii_board(engine.room_fixed, engine.player, engine.boxes),
        "valid_actions": engine.valid_actions(),
        "grid_hash": grid_hash(engine.room_state),
        "public": engine.public.to_dict(),
        "private": private,
    }
