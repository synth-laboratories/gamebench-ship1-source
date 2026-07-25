"""Hidden flawed policy — places frogs diagonally adjacent."""

from __future__ import annotations

from typing import Any


def choose_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[dict[str, Any]],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    del observation_text, engine, seed, ply
    public = readout["public"]
    placed = [tuple(cell) for cell in public.get("frogs", [])]
    board = public["board"]
    n = len(board)
    if placed:
        anchor = placed[-1]
        for dr, dc in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            row, col = anchor[0] + dr, anchor[1] + dc
            if 0 <= row < n and 0 <= col < n and (row, col) not in placed:
                return {
                    "actions": [{"kind": "place_frog", "row": row, "col": col}],
                    "policy_reason": "diagonal adjacency blind",
                }
    return {
        "actions": [{"kind": "place_frog", "row": 0, "col": 0}],
        "policy_reason": "diagonal seed placement",
    }
