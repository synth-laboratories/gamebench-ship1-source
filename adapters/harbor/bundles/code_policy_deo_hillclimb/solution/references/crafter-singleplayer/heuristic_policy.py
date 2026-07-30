"""Reactive Crafter policy: harvest visible resources and advance the tool chain."""

from __future__ import annotations

from typing import Any


DIRS = {
    "move_left": (-1, 0),
    "move_right": (1, 0),
    "move_up": (0, -1),
    "move_down": (0, 1),
}
RESOURCE_KINDS = {"tree", "stone", "coal", "iron", "diamond", "water", "chest"}
EXPLORE = ["move_right", "move_down", "move_left", "move_left", "move_up", "move_up", "move_right", "move_right"]
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
    del observation_text, action_history, action_history_names, min_action_batch_size
    del target_action_batch_size, engine, stream_callback
    session = session if session is not None else {}
    valid = set(valid_actions)
    readout = kwargs.get("readout") or {}
    obs = readout.get("observation") or {}
    player = obs.get("player") or {}
    pos = player.get("pos") or [0, 0]
    inv = dict(player.get("inventory") or {})
    achievements = dict(obs.get("achievements") or {})
    front = readout.get("front_tile") or {}
    front_kind = str(front.get("kind"))
    tiles = list((obs.get("view") or {}).get("tiles") or [])

    def available(action: str) -> bool:
        return action in valid

    def one(action: str) -> list[str]:
        return [action] if available(action) else ["noop"] if available("noop") else []

    # The crafting API acts on adjacent stations.  Place/craft immediately
    # while the station is still in front of the player.
    if achievements.get("place_table", 0) <= 0 and inv.get("wood", 0) >= 2:
        if front_kind == "grass" and available("place_table"):
            return {"actions": ["place_table"], "policy_reason": "place table", "session": session}
    if achievements.get("place_table", 0) > 0 and achievements.get("make_wood_pickaxe", 0) <= 0 and inv.get("wood", 0) >= 1:
        if available("make_wood_pickaxe"):
            return {"actions": ["make_wood_pickaxe"], "policy_reason": "craft wood pickaxe", "session": session}

    if achievements.get("place_furnace", 0) <= 0 and inv.get("stone", 0) >= 4:
        if front_kind == "grass" and available("place_furnace"):
            return {"actions": ["place_furnace"], "policy_reason": "place furnace", "session": session}
    if achievements.get("place_table", 0) > 0 and achievements.get("make_stone_pickaxe", 0) <= 0 and inv.get("wood", 0) >= 1 and inv.get("stone", 0) >= 1:
        if available("make_stone_pickaxe"):
            return {"actions": ["make_stone_pickaxe"], "policy_reason": "craft stone pickaxe", "session": session}
    if achievements.get("place_furnace", 0) > 0 and achievements.get("make_iron_pickaxe", 0) <= 0 and inv.get("wood", 0) >= 1 and inv.get("coal", 0) >= 1 and inv.get("iron", 0) >= 1:
        if available("make_iron_pickaxe"):
            return {"actions": ["make_iron_pickaxe"], "policy_reason": "craft iron pickaxe", "session": session}

    # Mine the first visible resource needed by the current progression.
    needed = {"tree"} if inv.get("wood", 0) < 2 else set()
    if inv.get("wood_pickaxe", 0) > 0:
        if inv.get("stone", 0) < 4:
            needed.add("stone")
        else:
            needed.update({"coal", "iron"})
    candidates = [t for t in tiles if str(t.get("kind")) in needed and t.get("in_bounds", True)]
    if candidates:
        target = min(candidates, key=lambda t: abs(int(t["pos"][0]) - int(pos[0])) + abs(int(t["pos"][1]) - int(pos[1])))
        tx, ty = int(target["pos"][0]), int(target["pos"][1])
        dx, dy = tx - int(pos[0]), ty - int(pos[1])
        if abs(dx) + abs(dy) == 1:
            # A blocked move still turns the player toward the resource.
            action = "move_right" if dx > 0 else "move_left" if dx < 0 else "move_down" if dy > 0 else "move_up"
            if front_kind == str(target.get("kind")) and available("do"):
                action = "do"
            return {"actions": one(action), "policy_reason": "approach visible resource", "session": session}
        # Move along the larger coordinate delta; use only walk actions.
        if abs(dx) >= abs(dy) and dx:
            action = "move_right" if dx > 0 else "move_left"
        elif dy:
            action = "move_down" if dy > 0 else "move_up"
        else:
            action = "do"
        return {"actions": one(action), "policy_reason": "navigate to visible resource", "session": session}

    # Find a nearby empty grass tile when a station can be placed but is not
    # currently in front; otherwise perform a deterministic expanding sweep.
    if (inv.get("wood", 0) >= 2 and achievements.get("place_table", 0) <= 0) or (inv.get("stone", 0) >= 4 and achievements.get("place_furnace", 0) <= 0):
        grass = [t for t in tiles if t.get("kind") == "grass" and t.get("in_bounds", True)]
        if grass:
            target = min(grass, key=lambda t: abs(int(t["pos"][0]) - int(pos[0])) + abs(int(t["pos"][1]) - int(pos[1])))
            gx, gy = int(target["pos"][0]) - int(pos[0]), int(target["pos"][1]) - int(pos[1])
            if gx or gy:
                action = "move_right" if gx > 0 else "move_left" if gx < 0 else "move_down" if gy > 0 else "move_up"
                return {"actions": one(action), "policy_reason": "find placeable grass", "session": session}

    cursor = int(session.get("cursor", 0))
    action = EXPLORE[cursor % len(EXPLORE)]
    session["cursor"] = cursor + 1
    return {"actions": one(action), "policy_reason": "explore for resources", "session": session}
