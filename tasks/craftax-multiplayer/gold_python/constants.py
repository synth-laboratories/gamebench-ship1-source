"""Craftax-Coop constants, independent of the single-player runtime."""

AGENT_IDS = ("agent_0", "agent_1", "agent_2")
ROLES = ("warrior", "forager", "miner")
MAP_SIZE = 48
NUM_LEVELS = 9
REQUEST_DURATION = 10
MAX_TIMESTEPS = 100_000
DAY_LENGTH = 300
MAX_HEALTH = 9
MAX_FOOD = 9
MAX_DRINK = 9
MAX_ENERGY = 9
MAX_MANA = 9
BOSS_HEALTH = 24
RESOURCES = ("food", "drink", "wood", "stone", "iron", "coal", "diamond", "ruby", "sapphire")
TERRAINS = (
    "grass", "water", "stone", "tree", "wood", "path", "coal", "iron", "diamond",
    "crafting_table", "furnace", "sand", "lava", "plant", "ripe_plant", "wall",
    "darkness", "wall_moss", "stalagmite", "sapphire", "ruby", "chest", "fountain",
    "fire_grass", "ice_grass", "gravel", "fire_tree", "ice_shrub",
    "enchantment_table_fire", "enchantment_table_ice", "necromancer", "grave",
    "stairs_down", "stairs_up", "boss",
)
BASE_ACTIONS = (
    "noop", "left", "right", "up", "down", "do", "sleep", "rest", "descend", "ascend",
    "place_stone", "place_table", "place_furnace", "place_plant", "make_wood_pickaxe",
    "make_stone_pickaxe", "make_iron_pickaxe", "make_diamond_pickaxe", "make_wood_sword",
    "make_stone_sword", "make_iron_sword", "make_diamond_sword", "make_iron_armour",
    "make_diamond_armour", "shoot_arrow", "make_arrow", "cast_spell", "place_torch",
    "make_torch", "attack", "drink_potion_red", "drink_potion_green",
    "drink_potion_blue", "drink_potion_pink", "drink_potion_cyan",
    "drink_potion_yellow", "read_book", "enchant_sword", "enchant_armour",
    "enchant_bow", "level_up_dexterity", "level_up_strength",
    "level_up_intelligence",
)
REQUEST_ACTIONS = tuple(f"request_{resource}" for resource in RESOURCES)
ACHIEVEMENTS = (
    "collect_wood", "collect_stone", "collect_coal", "collect_iron", "collect_diamond",
    "collect_ruby", "collect_sapphire", "eat_food", "drink_water", "craft_pickaxe",
    "craft_sword", "craft_armour", "trade", "descend", "defeat_monster", "damage_boss",
    "defeat_boss", "all_roles_alive", "place_table", "place_furnace", "place_plant",
    "eat_plant", "open_chest", "drink_potion", "read_book", "cast_spell",
    "shoot_arrow", "enchant_item", "level_up", "wake_up", "collect_sapling",
)
GLYPHS = {"grass": ".", "water": "~", "stone": "O", "tree": "T", "wood":"w", "path":"_", "coal": "c", "iron": "i", "diamond": "d", "ruby": "r", "sapphire": "s", "crafting_table":"C", "furnace":"F", "sand":":", "lava":"L", "plant":"p", "ripe_plant":"P", "wall":"#", "chest":"$", "fountain":"f", "fire_grass":";", "ice_grass":",", "fire_tree":"Y", "ice_shrub":"y", "enchantment_table_fire":"E", "enchantment_table_ice":"e", "necromancer":"N", "grave":"g", "stairs_down": ">", "stairs_up": "<", "boss": "B"}

POTION_COLOURS = ("red", "green", "blue", "pink", "cyan", "yellow")
MOB_STATS = {
    "cow": (3, 0), "bat": (2, 1), "zombie": (5, 2), "skeleton": (4, 2),
    "gnome": (5, 2), "orc": (7, 3), "troll": (10, 4), "fire_elemental": (8, 4),
    "ice_elemental": (8, 4), "necromancer_minion": (10, 5),
}
