"""Stable FrogsGame code-policy baseline."""

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
    public = readout["public"]
    placed = {tuple(cell) for cell in public.get("frogs", [])}
    for row, col in _solve(public["board"]):
        if (row, col) not in placed:
            return {
                "actions": [{"kind": "place_frog", "row": row, "col": col}],
                "policy_reason": f"place ({row},{col})",
            }
    return {"actions": [{"kind": "submit"}], "policy_reason": "submit complete board"}


def _solve(board: list[list[str]]) -> list[tuple[int, int]]:
    n = len(board)
    solution: list[tuple[int, int]] = []

    def search(row: int, used_cols: set[int], used_colors: set[str], positions: list[tuple[int, int]]) -> bool:
        if row == n:
            solution.extend(positions)
            return True
        for col in range(n):
            color = board[row][col]
            if col in used_cols or color in used_colors:
                continue
            if any(abs(row - r) <= 1 and abs(col - c) <= 1 for r, c in positions):
                continue
            if search(row + 1, used_cols | {col}, used_colors | {color}, [*positions, (row, col)]):
                return True
        return False

    search(0, set(), set(), [])
    return solution
