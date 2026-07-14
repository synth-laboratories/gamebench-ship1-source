"""Agent-facing observation and action parsing helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


ACTION_WORDS = ("up", "down", "left", "right")
ACTION_TAG_RE = re.compile(r"<action>\s*(up|down|left|right)\s*</action>", re.IGNORECASE)
ACTION_LINE_RE = re.compile(r"\b(?:action|move|direction)\s*[:=]\s*(up|down|left|right)\b", re.IGNORECASE)
WORD_RE = re.compile(r"\b(up|down|left|right)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedAction:
    action: str
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


def parse_action_text(raw_text: str, valid_actions: list[str] | None = None) -> ParsedAction:
    """Parse ReAct/LM output into one Sokoban action.

    The parser is deliberately deterministic. If the text is malformed or names
    an invalid action, it repairs to the first valid action in canonical order.
    """

    valid = [action for action in ACTION_WORDS if not valid_actions or action in valid_actions]
    if not valid:
        return ParsedAction(action="", invalid_parse=True, repaired=False, error="no_valid_actions")

    text = str(raw_text or "").strip()
    candidates: list[str] = []
    for matcher in (ACTION_TAG_RE, ACTION_LINE_RE, WORD_RE):
        match = matcher.search(text)
        if match:
            candidates.append(match.group(1).lower())

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            value = parsed.get("action", parsed.get("move", parsed.get("direction")))
            if value is not None:
                candidates.insert(0, str(value).lower().strip())
        elif isinstance(parsed, str):
            candidates.insert(0, parsed.lower().strip())
    except json.JSONDecodeError:
        pass

    for candidate in candidates:
        if candidate in valid:
            return ParsedAction(action=candidate, invalid_parse=False, repaired=False)
        if candidate in ACTION_WORDS:
            return ParsedAction(
                action=valid[0],
                invalid_parse=True,
                repaired=True,
                error=f"invalid_action:{candidate}",
            )
    return ParsedAction(action=valid[0], invalid_parse=True, repaired=True, error="no_action_found")


def format_agent_observation(readout: dict[str, Any], *, objective: str | None = None) -> dict[str, Any]:
    public = readout["public"]
    private = readout["private"]
    valid_actions = list(readout.get("valid_actions", []))
    remaining = max(0, int(private.get("max_steps", 0) or 0) - int(private.get("step_index", 0)))
    lines = [
        objective or "Push every box onto a target.",
        "",
        "Legend: # wall, @ player, $ box, . target, * box on target, + player on target.",
        "Board:",
        str(readout.get("ascii", "")),
        "",
        f"Valid actions: {', '.join(valid_actions) if valid_actions else 'none'}",
        f"Boxes on target: {public.get('boxes_on_target', 0)}",
        f"Reward total: {private.get('total_reward', 0.0):.2f}",
        f"Step: {private.get('step_index', 0)}",
    ]
    if remaining:
        lines.append(f"Steps remaining: {remaining}")
    lines.append('Reply with exactly one move as JSON, for example {"action":"right"}.')
    return {
        "observation_text": "\n".join(lines),
        "ascii": readout.get("ascii", ""),
        "valid_actions": valid_actions,
        "grid_hash": readout.get("grid_hash"),
        "public": public,
        "private": private,
    }
