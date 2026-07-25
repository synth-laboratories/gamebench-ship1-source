"""Hidden flawed policy — reuses colors within a row."""

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
    board = public["board"]
    placed = {tuple(cell) for cell in public.get("frogs", [])}
    used_by_row: dict[int, set[str]] = {}
    for row, col in placed:
        used_by_row.setdefault(row, set()).add(board[row][col])
    for row in range(len(board)):
        for col in range(len(board)):
            if (row, col) in placed:
                continue
            color = board[row][col]
            if color in used_by_row.get(row, set()):
                return {
                    "actions": [{"kind": "place_frog", "row": row, "col": col}],
                    "policy_reason": "color repeat blind",
                }
    return {
        "actions": [{"kind": "place_frog", "row": 0, "col": 0}],
        "policy_reason": "color repeat fallback",
    }
