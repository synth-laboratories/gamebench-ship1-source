"""Deterministic Crafter baseline code policy."""

from __future__ import annotations

from typing import Any


EXPLORE_PATTERN = [
    "do",
    "move_right",
    "do",
    "move_down",
    "do",
    "move_left",
    "do",
    "move_up",
]
RESOURCE_TILES = {"tree", "stone", "coal", "iron", "diamond", "water", "grass", "chest"}
USES_SIM_ENGINE = False


def choose_actions(
    *,
    observation_text: str,
    session: dict | None = None,
    action_history=None,
    action_history_names=None,
    valid_actions,
    min_action_batch_size: int = 3,
    target_action_batch_size: int = 5,
    max_action_batch_size: int = 8,
    engine=None,
    stream_callback=None,
    **kwargs,
) -> dict[str, Any]:
    del observation_text, action_history, action_history_names, engine, stream_callback
    session = session if session is not None else {}
    valid = set(valid_actions)
    readout = kwargs.get("readout") or {}
    obs = readout.get("observation", {})
    player = obs.get("player", {})
    inventory = dict(player.get("inventory", {}))
    achievements = obs.get("achievements", {})
    front = readout.get("front_tile") or {}
    front_kind = str(front.get("kind"))
    actions: list[str] = []

    def add(action: str) -> None:
        if action in valid and len(actions) < max_action_batch_size:
            actions.append(action)

    if front_kind in RESOURCE_TILES:
        add("do")
    if achievements.get("place_table", 0) <= 0 and inventory.get("wood", 0) >= 2:
        add("place_table")
    if achievements.get("make_wood_pickaxe", 0) <= 0 and inventory.get("wood", 0) >= 1:
        add("make_wood_pickaxe")
    if achievements.get("collect_stone", 0) <= 0 and inventory.get("wood_pickaxe", 0) > 0:
        add("do")
    if achievements.get("place_furnace", 0) <= 0 and inventory.get("stone", 0) >= 4:
        add("place_furnace")
    if achievements.get("make_stone_pickaxe", 0) <= 0 and inventory.get("wood", 0) >= 1 and inventory.get("stone", 0) >= 1:
        add("make_stone_pickaxe")
    if achievements.get("make_iron_pickaxe", 0) <= 0 and inventory.get("wood", 0) >= 1 and inventory.get("coal", 0) >= 1 and inventory.get("iron", 0) >= 1:
        add("make_iron_pickaxe")

    cursor = int(session.get("explore_cursor", 0))
    target_len = max(min_action_batch_size, target_action_batch_size)
    attempts = 0
    while len(actions) < target_len and attempts < len(EXPLORE_PATTERN) * 2:
        action = EXPLORE_PATTERN[cursor % len(EXPLORE_PATTERN)]
        cursor += 1
        attempts += 1
        if action in valid:
            actions.append(action)
    while len(actions) < target_len and "noop" in valid:
        actions.append("noop")
    session["explore_cursor"] = cursor
    return {
        "actions": actions[:max_action_batch_size],
        "policy_reason": "collect visible resources, craft available ladder items, then sweep deterministically",
        "session": session,
    }
