"""Sparse steering governor: mostly symbolic code, occasional LLM patches."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_TASK_ROOT = Path(__file__).resolve().parents[3]
_POLICIES = _TASK_ROOT / "policies"
if str(_POLICIES) not in sys.path:
    sys.path.insert(0, str(_POLICIES))

from heuristic_baseline import choose_joint_actions as _base_choose_joint_actions  # noqa: E402


def _maybe_steer(*, session: dict[str, Any], readout: dict[str, Any] | None, ply: int) -> None:
    if session.get("cyber_steer_disabled"):
        return
    stuck = int(session.get("stuck", 0))
    last = int(session.get("last_steer_ply", -999))
    if ply != 0 and stuck < 6 and ply - last < 8:
        return
    digest = {"ply": ply, "stuck": stuck}
    if isinstance(readout, dict):
        digest["observation"] = readout.get("observation") or readout
    try:
        patch = SteerSession.current().steer(
            purpose="phase_governor",
            ply=ply,
            digest=digest,
            schema_hint='Return JSON only: {"phase": str, "preferred_dir": str, "notes": str}',
        )
    except SteerBudgetExhausted:
        session["cyber_steer_disabled"] = True
        return
    session["cybernetics_patch"] = patch
    session["last_steer_ply"] = ply


def choose_joint_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: list[str],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    _maybe_steer(session=session, readout=readout, ply=ply)
    decision = _base_choose_joint_actions(
        observation_text=observation_text,
        session=session,
        valid_actions=valid_actions,
        engine=engine,
        readout=readout,
        seed=seed,
        ply=ply,
    )
    patch = session.get("cybernetics_patch")
    if isinstance(patch, dict) and patch.get("notes"):
        reason = str(decision.get("policy_reason") or "")
        decision["policy_reason"] = f"{reason} | steer:{patch.get('phase')}:{patch.get('notes')}".strip(" |")
    return decision
