"""Reference hillclimb candidate: seeded_win_block_v1 (oracle policy for verify)."""
from __future__ import annotations

from typing import Any

from registry import choose_action as registry_choose_action

POLICY_ID = "seeded_win_block_v1"


def choose_action(public: dict[str, Any], seed: int, ply: int) -> dict[str, Any]:
    state = {
        "board": list(public["board"]),
        "turn": public["turn"],
        "winner": public.get("winner"),
    }
    return registry_choose_action(POLICY_ID, state, seed=seed, ply=ply)
