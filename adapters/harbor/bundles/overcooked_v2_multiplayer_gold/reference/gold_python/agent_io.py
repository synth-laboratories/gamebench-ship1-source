"""Agent-facing observation and action parsing for Overcooked v2 MARL."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


DIRECTION_RE = re.compile(r"\b(north|south|east|west)\b", re.IGNORECASE)
WAIT_ACTION = {"kind": "wait"}


@dataclass(frozen=True)
class ParsedAction:
    action: dict[str, Any]
    invalid_parse: bool
    repaired: bool
    error: str | None = None


def parse_action_text(raw_text: Any, valid_actions: list[dict[str, Any]] | None = None) -> ParsedAction:
    valid = valid_actions or [WAIT_ACTION]
    text = raw_text if isinstance(raw_text, str) else json.dumps(raw_text)
    candidates: list[dict[str, Any]] = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            candidates.append(dict(parsed))
    except json.JSONDecodeError:
        pass
    lowered = text.lower()
    if "interact" in lowered:
        candidates.append({"kind": "interact"})
    if "wait" in lowered or "noop" in lowered:
        candidates.append(WAIT_ACTION)
    direction_match = DIRECTION_RE.search(text)
    if direction_match:
        candidates.append({"kind": "move", "direction": direction_match.group(1).lower()})
    for candidate in candidates:
        if candidate in valid:
            return ParsedAction(action=candidate, invalid_parse=False, repaired=False)
    return ParsedAction(action=dict(valid[0]), invalid_parse=True, repaired=True, error="no_valid_action_found")


def format_joint_observation(readout: dict[str, Any], *, objective: str | None = None) -> dict[str, Any]:
    private = readout.get("private") or {}
    public = readout.get("public") or {}
    lines = [
        objective or "Cooperate to prepare soup: pick ingredients, cook in pot, deliver at serve tile.",
        "",
        "ASCII legend: O/0-9 ingredient piles, T tomato, D dish, P pot, S serve, C counter, L button, R recipe indicator.",
        "",
        str(readout.get("ascii", "")),
        "",
        f"Public state: {json.dumps(public)}",
        f"Observation profile: {readout.get('observation_profile', 'symbolic_compact')}",
        f"Reward total: {float(private.get('total_reward', 0.0)):.2f}",
        f"Step: {private.get('step_index', 0)}",
        f"Joint valid actions: {json.dumps(readout.get('joint_valid_actions', {}))}",
    ]
    return {"observation_text": "\n".join(lines), "readout": readout}


def normalize_joint_action(raw: dict[str, Any], agent_ids: tuple[str, ...] | None = None) -> dict[str, Any]:
    ids = agent_ids or tuple(sorted(key for key in raw if str(key).startswith("agent_")))
    if ids:
        return {agent_id: dict(raw.get(agent_id, WAIT_ACTION)) for agent_id in ids}
    if "agent_0" in raw or "agent_1" in raw:
        return {
            "agent_0": dict(raw.get("agent_0", WAIT_ACTION)),
            "agent_1": dict(raw.get("agent_1", WAIT_ACTION)),
        }
    return dict(raw)
