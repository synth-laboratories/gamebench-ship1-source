"""Agent-facing observation and action parsing helpers for MiniHack."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


DIRECTION_RE = re.compile(
    r"\b(north|south|east|west|northeast|northwest|southeast|southwest)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedAction:
    action: dict[str, Any]
    invalid_parse: bool
    repaired: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "invalid_parse": self.invalid_parse,
            "repaired": self.repaired,
            "error": self.error,
        }


def _normalize_action(candidate: dict[str, Any]) -> dict[str, Any]:
    parsed = dict(candidate)
    if "kind" not in parsed and "direction" in parsed:
        parsed["kind"] = "move"
    return parsed


def _action_in_valid(candidate: dict[str, Any], valid_actions: list[dict[str, Any]]) -> bool:
    normalized = _normalize_action(candidate)
    for valid in valid_actions:
        if valid == normalized:
            return True
    return False


def parse_action_text(raw_text: Any, valid_actions: list[dict[str, Any]] | None = None) -> ParsedAction:
    valid = valid_actions or [{"kind": "wait"}]
    text = raw_text if isinstance(raw_text, str) else json.dumps(raw_text)
    candidates: list[dict[str, Any]] = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            if "action" in parsed and isinstance(parsed["action"], dict):
                candidates.append(dict(parsed["action"]))
            else:
                candidates.append(dict(parsed))
        elif isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            candidates.append(dict(parsed[0]))
    except json.JSONDecodeError:
        pass

    lowered = text.lower()
    if "pickup" in lowered or "pick up" in lowered:
        candidates.append({"kind": "pickup"})
    if "wait" in lowered:
        candidates.append({"kind": "wait"})
    if "attack" in lowered:
        direction_match = DIRECTION_RE.search(text)
        if direction_match:
            candidates.append({"kind": "attack", "direction": direction_match.group(1).lower()})
        else:
            candidates.append({"kind": "attack", "direction": "north"})
    direction_match = DIRECTION_RE.search(text)
    if direction_match:
        candidates.append({"kind": "move", "direction": direction_match.group(1).lower()})

    for candidate in candidates:
        normalized = _normalize_action(candidate)
        if _action_in_valid(normalized, valid):
            return ParsedAction(action=normalized, invalid_parse=False, repaired=False)

    return ParsedAction(action=dict(valid[0]), invalid_parse=True, repaired=True, error="no_valid_action_found")


def format_agent_observation(readout: dict[str, Any], *, objective: str | None = None) -> dict[str, Any]:
    public = readout.get("public") or {}
    private = readout.get("private") or {}
    profile = readout.get("profile", "unknown")
    lines = [
        objective or "Navigate the MiniHack symbolic grid: reach goals, solve box puzzles, or clear combat corridors.",
        "",
        "ASCII map legend: @ player, > goal, * target, O boulder, M monster, ~ lava, # wall.",
        f"Profile: {profile}",
        "",
        str(readout.get("ascii", "")),
        "",
        f"Player: {json.dumps(public.get('player'))}",
        f"Inventory: {json.dumps(public.get('inventory', []))}",
        f"Reward total: {float(private.get('total_reward', 0.0)):.2f}",
        f"Step: {private.get('step_index', 0)}",
        f"Valid actions: {json.dumps(readout.get('valid_actions', []))}",
    ]
    observation_text = "\n".join(lines)
    return {"observation_text": observation_text, "readout": readout}
