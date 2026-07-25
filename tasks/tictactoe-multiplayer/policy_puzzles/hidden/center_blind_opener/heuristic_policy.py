"""Hidden flawed policy — undervalues center on opening."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

TASK_ROOT = Path(__file__).resolve().parents[3]
if str(TASK_ROOT / "policies") not in sys.path:
    sys.path.insert(0, str(TASK_ROOT / "policies"))

from registry import CORNERS, legal_positions, winning_position


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
    legal_no_center = [pos for pos in legal if pos != 4]
    prefer = 0 if 0 in legal_no_center else next((pos for pos in CORNERS if pos in legal_no_center), legal_no_center[0])
    return {"position": prefer}
