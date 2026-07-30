"""Baseline symbolic code policy for multiplayer Tic-Tac-Toe sweeps."""

from __future__ import annotations

from typing import Any

from policies.registry import choose_position


def choose_action(public: dict[str, Any], agent_id: str, seed: int, ply: int) -> dict[str, Any]:
    position = choose_position(
        "win_block_center_v1",
        {
            "board": list(public["board"]),
            "turn": public["turn"],
            "winner": public.get("winner"),
        },
        seed=seed,
        ply=ply,
    )
    return {"agent_id": agent_id, "kind": "place", "position": position}
