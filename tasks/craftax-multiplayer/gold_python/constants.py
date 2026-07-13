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
    "grave2", "grave3", "necromancer_vulnerable", "stairs_down", "stairs_up", "boss",
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
    "collect_wood", "place_table", "eat_cow", "collect_sapling", "collect_drink",
    "collect_food", "make_wood_pickaxe", "make_wood_sword", "place_plant",
    "defeat_zombie", "collect_stone", "place_stone", "eat_plant", "defeat_skeleton",
    "make_stone_pickaxe", "make_stone_sword", "wake_up", "place_furnace",
    "collect_coal", "collect_iron", "collect_diamond", "make_iron_pickaxe",
    "make_iron_sword", "make_arrow", "make_torch", "place_torch",
    "make_diamond_sword", "make_iron_armour", "make_diamond_armour",
    "enter_gnomish_mines", "enter_dungeon", "enter_sewers", "enter_vault",
    "enter_troll_mines", "enter_fire_realm", "enter_ice_realm", "enter_graveyard",
    "defeat_gnome_warrior", "defeat_gnome_archer", "defeat_orc_soldier",
    "defeat_orc_mage", "defeat_lizard", "defeat_kobold", "defeat_troll",
    "defeat_deep_thing", "defeat_pigman", "defeat_fire_elemental",
    "defeat_frost_troll", "defeat_ice_elemental", "damage_necromancer",
    "defeat_necromancer", "eat_bat", "eat_snail", "find_bow", "fire_bow",
    "collect_sapphire", "learn_spell", "cast_spell", "collect_ruby",
    "make_diamond_pickaxe", "open_chest", "drink_potion", "enchant_sword",
    "enchant_armour", "defeat_knight", "defeat_archer",
    # GameBench cooperative contract achievements retained in addition to author achievements.
    "trade", "all_roles_alive", "level_up",
)
GLYPHS = {"grass": ".", "water": "~", "stone": "O", "tree": "T", "wood":"w", "path":"_", "coal": "c", "iron": "i", "diamond": "d", "ruby": "r", "sapphire": "s", "crafting_table":"C", "furnace":"F", "sand":":", "lava":"L", "plant":"p", "ripe_plant":"P", "wall":"#", "chest":"$", "fountain":"f", "fire_grass":";", "ice_grass":",", "fire_tree":"Y", "ice_shrub":"y", "enchantment_table_fire":"E", "enchantment_table_ice":"e", "necromancer":"N", "grave":"g", "stairs_down": ">", "stairs_up": "<", "boss": "B"}

POTION_COLOURS = ("red", "green", "blue", "pink", "cyan", "yellow")
FLOOR_MOBS = (
    ("cow", "zombie", "skeleton"),
    ("bat", "gnome_warrior", "gnome_archer"),
    ("snail", "orc_soldier", "orc_mage"),
    ("bat", "lizard", "kobold"),
    (None, "knight", "archer"),
    (None, "troll", "deep_thing"),
    (None, "pigman", "fire_elemental"),
    (None, "frost_troll", "ice_elemental"),
    (None, None, None),
)
MOB_HEALTH = (
    (3, 5, 3), (4, 7, 5), (6, 9, 6), (8, 11, 8),
    (0, 12, 12), (0, 20, 4), (0, 20, 14), (0, 24, 16), (0, 0, 0),
)
MOB_DAMAGE = {
    "zombie": (2, 0, 0), "skeleton": (2, 0, 0),
    "gnome_warrior": (4, 0, 0), "gnome_archer": (4, 0, 0),
    "orc_soldier": (3, 0, 0), "orc_mage": (0, 3, 0),
    "lizard": (5, 0, 0), "kobold": (0, 0, 3),
    "knight": (6, 0, 0), "archer": (5, 0, 0),
    "troll": (6, 1, 1), "deep_thing": (4, 3, 3),
    "pigman": (3, 5, 0), "fire_elemental": (3, 5, 0),
    "frost_troll": (4, 0, 5), "ice_elemental": (4, 0, 5),
}
PROJECTILE_KIND = {
    "skeleton": "arrow", "gnome_archer": "arrow", "orc_mage": "fireball",
    "kobold": "dagger", "archer": "arrow2", "deep_thing": "slimeball",
    "fire_elemental": "fireball2", "ice_elemental": "iceball2",
}
LEVEL_ACHIEVEMENTS = (
    None, "enter_gnomish_mines", "enter_dungeon", "enter_sewers", "enter_vault",
    "enter_troll_mines", "enter_fire_realm", "enter_ice_realm", "enter_graveyard",
)
KILL_ACHIEVEMENTS = {
    "cow": "eat_cow", "bat": "eat_bat", "snail": "eat_snail",
    "zombie": "defeat_zombie", "skeleton": "defeat_skeleton",
    "gnome_warrior": "defeat_gnome_warrior", "gnome_archer": "defeat_gnome_archer",
    "orc_soldier": "defeat_orc_soldier", "orc_mage": "defeat_orc_mage",
    "lizard": "defeat_lizard", "kobold": "defeat_kobold", "knight": "defeat_knight",
    "archer": "defeat_archer", "troll": "defeat_troll", "deep_thing": "defeat_deep_thing",
    "pigman": "defeat_pigman", "fire_elemental": "defeat_fire_elemental",
    "frost_troll": "defeat_frost_troll", "ice_elemental": "defeat_ice_elemental",
}
