"""Deterministic role-aware Craftax-Coop code policy."""

from __future__ import annotations

WALKABLE = {
    "grass", "path", "sand", "gravel", "fire_grass", "ice_grass",
    "stairs_down", "stairs_up", "crafting_table", "furnace",
    "enchantment_table_fire", "enchantment_table_ice",
}
DELTAS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}


def _cells(observation: dict) -> list[dict]:
    return [cell for row in observation["local_view"] for cell in row]


def _cell(observation: dict, x: int, y: int) -> dict | None:
    return next(
        (cell for cell in _cells(observation) if cell["x"] == x and cell["y"] == y),
        None,
    )


def act(observation: dict) -> dict:
    me = observation["self"]
    agent_id = me["agent_id"]
    role = observation["role"]
    inventory = me["inventory"]
    x, y = me["position"]
    facing = me["facing"]
    front_dx, front_dy = DELTAS[facing]
    front = _cell(observation, x + front_dx, y + front_dy)

    coordination = observation["shared"].get("coordination")
    if coordination:
        site = coordination["sites"][0]
        if site["kind"] == "sync_2":
            if agent_id in ("agent_0", "agent_1"):
                return {"kind": "do"}
            return {"kind": "say", "to": "all", "code": "MEET_AT", "site_id": site["site_id"]}
        if site["kind"] == "sync_all":
            return {"kind": "do"}
        if role == "miner" and site["status"] == "open":
            return {"kind": "do"}
        if role == "forager" and site["status"] == "opened":
            return {"kind": "do"}
        return {"kind": "say", "to": "all", "code": "NEED_IRON", "site_id": site["site_id"]}

    for teammate in observation["teammate_dashboard"]:
        resource = teammate["request"]["resource"]
        if (
            teammate["agent_id"] != agent_id
            and resource
            and _resource_stock(me, resource) > 0
        ):
            return {"kind": f"give_{resource}_to_{teammate['agent_id']}"}
    if front and front["terrain"] in ("water", "fountain") and me["drink"] <= 6:
        return {"kind": "do"}
    if (
        role == "forager"
        and any(teammate["health"] <= 5 for teammate in observation["teammate_dashboard"])
        and me["mana"] >= 2
    ):
        return {"kind": "cast_spell"}
    if me["health"] <= 3 and me["equipment"]["potions"]["red"]:
        return {"kind": "drink_potion_red"}
    if me["food"] <= 2:
        return {"kind": "request_food"}
    if me["drink"] <= 2:
        return {"kind": "request_drink"}
    if role == "miner":
        if inventory["diamond"] >= 2 and me["equipment"]["pickaxe"] < 4:
            return {"kind": "make_diamond_pickaxe"}
        if inventory["iron"] >= 2 and me["equipment"]["pickaxe"] < 3:
            return {"kind": "make_iron_pickaxe"}
        if inventory["stone"] >= 2 and me["equipment"]["pickaxe"] < 2:
            return {"kind": "make_stone_pickaxe"}
    if inventory["wood"] and me["equipment"]["sword"] < 1:
        return {"kind": "make_wood_sword"}

    wanted = {
        "warrior": {"tree", "chest", "ripe_plant", "boss"},
        "forager": {"tree", "ripe_plant", "chest", "fountain", "boss"},
        "miner": {
            "tree", "stone", "coal", "iron", "diamond", "ruby", "sapphire",
            "chest", "boss",
        },
    }[role]
    if front and (front["terrain"] in wanted or front["mobs"]):
        return {"kind": "do"}
    adjacent = []
    for direction, (dx, dy) in DELTAS.items():
        cell = _cell(observation, x + dx, y + dy)
        if cell and (cell["terrain"] in wanted or cell["mobs"]):
            adjacent.append(direction)
    if adjacent:
        return {"kind": adjacent[0]}
    here = _cell(observation, x, y)
    if here and here["terrain"] == "stairs_down":
        return {"kind": "descend"}

    target = (24, 24) if observation["level"] == 8 else (45, 45)
    preferred = []
    if target[0] != x:
        preferred.append("right" if target[0] > x else "left")
    if target[1] != y:
        preferred.append("down" if target[1] > y else "up")
    preferred.extend(direction for direction in DELTAS if direction not in preferred)
    if role == "forager" and len(preferred) > 1:
        preferred[0], preferred[1] = preferred[1], preferred[0]
    for direction in preferred:
        dx, dy = DELTAS[direction]
        cell = _cell(observation, x + dx, y + dy)
        if cell and cell["terrain"] in WALKABLE and not cell["agents"]:
            return {"kind": direction}
    return {"kind": "rest"}


def _resource_stock(player: dict, resource: str) -> int:
    if resource in ("food", "drink"):
        return int(player[resource])
    return int(player["inventory"][resource])
