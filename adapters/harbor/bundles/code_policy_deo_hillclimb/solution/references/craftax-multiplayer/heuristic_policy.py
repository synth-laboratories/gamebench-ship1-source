"""Craftax-Coop heuristic with early progression and cooperative survival."""

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
    return next((cell for cell in _cells(observation) if cell["x"] == x and cell["y"] == y), None)


def _stock(player: dict, resource: str) -> int:
    if resource in ("food", "drink"):
        return int(player[resource])
    return int(player["inventory"].get(resource, 0))


def _near(observation: dict, terrain: str) -> bool:
    me = observation["self"]
    x, y = me["position"]
    return any(
        cell["terrain"] == terrain and abs(cell["x"] - x) <= 1 and abs(cell["y"] - y) <= 1
        for cell in _cells(observation)
    )


def act(observation: dict) -> dict:
    me = observation["self"]
    agent_id, role = me["agent_id"], observation["role"]
    inv, equip = me["inventory"], me["equipment"]
    x, y = me["position"]
    dx, dy = DELTAS[me["facing"]]
    front = _cell(observation, x + dx, y + dy)

    # Fulfil live requests, but leave emergency food and drink for ourselves.
    for teammate in observation["teammate_dashboard"]:
        resource = teammate["request"]["resource"]
        if teammate["agent_id"] == agent_id or not resource:
            continue
        reserve = 2 if resource in ("food", "drink") else 0
        if _stock(me, resource) > reserve:
            return {"kind": f"give_{resource}_to_{teammate['agent_id']}"}

    if front and front["terrain"] in ("water", "fountain") and me["drink"] <= 6:
        return {"kind": "do"}
    if me["health"] <= 3 and me["equipment"]["potions"]["red"]:
        return {"kind": "drink_potion_red"}
    if role == "forager":
        if any(t["health"] <= 5 for t in observation["teammate_dashboard"]) and me["mana"] >= 6:
            return {"kind": "cast_spell"}
        if me["food"] <= 2:
            return {"kind": "request_food"}
        if me["drink"] <= 2:
            return {"kind": "request_drink"}
    elif me["food"] <= 1:
        return {"kind": "request_food"}
    elif me["drink"] <= 1:
        return {"kind": "request_drink"}

    # Build the tools that unlock the next region/resource tier.
    near_table = _near(observation, "crafting_table")
    needs_crafting = (
        (role == "miner" and equip["pickaxe"] < 1 and inv["wood"] >= 1)
        or (role == "warrior" and equip["sword"] < 1 and inv["wood"] >= 1)
    )
    if needs_crafting and not near_table:
        for direction, (ddx, ddy) in DELTAS.items():
            cell = _cell(observation, x + ddx, y + ddy)
            if cell and cell["terrain"] == "crafting_table":
                return {"kind": direction}
    if role == "miner" and near_table:
        if equip["pickaxe"] < 1 and inv["wood"] >= 1:
            return {"kind": "make_wood_pickaxe"}
        if inv["diamond"] >= 3 and equip["pickaxe"] < 4:
            return {"kind": "make_diamond_pickaxe"}
        if inv["iron"] >= 1 and inv["stone"] >= 1 and inv["coal"] >= 1 and equip["pickaxe"] < 3:
            return {"kind": "make_iron_pickaxe"}
        if inv["stone"] >= 1 and inv["wood"] >= 1 and equip["pickaxe"] < 2:
            return {"kind": "make_stone_pickaxe"}
    if role == "warrior" and near_table:
        if inv["diamond"] >= 2 and equip["sword"] < 4:
            return {"kind": "make_diamond_sword"}
        if inv["iron"] >= 1 and inv["stone"] >= 1 and inv["coal"] >= 1 and equip["sword"] < 3:
            return {"kind": "make_iron_sword"}
        if inv["stone"] >= 1 and inv["wood"] >= 1 and equip["sword"] < 2:
            return {"kind": "make_stone_sword"}
    if inv["wood"] and equip["sword"] < 1 and near_table:
        return {"kind": "make_wood_sword"}

    # Use books as soon as found; the forager can then heal the whole party.
    if me["equipment"]["books"] > 0 and not me["equipment"]["learned_spell"]:
        return {"kind": "read_book"}

    wanted = {
        "warrior": {"tree", "chest", "ripe_plant", "boss", "crafting_table"},
        "forager": {"tree", "ripe_plant", "chest", "fountain", "boss"},
        "miner": {"tree", "stone", "coal", "iron", "diamond", "ruby", "sapphire", "chest", "boss", "crafting_table"},
    }[role]
    if front and front["terrain"] == "crafting_table":
        return {"kind": me["facing"]}
    if front and (front["terrain"] in wanted or front["mobs"]):
        return {"kind": "do"}
    for direction, (ddx, ddy) in DELTAS.items():
        cell = _cell(observation, x + ddx, y + ddy)
        if cell and (cell["terrain"] in wanted or cell["mobs"]):
            return {"kind": direction}

    here = _cell(observation, x, y)
    if here and here["terrain"] == "stairs_down":
        return {"kind": "descend"}
    target = (24, 24) if observation["level"] == 8 else (45, 45)
    preferred = []
    if target[0] != x:
        preferred.append("right" if target[0] > x else "left")
    if target[1] != y:
        preferred.append("down" if target[1] > y else "up")
    preferred.extend(d for d in DELTAS if d not in preferred)
    if role == "forager" and len(preferred) > 1:
        preferred[0], preferred[1] = preferred[1], preferred[0]
    for direction in preferred:
        ddx, ddy = DELTAS[direction]
        cell = _cell(observation, x + ddx, y + ddy)
        if cell and cell["terrain"] in WALKABLE and not cell["agents"]:
            return {"kind": direction}
    return {"kind": "rest"}
