"""Monty policy module — win/block/center heuristic."""

from __future__ import annotations

from typing import Any

from registry import choose_action as registry_choose_action


def choose_action(public: dict[str, Any], seed: int, ply: int) -> dict[str, Any]:
    state = {
        "board": list(public["board"]),
        "turn": public["turn"],
        "winner": public.get("winner"),
    }
    return registry_choose_action("win_block_center_v1", state, seed=seed, ply=ply)
