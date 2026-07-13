"""Hidden flawed policy — wanders with ingredients at counter."""

from __future__ import annotations

from typing import Any

_WAIT = {"kind": "wait"}
_DIRS = [
    {"kind": "move", "direction": "north"},
    {"kind": "move", "direction": "south"},
    {"kind": "move", "direction": "east"},
    {"kind": "move", "direction": "west"},
]


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
    del observation_text, engine, seed
    joint_valid = readout.get("joint_valid_actions") or (valid_actions if isinstance(valid_actions, dict) else {})
    joint: dict[str, dict[str, Any]] = {}
    for agent_id, valid in joint_valid.items():
        held = ((readout.get("observations") or {}).get(agent_id) or {}).get("held")
        if held in {"onion", "tomato", "dish", "soup"}:
            action = _DIRS[(ply + hash(agent_id)) % len(_DIRS)]
            joint[agent_id] = action if action in valid else (_WAIT if _WAIT in valid else valid[0])
        else:
            joint[agent_id] = _WAIT if _WAIT in valid else valid[0]
    return {"joint_action": joint, "policy_reason": "pot idle cook"}
