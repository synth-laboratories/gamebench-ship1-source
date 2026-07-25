"""Hidden flawed policy — fills rows out of order."""

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
    placed = {tuple(cell) for cell in public.get("frogs", [])}
    board = public["board"]
    n = len(board)
    order = list(range(n - 1, -1, -1))
    for row in order:
        for col in range(n):
            if (row, col) in placed:
                continue
            return {
                "actions": [{"kind": "place_frog", "row": row, "col": col}],
                "policy_reason": "row order skip",
            }
    return {"actions": [{"kind": "submit"}], "policy_reason": "submit after row order skip"}
