"""Canonical tic-tac-toe board primitives (multiplayer gold owns this module)."""

from __future__ import annotations

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

AGENT_IDS = ("agent_0", "agent_1")
AGENT_MARKS = {"agent_0": "X", "agent_1": "O"}
MARK_TO_AGENT = {"X": "agent_0", "O": "agent_1"}


def winner_for(board: list[str]) -> str | None:
    for a, b, c in WIN_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


def legal_positions(board: list[str]) -> list[int]:
    return [index for index, value in enumerate(board) if not value]
