"""Pinned NLE action-space index adapter shared by the Python gold lane."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
MAP_PATH = TASK_DIR / "shared" / "nle_action_map.json"


@dataclass(frozen=True)
class NleAction:
    id: int | None
    canonical: str
    value: int

    @property
    def enum_class(self) -> str:
        return self.canonical.partition(".")[0]

    @property
    def name(self) -> str:
        return self.canonical.partition(".")[2]

    @property
    def key(self) -> str:
        if 32 <= self.value <= 126:
            return chr(self.value)
        if 128 <= self.value <= 255:
            return chr(self.value & 0x7F)
        if 0 <= self.value <= 31:
            return chr(self.value)
        return ""


def _load() -> tuple[
    tuple[NleAction, ...],
    dict[str, NleAction],
    dict[int, NleAction],
    dict[str, NleAction],
    dict[str, NleAction],
    dict[str, NleAction],
]:
    raw = json.loads(MAP_PATH.read_text())
    actions = tuple(NleAction(int(entry[0]), str(entry[1]), int(entry[2])) for entry in raw["actions"])
    unsafe_actions = tuple(
        NleAction(None, str(entry[0]), int(entry[1]))
        for entry in raw.get("accepted_unsafe_keycodes", [])
    )
    by_id = {action.id: action for action in actions if action.id is not None}
    by_name = {action.canonical: action for action in actions}
    by_key: dict[str, NleAction] = {}
    for action in actions:
        if action.key and action.key not in by_key:
            by_key[action.key] = action
    unsafe_by_name = {action.canonical: action for action in unsafe_actions}
    unsafe_by_key = {action.key: action for action in unsafe_actions if action.key}
    return actions, by_name, by_id, by_key, unsafe_by_name, unsafe_by_key


ACTIONS, BY_NAME, BY_ID, BY_KEY, UNSAFE_BY_NAME, UNSAFE_BY_KEY = _load()
ALIASES = {
    "up": "MiscDirection.UP",
    "down": "MiscDirection.DOWN",
    "wait": "MiscDirection.WAIT",
    "more": "MiscAction.MORE",
    "escape": "Command.ESC",
    "inventory": "Command.INVENTORY",
    "pickup": "Command.PICKUP",
    "open": "Command.OPEN",
    "close": "Command.CLOSE",
    "kick": "Command.KICK",
    "search": "Command.SEARCH",
    "eat": "Command.EAT",
    "wear": "Command.WEAR",
    "wield": "Command.WIELD",
    "quit": "Command.QUIT",
    "help": "UnsafeActions.HELP",
    "prevmsg": "UnsafeActions.PREVMSG",
}


def coerce_action(value: Any) -> NleAction | None:
    """Accept the authoritative id plus authoring-friendly canonical adapters."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return BY_ID.get(value)
    if not isinstance(value, str):
        return None
    raw = value
    token = raw.strip()
    if token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
        return BY_ID.get(int(token))
    if token in BY_NAME:
        return BY_NAME[token]
    if token in UNSAFE_BY_NAME:
        return UNSAFE_BY_NAME[token]
    upper = token.upper()
    if "." not in token:
        alias = ALIASES.get(token.lower())
        if alias:
            return BY_NAME.get(alias) or UNSAFE_BY_NAME.get(alias)
        for enum_class in ("CompassDirection", "CompassDirectionLonger", "MiscDirection", "MiscAction", "Command", "TextCharacters"):
            candidate = f"{enum_class}.{upper}"
            if candidate in BY_NAME:
                return BY_NAME[candidate]
    if len(raw) == 1:
        return UNSAFE_BY_KEY.get(raw) or BY_KEY.get(raw)
    if len(token) == 1:
        return UNSAFE_BY_KEY.get(token) or BY_KEY.get(token)
    return None


def action_payload(action: NleAction) -> dict[str, Any]:
    return {"id": action.id, "name": action.canonical, "value": action.value, "key": action.key}


DIRECTIONS = {
    "N": (0, -1),
    "E": (1, 0),
    "S": (0, 1),
    "W": (-1, 0),
    "NE": (1, -1),
    "SE": (1, 1),
    "SW": (-1, 1),
    "NW": (-1, -1),
}


def direction_for(action: NleAction) -> tuple[int, int] | None:
    if action.enum_class not in {"CompassDirection", "CompassDirectionLonger"}:
        return None
    return DIRECTIONS.get(action.name)
