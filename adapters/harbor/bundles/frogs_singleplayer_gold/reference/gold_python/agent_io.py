"""Agent-facing observation and action parsing helpers for FrogsGame."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


CELL_RE = re.compile(r"\b(?:row|r)\s*[:= ]\s*(\d+)\D+(?:col|c)\s*[:= ]\s*(\d+)", re.IGNORECASE)


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


def parse_action_text(raw_text: Any, valid_actions: list[dict[str, Any]] | None = None) -> ParsedAction:
    valid = valid_actions or [{"kind": "submit"}]
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
    if "submit" in lowered:
        candidates.append({"kind": "submit"})
    if "reset" in lowered:
        candidates.append({"kind": "reset"})
    match = CELL_RE.search(text)
    if match:
        candidates.append({"kind": "place_frog", "row": int(match.group(1)), "col": int(match.group(2))})

    for candidate in candidates:
        normalized = _normalize_action(candidate)
        if normalized in valid:
            return ParsedAction(action=normalized, invalid_parse=False, repaired=False)
        if normalized.get("kind") == "submit":
            return ParsedAction(action=normalized, invalid_parse=False, repaired=False)

    return ParsedAction(action=dict(valid[0]), invalid_parse=True, repaired=True, error="no_valid_action_found")


def format_agent_observation(readout: dict[str, Any], *, objective: str | None = None) -> dict[str, Any]:
    public = readout["public"]
    private = readout["private"]
    board = public["board"]
    frogs = public["frogs"]
    valid_actions = _valid_actions_from_public(public)
    lines = [
        objective or "Place one frog in every row, column, and color, with no adjacent frogs, then submit.",
        "",
        "Board cells are color names. Frogs are marked with F.",
        "Board:",
        str(readout.get("ascii", "")),
        "",
        f"Placed frogs: {json.dumps(frogs)}",
        f"Board size: {len(board)}",
        f"Reward total: {float(private.get('total_reward', 0.0)):.2f}",
        f"Step: {private.get('step_index', 0)}",
        "Reply with JSON, for example {\"kind\":\"place_frog\",\"row\":0,\"col\":1} or {\"kind\":\"submit\"}.",
    ]
    return {
        "observation_text": "\n".join(lines),
        "ascii": readout.get("ascii", ""),
        "valid_actions": valid_actions,
        "grid_hash": readout.get("grid_hash"),
        "public": public,
        "private": private,
    }


def _valid_actions_from_public(public: dict[str, Any]) -> list[dict[str, Any]]:
    from scoring import validate_frogs

    board = public["board"]
    frogs = [(int(row), int(col)) for row, col in public.get("frogs", [])]
    frog_set = set(frogs)
    valid: list[dict[str, Any]] = [{"kind": "submit"}, {"kind": "reset"}]
    for row in range(len(board)):
        for col in range(len(board)):
            if (row, col) in frog_set:
                valid.append({"kind": "remove_frog", "row": row, "col": col})
            elif not validate_frogs(board, [*frogs, (row, col)], require_complete=False):
                valid.append({"kind": "place_frog", "row": row, "col": col})
    return valid


def _normalize_action(action: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(action)
    if "kind" not in normalized and "type" in normalized:
        normalized["kind"] = normalized["type"]
    if normalized.get("kind") in {"place_frog", "remove_frog"}:
        normalized["row"] = int(normalized.get("row", -1))
        normalized["col"] = int(normalized.get("col", -1))
    return normalized
