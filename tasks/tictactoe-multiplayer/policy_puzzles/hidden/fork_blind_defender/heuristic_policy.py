"""Hidden flawed policy — takes own wins but never blocks opponent forks."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

TASK_ROOT = Path(__file__).resolve().parents[3]
if str(TASK_ROOT / "policies") not in sys.path:
    sys.path.insert(0, str(TASK_ROOT / "policies"))

from registry import legal_positions, winning_position


def choose_action(public: dict[str, Any], agent_id: str, seed: int = 0, ply: int = 0) -> dict[str, Any]:
    state = {"board": list(public["board"]), "turn": public["turn"], "winner": public.get("winner")}
    player = state["turn"]
    board = state["board"]
    legal = legal_positions(state)
    state = {"board": list(public["board"]), "turn": public["turn"], "winner": public.get("winner")}
    player = state["turn"]
    board = state["board"]
    legal = legal_positions(state)
    own_win = winning_position(board, player)
    if own_win is not None:
        return {"position": own_win}
    return {"position": legal[0]}
