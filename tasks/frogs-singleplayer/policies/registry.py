"""Deterministic FrogsGame policy registry."""

from __future__ import annotations

from typing import Any


def choose_action(policy_id: str, observation: dict[str, Any], *, seed: int = 0, ply: int = 0) -> dict[str, Any]:
    if policy_id in {"solver_v1", "baseline_v1"}:
        return solver_policy(observation, seed=seed, ply=ply)
    if policy_id == "submit_now_v1":
        return {"kind": "submit"}
    raise KeyError(f"unknown frogs policy_id: {policy_id}")


def solver_policy(observation: dict[str, Any], *, seed: int = 0, ply: int = 0) -> dict[str, Any]:
    public = observation["public"]
    board = public["board"]
    placed = {tuple(cell) for cell in public.get("frogs", [])}
    solution = _solve(board)
    for row, col in solution:
        if (row, col) not in placed:
            return {"kind": "place_frog", "row": row, "col": col}
    return {"kind": "submit"}


def _solve(board: list[list[str]]) -> list[tuple[int, int]]:
    n = len(board)
    rows: list[tuple[int, int]] = []

    def search(row: int, used_cols: set[int], used_colors: set[str], positions: list[tuple[int, int]]) -> bool:
        if row == n:
            rows.extend(positions)
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

    if not search(0, set(), set(), []):
        return []
    return rows
