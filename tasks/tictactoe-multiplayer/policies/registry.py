"""Deterministic Tic-Tac-Toe rollout policies (registry)."""

from __future__ import annotations

import hashlib
from typing import Any


WIN_LINES = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)

CORNERS = (0, 2, 6, 8)
EDGES = (1, 3, 5, 7)


def legal_positions(state: dict[str, Any]) -> list[int]:
    return [index for index, value in enumerate(state["board"]) if not value]


def winning_position(board: list[str], player: str) -> int | None:
    for line in WIN_LINES:
        values = [board[index] for index in line]
        if values.count(player) == 2 and values.count("") == 1:
            return line[values.index("")]
    return None


def opponent(player: str) -> str:
    return "O" if player == "X" else "X"


def seeded_order(values: list[int], seed: int, ply: int, namespace: str) -> list[int]:
    return sorted(
        values,
        key=lambda value: hashlib.sha256(f"{namespace}:{seed}:{ply}:{value}".encode()).hexdigest(),
    )


def choose_position(policy_id: str, state: dict[str, Any], seed: int = 0, ply: int = 0) -> int:
    player = state["turn"]
    board = state["board"]
    legal = legal_positions(state)
    if not legal:
        raise ValueError("no legal positions")

    if policy_id == "first_legal_v1":
        return legal[0]
    if policy_id == "last_legal_v1":
        return legal[-1]
    if policy_id == "center_first_v1":
        return 4 if 4 in legal else legal[0]
    if policy_id == "corner_first_v1":
        return next((pos for pos in CORNERS if pos in legal), legal[0])
    if policy_id == "edge_first_v1":
        return next((pos for pos in EDGES if pos in legal), legal[0])
    if policy_id == "win_block_center_v1":
        return (
            winning_position(board, player)
            or winning_position(board, opponent(player))
            or (4 if 4 in legal else None)
            or next((pos for pos in CORNERS if pos in legal), None)
            or legal[0]
        )
    if policy_id == "block_win_center_v1":
        return (
            winning_position(board, opponent(player))
            or winning_position(board, player)
            or (4 if 4 in legal else None)
            or next((pos for pos in CORNERS if pos in legal), None)
            or legal[0]
        )
    if policy_id == "mirror_preferred_v1":
        for pos in (8, 6, 2, 0, 4, 7, 5, 3, 1):
            if pos in legal:
                return pos
    if policy_id == "seeded_legal_v1":
        return seeded_order(legal, seed, ply, "tictactoe.seeded_legal_v1")[0]
    if policy_id == "seeded_win_block_v1":
        return (
            winning_position(board, player)
            or winning_position(board, opponent(player))
            or seeded_order(legal, seed, ply, "tictactoe.seeded_win_block_v1")[0]
        )
    raise ValueError(f"unknown policy_id: {policy_id}")


def choose_action(policy_id: str, state: dict[str, Any], seed: int = 0, ply: int = 0) -> dict[str, Any]:
    return {"player": state["turn"], "position": choose_position(policy_id, state, seed, ply)}
