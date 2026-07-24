"""Agent-facing observation and action parsing helpers for Rogue."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


ACTION_WORDS = (
    "h",
    "j",
    "k",
    "l",
    "y",
    "u",
    "b",
    "n",
    ".",
    ",",
    ">",
    "<",
    "s",
    "H",
    "J",
    "K",
    "L",
    "Y",
    "U",
    "B",
    "N",
    "q",
    "r",
    "e",
    "w",
    "W",
    "T",
    "P",
    "R",
    "d",
    "i",
    "I",
    "z",
    "t",
    "f",
    "F",
    "m",
    "?",
    "/",
    "c",
    "o",
    "D",
    "S",
    ")",
    "]",
    "=",
    "@",
    "^",
    " ",
)
ACTION_RE = re.compile(r"\b(?:action|move|command)\s*[:=]\s*([^\s,;]+)", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedAction:
    action: str
    invalid_parse: bool
    repaired: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "invalid_parse": self.invalid_parse, "repaired": self.repaired, "error": self.error}


def parse_action_text(raw_text: Any, valid_actions: list[str] | None = None) -> ParsedAction:
    valid = [action for action in ACTION_WORDS if not valid_actions or action in valid_actions]
    if not valid:
        return ParsedAction("", True, False, "no_valid_actions")
    text = str(raw_text or "").strip()
    candidates: list[str] = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            value = parsed.get("action", parsed.get("move", parsed.get("command")))
            if value is not None:
                candidates.append(str(value).strip())
        elif isinstance(parsed, str):
            candidates.append(parsed.strip())
    except json.JSONDecodeError:
        pass
    match = ACTION_RE.search(text)
    if match:
        candidates.append(match.group(1).strip())
    if text in ACTION_WORDS:
        candidates.append(text)
    for candidate in candidates:
        candidate = _clean_candidate(candidate)
        if candidate in valid:
            return ParsedAction(candidate, False, False)
        if candidate in ACTION_WORDS:
            return ParsedAction(valid[0], True, True, f"invalid_action:{candidate}")
    return ParsedAction(valid[0], True, True, "no_action_found")


def format_agent_observation(readout: dict[str, Any], *, objective: str | None = None) -> dict[str, Any]:
    private = readout["private"]
    valid_actions = list(readout.get("valid_actions", []))
    lines = [
        objective or "Explore the Rogue room, collect useful items, reach stairs (%), then use >.",
        "",
        "Rogue commands include vi movement h/j/k/l/y/u/b/n, run with uppercase movement, . rest, , pick up, > descend, < ascend, s search, i inventory, q/r/e use items, w/W/T equip armor or weapons, P/R rings, d drop, z zap, t throw, f/F fight, ? help, / identify.",
        "Map:",
        str(readout.get("ascii", "")),
        "",
        f"Valid actions: {', '.join(valid_actions)}",
        f"Dungeon level: {private.get('dungeon_level', 1)}",
        f"Gold: {private.get('purse', 0)}",
        f"Step: {private.get('step_index', 0)}",
        'Reply with JSON, for example {"action":"l"}.',
    ]
    return {"observation_text": "\n".join(lines), "ascii": readout.get("ascii", ""), "valid_actions": valid_actions, "grid_hash": readout.get("grid_hash"), "public": readout["public"], "private": private}


def _clean_candidate(candidate: str) -> str:
    candidate = candidate.strip()
    if candidate in ACTION_WORDS:
        return candidate
    return candidate.strip("\"'`.,;")
