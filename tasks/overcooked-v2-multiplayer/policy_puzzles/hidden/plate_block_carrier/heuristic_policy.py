"""Hidden flawed policy — blocks partner choke point while holding plate."""

from __future__ import annotations

from typing import Any

_WAIT = {"kind": "wait"}


def choose_joint_actions(
    *,
    observation_text: str,
    session: dict[str, Any],
    valid_actions: dict[str, list[dict[str, Any]]] | list[dict[str, Any]],
    engine: Any = None,
    readout: dict[str, Any],
    seed: int,
    ply: int,
) -> dict[str, Any]:
    del observation_text, session, seed, ply, engine
    joint_valid = readout.get("joint_valid_actions") or (valid_actions if isinstance(valid_actions, dict) else {})
    joint = {agent_id: (_WAIT if _WAIT in valid else valid[0]) for agent_id, valid in joint_valid.items()}
    return {"joint_action": joint, "policy_reason": "plate block carrier"}
