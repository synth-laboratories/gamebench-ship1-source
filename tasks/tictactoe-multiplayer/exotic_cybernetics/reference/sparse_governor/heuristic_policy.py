"""Sparse steering governor for multiplayer Tic-Tac-Toe."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_TASK_ROOT = Path(__file__).resolve().parents[3]
if str(_TASK_ROOT) not in sys.path:
    sys.path.insert(0, str(_TASK_ROOT))

from containers.codepolicy.heuristic_policy import choose_action as _base_choose_action  # noqa: E402


def choose_action(public: dict[str, Any], agent_id: str, seed: int, ply: int) -> dict[str, Any]:
    session_key = f"cyber_{agent_id}"
    session = public.setdefault("_cyber_sessions", {}).setdefault(session_key, {})
    if ply == 0 or int(session.get("stuck", 0)) >= 4:
        try:
            patch = SteerSession.current().steer(
                purpose="opening" if ply == 0 else "recovery",
                ply=ply,
                digest={"agent_id": agent_id, "turn": public.get("turn"), "ply": ply, "stuck": int(session.get("stuck", 0))},
                schema_hint='Return JSON only: {"phase": str, "preferred_dir": str, "notes": str}',
            )
            session["patch"] = patch
        except SteerBudgetExhausted:
            session["cyber_steer_disabled"] = True
    return _base_choose_action(public, agent_id, seed, ply)
