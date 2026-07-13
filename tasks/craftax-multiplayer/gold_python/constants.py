"""Craftax-Coop constants, independent of the single-player runtime."""

AGENT_IDS = ("agent_0", "agent_1", "agent_2")
ROLES = ("warrior", "forager", "miner")
MAP_SIZE = 48
NUM_LEVELS = 9
REQUEST_DURATION = 10
MAX_TIMESTEPS = 100_000
RESOURCES = ("food", "drink", "wood", "stone", "iron", "coal", "diamond", "ruby", "sapphire")
TERRAINS = ("grass", "water", "stone", "tree", "coal", "iron", "diamond", "ruby", "sapphire", "stairs_down", "stairs_up", "boss")
BASE_ACTIONS = (
    "noop", "left", "right", "up", "down", "do", "sleep", "rest", "descend", "ascend",
    "place_stone", "place_table", "place_furnace", "place_plant", "make_wood_pickaxe",
    "make_stone_pickaxe", "make_iron_pickaxe", "make_diamond_pickaxe", "make_wood_sword",
    "make_stone_sword", "make_iron_sword", "make_diamond_sword", "make_iron_armour",
    "make_diamond_armour", "shoot_arrow", "make_arrow", "cast_spell", "place_torch",
    "make_torch", "attack",
)
REQUEST_ACTIONS = tuple(f"request_{resource}" for resource in RESOURCES)
ACHIEVEMENTS = (
    "collect_wood", "collect_stone", "collect_coal", "collect_iron", "collect_diamond",
    "collect_ruby", "collect_sapphire", "eat_food", "drink_water", "craft_pickaxe",
    "craft_sword", "craft_armour", "trade", "descend", "defeat_monster", "damage_boss",
    "defeat_boss", "all_roles_alive",
)
GLYPHS = {"grass": ".", "water": "~", "stone": "O", "tree": "T", "coal": "c", "iron": "i", "diamond": "d", "ruby": "r", "sapphire": "s", "stairs_down": ">", "stairs_up": "<", "boss": "B"}
