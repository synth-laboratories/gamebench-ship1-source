"""Deterministic Crafter task resolver shared by Python and Rust lanes."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
DEFAULT_WORLD_MAP_LEGEND = {
    "~": "water",
    ".": "grass",
    "#": "stone",
    ":": "path",
    ",": "sand",
    "T": "tree",
    "L": "lava",
    "C": "coal",
    "I": "iron",
    "D": "diamond",
    "S": "sapphire",
    "R": "ruby",
    "$": "chest",
    "=": "table",
    "F": "furnace",
}
INVENTORY_KEYS = {
    "health",
    "food",
    "drink",
    "energy",
    "sapling",
    "wood",
    "stone",
    "coal",
    "iron",
    "diamond",
    "sapphire",
    "ruby",
    "wood_pickaxe",
    "stone_pickaxe",
    "iron_pickaxe",
    "diamond_pickaxe",
    "wood_sword",
    "stone_sword",
    "iron_sword",
    "diamond_sword",
    "bow",
    "arrows",
    "armor_helmet",
    "armor_chestplate",
    "armor_leggings",
    "armor_boots",
    "potion_red",
    "potion_green",
    "potion_blue",
    "potion_pink",
    "potion_cyan",
    "potion_yellow",
    "xp",
    "level",
    "stat_points",
}
FACING_VALUES = {(-1, 0), (1, 0), (0, -1), (0, 1)}
MAX_U32 = 4_294_967_295
MAX_ENTITY_HEALTH = 255
WORLDGEN_DENSITY_KEYS = (
    "tree_density",
    "coal_density",
    "iron_density",
    "diamond_density",
    "cow_density",
    "zombie_density",
    "skeleton_density",
)
ENTITY_DEFAULT_HEALTH = {
    "cow": 3,
    "zombie": 5,
    "skeleton": 3,
    "orc_soldier": 5,
    "orc_mage": 3,
    "knight": 9,
    "knight_archer": 8,
    "troll": 12,
    "bat": 2,
    "snail": 3,
}
ENTITY_KINDS = set(ENTITY_DEFAULT_HEALTH)
ACHIEVEMENT_KEYS = {
    "collect_coal",
    "collect_diamond",
    "collect_drink",
    "collect_iron",
    "collect_sapling",
    "collect_stone",
    "collect_wood",
    "defeat_skeleton",
    "defeat_zombie",
    "eat_cow",
    "eat_plant",
    "make_iron_pickaxe",
    "make_iron_sword",
    "make_stone_pickaxe",
    "make_stone_sword",
    "make_wood_pickaxe",
    "make_wood_sword",
    "place_furnace",
    "place_plant",
    "place_stone",
    "place_table",
    "wake_up",
    "collect_sapphire",
    "collect_ruby",
    "open_chest",
    "make_diamond_pickaxe",
    "make_diamond_sword",
    "make_bow",
    "make_arrow",
    "make_iron_armor",
    "make_diamond_armor",
    "defeat_orc_soldier",
    "defeat_orc_mage",
    "defeat_knight",
    "defeat_knight_archer",
    "defeat_troll",
    "drink_potion",
    "gain_xp",
    "reach_level",
}
MONTY_MODULES = {"collect_wood_shaped_v1", "achievement_ladder_v1", "sparse_classic", "goal_binary_v1"}
MONTY_ACTION_PENALTIES = {"unknown_action", "terminal"}
REWARD_MODES = frozenset({"standard", "goal_binary"})
RULE_REWARD_DEFAULTS = {
    "achievement": 1.0,
    "invalid_action": 0.0,
    "death": 0.0,
    "step": 0.0,
}
CHECKPOINT_EVERY_N_STEPS_DEFAULT = 10

BASE_MATERIALS = {
    "water",
    "grass",
    "stone",
    "path",
    "sand",
    "tree",
    "lava",
    "coal",
    "iron",
    "diamond",
    "table",
    "furnace",
}
CRAFTAX_ITEM_TERRAIN = {"sapphire", "ruby"}
MATERIALS = BASE_MATERIALS | CRAFTAX_ITEM_TERRAIN | {"chest"}

CLASSIC_INVENTORY_SLOTS = {
    "health",
    "food",
    "drink",
    "energy",
    "sapling",
    "wood",
    "stone",
    "coal",
    "iron",
    "diamond",
    "wood_pickaxe",
    "stone_pickaxe",
    "iron_pickaxe",
    "diamond_pickaxe",
    "wood_sword",
    "stone_sword",
    "iron_sword",
    "diamond_sword",
}
CRAFTAX_ITEM_INVENTORY_SLOTS = {
    "sapphire",
    "ruby",
    "bow",
    "arrows",
    "armor_helmet",
    "armor_chestplate",
    "armor_leggings",
    "armor_boots",
    "potion_red",
    "potion_green",
    "potion_blue",
    "potion_pink",
    "potion_cyan",
    "potion_yellow",
    "stat_points",
}
CRAFTAX_RECIPE_INVENTORY_SLOTS = {
    "diamond_pickaxe",
    "diamond_sword",
    "bow",
    "armor_helmet",
    "armor_chestplate",
    "armor_leggings",
    "armor_boots",
}
CRAFTAX_POTION_INVENTORY_SLOTS = {
    "potion_red",
    "potion_green",
    "potion_blue",
    "potion_pink",
    "potion_cyan",
    "potion_yellow",
}
CRAFTAX_XP_INVENTORY_SLOTS = {"xp", "level", "stat_points"}
CRAFTAX_ONLY_ACTIONS = {
    "make_bow",
    "make_arrow",
    "make_iron_armor",
    "make_diamond_armor",
    "shoot_arrow",
    "drink_potion_red",
    "drink_potion_green",
    "drink_potion_blue",
    "drink_potion_pink",
    "drink_potion_cyan",
    "drink_potion_yellow",
}


def _substrate_profile_from_rules(rules: dict[str, Any]) -> str:
    return str(rules.get("substrate_profile") or "classic")


def _resolved_probe(rules: dict[str, Any]) -> dict[str, Any]:
    return {"substrate_profile": _substrate_profile_from_rules(rules), "rules": rules}


def _craftax_rule_bool(craftax: dict[str, Any], key: str, default: bool) -> bool:
    value = craftax.get(key, default)
    return bool(value) if isinstance(value, bool) else default


def craftax_items_enabled_for_resolved(resolved: dict[str, Any]) -> bool:
    if resolved.get("substrate_profile") != "craftax_partial":
        return False
    craftax = dict(resolved.get("rules", {}).get("craftax", {}))
    return _craftax_rule_bool(craftax, "enabled", True) and _craftax_rule_bool(craftax, "items_enabled", True)


def craftax_recipes_enabled_for_resolved(resolved: dict[str, Any]) -> bool:
    if not craftax_items_enabled_for_resolved(resolved):
        return False
    crafting = dict(resolved.get("rules", {}).get("crafting", {}))
    return bool(crafting.get("craftax_recipes", False))


def craftax_potions_enabled_for_resolved(resolved: dict[str, Any]) -> bool:
    if not craftax_items_enabled_for_resolved(resolved):
        return False
    craftax = dict(resolved.get("rules", {}).get("craftax", {}))
    return _craftax_rule_bool(craftax, "potions_enabled", True)


def craftax_chests_enabled_for_resolved(resolved: dict[str, Any]) -> bool:
    if not craftax_items_enabled_for_resolved(resolved):
        return False
    craftax = dict(resolved.get("rules", {}).get("craftax", {}))
    return _craftax_rule_bool(craftax, "chests_enabled", True)


def craftax_xp_enabled_for_resolved(resolved: dict[str, Any]) -> bool:
    if resolved.get("substrate_profile") != "craftax_partial":
        return False
    craftax = dict(resolved.get("rules", {}).get("craftax", {}))
    return _craftax_rule_bool(craftax, "enabled", True) and _craftax_rule_bool(craftax, "xp_enabled", True)


def craftax_combat_enabled_for_resolved(resolved: dict[str, Any]) -> bool:
    if resolved.get("substrate_profile") != "craftax_partial":
        return False
    craftax = dict(resolved.get("rules", {}).get("craftax", {}))
    return _craftax_rule_bool(craftax, "enabled", True) and _craftax_rule_bool(craftax, "combat_enabled", True)


def craftax_player_projectiles_enabled_for_resolved(resolved: dict[str, Any]) -> bool:
    return craftax_combat_enabled_for_resolved(resolved) and craftax_items_enabled_for_resolved(resolved)


def craftax_achievements_enabled_for_resolved(resolved: dict[str, Any]) -> bool:
    achievements = dict(resolved.get("rules", {}).get("achievements", {}))
    include_craftax = achievements.get("enabled", "classic") == "classic_plus_craftax"
    if resolved.get("substrate_profile") != "craftax_partial":
        return False
    craftax = dict(resolved.get("rules", {}).get("craftax", {}))
    return include_craftax and _craftax_rule_bool(craftax, "enabled", True) and _craftax_rule_bool(
        craftax, "achievements_enabled", True
    )


def is_craftax_achievement(name: str) -> bool:
    return name in {
        "collect_sapphire",
        "collect_ruby",
        "open_chest",
        "make_bow",
        "make_arrow",
        "make_iron_armor",
        "make_diamond_armor",
        "defeat_orc_soldier",
        "defeat_orc_mage",
        "defeat_knight",
        "defeat_knight_archer",
        "defeat_troll",
        "drink_potion",
        "gain_xp",
        "reach_level",
    }


def material_allowed_for_rules(material: str, rules: dict[str, Any]) -> bool:
    return material_allowed_for_resolved(material, _resolved_probe(rules))


def material_allowed_for_resolved(material: str, resolved: dict[str, Any]) -> bool:
    if material in BASE_MATERIALS:
        return True
    if material == "chest":
        return craftax_chests_enabled_for_resolved(resolved)
    if material in CRAFTAX_ITEM_TERRAIN:
        return craftax_items_enabled_for_resolved(resolved)
    return False


def action_allowed_for_resolved(action: str, resolved: dict[str, Any]) -> bool:
    if action not in CRAFTAX_ONLY_ACTIONS:
        return True
    if action.startswith("drink_potion"):
        return craftax_potions_enabled_for_resolved(resolved)
    if action in {"make_bow", "make_arrow", "make_iron_armor", "make_diamond_armor"}:
        return craftax_recipes_enabled_for_resolved(resolved)
    if action == "shoot_arrow":
        return craftax_player_projectiles_enabled_for_resolved(resolved)
    return False


def inventory_slot_visible_for_resolved(slot: str, resolved: dict[str, Any]) -> bool:
    if slot in CLASSIC_INVENTORY_SLOTS:
        return True
    if not craftax_items_enabled_for_resolved(resolved):
        return False
    if slot in CRAFTAX_RECIPE_INVENTORY_SLOTS:
        return craftax_recipes_enabled_for_resolved(resolved)
    if slot in CRAFTAX_POTION_INVENTORY_SLOTS:
        return craftax_potions_enabled_for_resolved(resolved)
    if slot in CRAFTAX_XP_INVENTORY_SLOTS:
        return craftax_xp_enabled_for_resolved(resolved)
    return slot in CRAFTAX_ITEM_INVENTORY_SLOTS


def project_inventory_for_resolved(inventory: dict[str, int], resolved: dict[str, Any]) -> dict[str, int]:
    return {key: int(value) for key, value in inventory.items() if inventory_slot_visible_for_resolved(key, resolved)}


def project_achievements_for_resolved(achievements: dict[str, int], resolved: dict[str, Any]) -> dict[str, int]:
    return {
        key: int(value)
        for key, value in achievements.items()
        if not is_craftax_achievement(key) or craftax_achievements_enabled_for_resolved(resolved)
    }


@dataclass(frozen=True)
class ResolvedTask:
    task_id: str
    scenario_id: str
    seed: int
    width: int
    height: int
    view_radius: int
    max_steps: int
    world: dict[str, Any]
    rules: dict[str, Any]
    readouts: dict[str, Any]
    stream: dict[str, Any]
    monty_reward: dict[str, Any] | None
    checkpoint_every_n_steps: int
    substrate_profile: str
    substrate_config: dict[str, Any]
    adapter_hooks: dict[str, Any]
    unsupported_rules: list[str]
    config_hash: str
    resolved_json: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "view_radius": self.view_radius,
            "max_steps": self.max_steps,
            "world": self.world,
            "rules": self.rules,
            "readouts": self.readouts,
            "stream": self.stream,
            "monty_reward": self.monty_reward,
            "checkpoint_every_n_steps": self.checkpoint_every_n_steps,
            "substrate_profile": self.substrate_profile,
            "substrate_config": self.substrate_config,
            "adapter_hooks": self.adapter_hooks,
            "unsupported_rules": self.unsupported_rules,
            "config_hash": self.config_hash,
            "resolved_json": self.resolved_json,
        }


def resolve_task(task: dict[str, Any], seed_override: int | None = None) -> ResolvedTask:
    schema = task.get("schema") or task.get("schema_version")
    if schema not in (None, "gamebench.task.crafter.v1"):
        raise ValueError(f"unsupported crafter task schema: {schema}")

    task_id = str(task.get("task_id", "crafter_manual"))
    scenario_id = str(task.get("scenario_id", task_id))
    world = _resolve_world(dict(task.get("world", {})))
    if seed_override is not None:
        world["seed"] = int(seed_override)
    seed = int(world.get("seed", 0))
    rules = _resolve_rules(dict(task.get("rules", {})))
    readouts = _resolve_readouts(task.get("readouts", {"symbolic": "symbolic_compact", "visual": False}))
    stream = {
        "enabled": False,
        "every_n_steps": 1,
        "persist_frames": False,
    }
    _deep_merge(stream, dict(task.get("stream", {})))

    width = _positive_int(world.get("width", 64), "world.width")
    height = _positive_int(world.get("height", 64), "world.height")
    view_radius = _nonnegative_int(world.get("view_radius", 4), "world.view_radius")
    max_steps = _positive_int(task.get("max_steps", world.get("max_steps", 10000)), "max_steps")
    if "tiles" in world and "map" in world:
        raise ValueError("world.tiles and world.map are mutually exclusive")
    if "tiles" in world:
        world["map"] = _resolve_world_map({"rows": world.pop("tiles")}, width=width, height=height, rules=rules)
    elif "map" in world:
        world["map"] = _resolve_world_map(world["map"], width=width, height=height, rules=rules)
    if "map" in world:
        _validate_authored_map_profile(world["map"], rules)
    if "initial_state" in world:
        world["initial_state"] = _resolve_initial_state(world["initial_state"], width=width, height=height)
    substrate_profile = str(rules.get("substrate_profile") or world.get("worldgen", {}).get("profile") or "classic")
    if substrate_profile not in {"classic", "craftax_partial"}:
        raise ValueError(f"unsupported substrate_profile: {substrate_profile}")

    full_world_state = bool(readouts.get("full_world_state", False))
    worldgen_densities = _resolve_worldgen_densities(world)
    runtime_rules = _resolve_substrate_runtime_rules(rules)
    substrate_config = {
        "world_width": width,
        "world_height": height,
        "view_radius": view_radius,
        "max_steps": max_steps,
        "profile": None if substrate_profile == "classic" else substrate_profile,
        "full_world_state": full_world_state,
        **worldgen_densities,
        **runtime_rules,
    }
    adapter_hooks = _adapter_hooks(rules)
    unsupported_rules = _unsupported_rules(world, rules, adapter_hooks)
    if unsupported_rules and bool(rules.get("strict_rule_support", False)):
        joined = ", ".join(unsupported_rules)
        raise ValueError(f"resolved task requires unsupported Crafter rule knobs: {joined}")
    monty_reward = _resolve_monty_reward(task.get("monty_reward"))
    rules, monty_reward, reward_mode, objective = _apply_reward_mode(task, rules, monty_reward)

    resolved = {
        "schema": "gamebench.task.crafter.v1",
        "task_id": task_id,
        "scenario_id": scenario_id,
        "seed": seed,
        "reward_mode": reward_mode,
        "objective": objective,
        "world": world,
        "rules": rules,
        "readouts": readouts,
        "stream": stream,
        "monty_reward": copy.deepcopy(monty_reward),
        "agent_policy": copy.deepcopy(task.get("agent_policy")),
        "checkpoint_every_n_steps": _nonnegative_int(
            task.get("checkpoint_every_n_steps", CHECKPOINT_EVERY_N_STEPS_DEFAULT),
            "checkpoint_every_n_steps",
        ),
        "substrate": {
            "engine": "gamebench-native",
            "profile": substrate_profile,
            "config": substrate_config,
            "adapter_hooks": adapter_hooks,
            "unsupported_rules": unsupported_rules,
        },
    }
    digest = hashlib.sha256(canonical_json(resolved).encode()).hexdigest()
    resolved["config_hash"] = f"sha256:{digest}"
    return ResolvedTask(
        task_id=task_id,
        scenario_id=scenario_id,
        seed=seed,
        width=width,
        height=height,
        view_radius=view_radius,
        max_steps=max_steps,
        world=world,
        rules=rules,
        readouts=readouts,
        stream=stream,
        monty_reward=copy.deepcopy(monty_reward),
        checkpoint_every_n_steps=_nonnegative_int(
            task.get("checkpoint_every_n_steps", CHECKPOINT_EVERY_N_STEPS_DEFAULT),
            "checkpoint_every_n_steps",
        ),
        substrate_profile=substrate_profile,
        substrate_config=substrate_config,
        adapter_hooks=adapter_hooks,
        unsupported_rules=unsupported_rules,
        config_hash=resolved["config_hash"],
        resolved_json=resolved,
    )


def load_task_path(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def task_for_suite_seed(suite: dict[str, Any], seed: int) -> dict[str, Any]:
    template_path = TASK_DIR / str(suite["task_template"])
    task = load_task_path(template_path)
    task.setdefault("world", {})
    task["world"]["use_default"] = suite.get("world_default", task["world"].get("use_default", "policy_dev_small"))
    task["world"]["seed"] = seed
    task["world"]["max_steps"] = int(suite.get("max_steps", task["world"].get("max_steps", 120)))
    task["rules"] = {"base": suite.get("rules_default", "no_homeostasis")}
    if "reward_mode" in suite:
        task["reward_mode"] = str(suite["reward_mode"])
    if "objective" in suite:
        task["objective"] = str(suite["objective"])
    objective = suite.get("objective")
    task_prefix = str(task.get("task_id", "crafter_policy_dev"))
    if objective:
        task_prefix = f"{task_prefix}_{objective}"
    task["task_id"] = f"{task_prefix}_{seed}"
    task["scenario_id"] = f"{task.get('scenario_id', task_prefix)}_{seed}"
    return task


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _resolve_world(world_spec: dict[str, Any]) -> dict[str, Any]:
    default_name = world_spec.get("use_default")
    if default_name is None:
        if "width" not in world_spec or "height" not in world_spec:
            default_name = "classic_64"
    if default_name is not None:
        worlds = json.loads((TASK_DIR / "defaults" / "worlds.json").read_text())["worlds"]
        if str(default_name) not in worlds:
            raise FileNotFoundError(f"missing world default: {default_name}")
        merged = copy.deepcopy(worlds[str(default_name)])
        _deep_merge(merged, {key: value for key, value in world_spec.items() if key != "use_default"})
        merged["default_ref"] = str(default_name)
        return merged
    return copy.deepcopy(world_spec)


def _resolve_worldgen_densities(world: dict[str, Any]) -> dict[str, float]:
    worldgen = dict(world.get("worldgen", {}))
    return {
        key: _nonnegative_float(worldgen.get(key, 1.0), f"world.worldgen.{key}")
        for key in WORLDGEN_DENSITY_KEYS
    }


def _resolve_world_map(raw: Any, *, width: int, height: int, rules: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("world.map must be an object")
    unknown = set(raw) - {"rows", "tiles", "legend"}
    if unknown:
        raise ValueError(f"unsupported world.map keys: {', '.join(sorted(unknown))}")
    if "rows" in raw and "tiles" in raw:
        raise ValueError("world.map.rows and world.map.tiles are mutually exclusive")
    rows_raw = raw.get("rows", raw.get("tiles"))
    if rows_raw is None:
        raise ValueError("world.map requires rows or tiles")
    if not isinstance(rows_raw, list):
        raise ValueError("world.map rows must be an array")
    if len(rows_raw) != height:
        raise ValueError(f"world.map must have exactly {height} rows")

    legend = dict(DEFAULT_WORLD_MAP_LEGEND)
    if "legend" in raw:
        legend_raw = raw["legend"]
        if not isinstance(legend_raw, dict):
            raise ValueError("world.map.legend must be an object")
        for key, value in legend_raw.items():
            if not isinstance(key, str) or len(key) != 1:
                raise ValueError("world.map.legend keys must be single-character strings")
            material = str(value).lower()
            if material not in MATERIALS:
                raise ValueError(f"unsupported world.map.legend material: {material}")
            if not material_allowed_for_rules(material, rules):
                raise ValueError(
                    f"world.map.legend material {material} is unsupported for substrate profile "
                    f"{_substrate_profile_from_rules(rules)}"
                )
            legend[key] = material

    tiles: list[list[str]] = []
    for y, row in enumerate(rows_raw):
        if isinstance(row, str):
            if len(row) != width:
                raise ValueError(f"world.map row {y} must be exactly {width} characters")
            tiles.append([
                _resolve_world_map_symbol(symbol, legend, rules, f"world.map.rows[{y}][{x}]")
                for x, symbol in enumerate(row)
            ])
            continue
        if not isinstance(row, list):
            raise ValueError(f"world.map row {y} must be a string or array")
        if len(row) != width:
            raise ValueError(f"world.map row {y} must have exactly {width} columns")
        tiles.append([
            _resolve_world_map_cell(cell, legend, rules, f"world.map.rows[{y}][{x}]")
            for x, cell in enumerate(row)
        ])
    return {
        "encoding": "gamebench.crafter.world_map.v1",
        "tiles": tiles,
    }


def _validate_authored_map_profile(world_map: dict[str, Any], rules: dict[str, Any]) -> None:
    tiles = world_map.get("tiles")
    if not isinstance(tiles, list):
        raise ValueError("world.map.tiles must be an array")
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            raise ValueError(f"world.map row {y} must be an array")
        for x, cell in enumerate(row):
            if not isinstance(cell, str):
                raise ValueError(f"world.map.tiles[{y}][{x}] must be a material string")
            if not material_allowed_for_rules(cell, rules):
                raise ValueError(
                    f"world.map.tiles[{y}][{x}] is {cell} while profile disallows Craftax terrain"
                )


def _resolve_world_map_symbol(symbol: str, legend: dict[str, str], rules: dict[str, Any], field: str) -> str:
    if symbol not in legend:
        raise ValueError(f"{field} has no world.map.legend entry: {symbol!r}")
    material = legend[symbol]
    if not material_allowed_for_rules(material, rules):
        raise ValueError(
            f"{field} material {material} is unsupported for substrate profile "
            f"{_substrate_profile_from_rules(rules)}"
        )
    return material


def _resolve_world_map_cell(cell: Any, legend: dict[str, str], rules: dict[str, Any], field: str) -> str:
    if not isinstance(cell, str):
        raise ValueError(f"{field} must be a material name or legend symbol")
    material = cell.lower()
    if material in MATERIALS:
        if not material_allowed_for_rules(material, rules):
            raise ValueError(
                f"{field} material {material} is unsupported for substrate profile "
                f"{_substrate_profile_from_rules(rules)}"
            )
        return material
    if len(cell) == 1 and cell in legend:
        material = legend[cell]
        if not material_allowed_for_rules(material, rules):
            raise ValueError(
                f"{field} material {material} is unsupported for substrate profile "
                f"{_substrate_profile_from_rules(rules)}"
            )
        return material
    raise ValueError(f"unsupported {field} material: {cell}")


def _resolve_substrate_runtime_rules(rules: dict[str, Any]) -> dict[str, float | int | bool]:
    survival = dict(rules.get("survival", {}))
    day_night = dict(rules.get("day_night", {}))
    mobs = dict(rules.get("mobs", {}))
    mobs_enabled = _bool(mobs.get("enabled", True), "rules.mobs.enabled")
    resolved: dict[str, float | int | bool] = {
        "hunger_enabled": _bool(survival.get("hunger_enabled", True), "rules.survival.hunger_enabled"),
        "thirst_enabled": _bool(survival.get("thirst_enabled", True), "rules.survival.thirst_enabled"),
        "fatigue_enabled": _bool(survival.get("fatigue_enabled", True), "rules.survival.fatigue_enabled"),
        "health_enabled": _bool(survival.get("health_enabled", True), "rules.survival.health_enabled"),
        "day_night_cycle": _bool(day_night.get("enabled", True), "rules.day_night.enabled"),
        "day_cycle_period": _positive_int(day_night.get("period", 300), "rules.day_night.period"),
        "mobs_enabled": mobs_enabled,
        "zombie_spawn_rate": (
            _nonnegative_float(mobs.get("zombie_spawn_rate", 0.3), "rules.mobs.zombie_spawn_rate")
            if mobs_enabled
            else 0.0
        ),
        "cow_spawn_rate": (
            _nonnegative_float(mobs.get("cow_spawn_rate", 0.01), "rules.mobs.cow_spawn_rate")
            if mobs_enabled
            else 0.0
        ),
    }
    if "hunger_rate" in survival:
        resolved["hunger_rate"] = _positive_int(survival["hunger_rate"], "rules.survival.hunger_rate")
    if "thirst_rate" in survival:
        resolved["thirst_rate"] = _positive_int(survival["thirst_rate"], "rules.survival.thirst_rate")
    for key, default in (
        ("zombie_despawn_rate", 0.4),
        ("cow_despawn_rate", 0.01),
        ("zombie_damage_mult", 1.0),
        ("arrow_damage_mult", 1.0),
        ("player_damage_mult", 1.0),
    ):
        if key in mobs:
            resolved[key] = _nonnegative_float(mobs.get(key, default), f"rules.mobs.{key}")
    return resolved


def _resolve_initial_state(raw: Any, *, width: int, height: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("world.initial_state must be an object")
    unknown = set(raw) - {"player", "inventory", "tiles", "entities", "achievements"}
    if unknown:
        raise ValueError(f"unsupported world.initial_state keys: {', '.join(sorted(unknown))}")

    resolved: dict[str, Any] = {}
    player_raw = raw.get("player")
    if player_raw is not None:
        if not isinstance(player_raw, dict):
            raise ValueError("world.initial_state.player must be an object")
        player_unknown = set(player_raw) - {"pos", "facing"}
        if player_unknown:
            raise ValueError(f"unsupported world.initial_state.player keys: {', '.join(sorted(player_unknown))}")
        player: dict[str, Any] = {}
        if "pos" in player_raw:
            player["pos"] = _resolve_position(player_raw["pos"], "world.initial_state.player.pos", width=width, height=height)
        if "facing" in player_raw:
            player["facing"] = _resolve_facing(player_raw["facing"], "world.initial_state.player.facing")
        if player:
            resolved["player"] = player

    if "inventory" in raw:
        inventory_raw = raw["inventory"]
        if not isinstance(inventory_raw, dict):
            raise ValueError("world.initial_state.inventory must be an object")
        inventory: dict[str, int] = {}
        for key in sorted(inventory_raw):
            if key not in INVENTORY_KEYS:
                raise ValueError(f"unsupported inventory slot in world.initial_state: {key}")
            value = _nonnegative_int(inventory_raw[key], f"world.initial_state.inventory.{key}")
            limit = MAX_U32 if key == "xp" else 9
            if value > limit:
                raise ValueError(f"world.initial_state.inventory.{key} must be <= {limit}")
            inventory[key] = value
        resolved["inventory"] = inventory

    if "tiles" in raw:
        tiles_raw = raw["tiles"]
        if not isinstance(tiles_raw, list):
            raise ValueError("world.initial_state.tiles must be an array")
        seen: set[tuple[int, int]] = set()
        tiles: list[dict[str, Any]] = []
        for idx, patch in enumerate(tiles_raw):
            if not isinstance(patch, dict):
                raise ValueError(f"world.initial_state.tiles[{idx}] must be an object")
            patch_unknown = set(patch) - {"pos", "kind"}
            if patch_unknown:
                raise ValueError(
                    f"unsupported world.initial_state.tiles[{idx}] keys: {', '.join(sorted(patch_unknown))}"
                )
            pos = _resolve_position(patch.get("pos"), f"world.initial_state.tiles[{idx}].pos", width=width, height=height)
            pos_key = (pos[0], pos[1])
            if pos_key in seen:
                raise ValueError(f"duplicate world.initial_state tile patch at {pos}")
            seen.add(pos_key)
            kind = str(patch.get("kind", "")).lower()
            if kind not in MATERIALS:
                raise ValueError(f"unsupported material in world.initial_state.tiles[{idx}].kind: {kind}")
            tiles.append({"pos": pos, "kind": kind})
        resolved["tiles"] = tiles

    if "entities" in raw:
        entities_raw = raw["entities"]
        if not isinstance(entities_raw, list):
            raise ValueError("world.initial_state.entities must be an array")
        seen: set[tuple[int, int]] = set()
        entities: list[dict[str, Any]] = []
        for idx, entity_raw in enumerate(entities_raw):
            if not isinstance(entity_raw, dict):
                raise ValueError(f"world.initial_state.entities[{idx}] must be an object")
            entity_unknown = set(entity_raw) - {"kind", "pos", "health"}
            if entity_unknown:
                raise ValueError(
                    f"unsupported world.initial_state.entities[{idx}] keys: {', '.join(sorted(entity_unknown))}"
                )
            kind = str(entity_raw.get("kind", "")).lower()
            if kind not in ENTITY_KINDS:
                raise ValueError(f"unsupported entity kind in world.initial_state.entities[{idx}].kind: {kind}")
            pos = _resolve_position(entity_raw.get("pos"), f"world.initial_state.entities[{idx}].pos", width=width, height=height)
            pos_key = (pos[0], pos[1])
            if pos_key in seen:
                raise ValueError(f"duplicate world.initial_state entity at {pos}")
            seen.add(pos_key)
            health = _positive_int(
                entity_raw.get("health", ENTITY_DEFAULT_HEALTH[kind]),
                f"world.initial_state.entities[{idx}].health",
            )
            if health > MAX_ENTITY_HEALTH:
                raise ValueError(
                    f"world.initial_state.entities[{idx}].health must be <= {MAX_ENTITY_HEALTH}"
                )
            entities.append({"kind": kind, "pos": pos, "health": health})
        resolved["entities"] = entities

    if "achievements" in raw:
        achievements_raw = raw["achievements"]
        if not isinstance(achievements_raw, dict):
            raise ValueError("world.initial_state.achievements must be an object")
        achievements: dict[str, int] = {}
        for key in sorted(achievements_raw):
            if key not in ACHIEVEMENT_KEYS:
                raise ValueError(f"unsupported achievement in world.initial_state: {key}")
            value = _nonnegative_int(achievements_raw[key], f"world.initial_state.achievements.{key}")
            if value > MAX_U32:
                raise ValueError(f"world.initial_state.achievements.{key} must be <= {MAX_U32}")
            achievements[key] = value
        resolved["achievements"] = achievements

    return resolved


def _resolve_monty_reward(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("monty_reward must be an object")
    unknown = set(raw) - {
        "kind",
        "use_default",
        "module",
        "entry",
        "achievement_default",
        "achievement_rewards",
        "resource_rewards",
        "action_penalties",
    }
    if unknown:
        raise ValueError(f"unsupported monty_reward keys: {', '.join(sorted(unknown))}")

    default_name = raw.get("use_default")
    if default_name is None and isinstance(raw.get("module"), str) and raw["module"] in MONTY_MODULES:
        default_name = raw["module"]
    source = copy.deepcopy(raw)
    if default_name is not None:
        source = _load_monty_reward_default(str(default_name))
        _deep_merge(source, {key: value for key, value in raw.items() if key != "use_default"})
        source["default_ref"] = str(default_name)

    kind = str(source.get("kind", "monty_python"))
    if kind != "monty_python":
        raise ValueError(f"unsupported monty_reward.kind: {kind}")
    entry = str(source.get("entry", "score_transition"))
    if entry != "score_transition":
        raise ValueError(f"unsupported monty_reward.entry: {entry}")

    resolved: dict[str, Any] = {"kind": kind, "entry": entry}
    if "default_ref" in source:
        resolved["default_ref"] = str(source["default_ref"])
    if "module" in source:
        module = str(source["module"])
        if module not in MONTY_MODULES:
            raise ValueError(f"unsupported monty_reward.module: {module}")
        resolved["module"] = module
    if "achievement_default" in source:
        resolved["achievement_default"] = _finite_float(
            source["achievement_default"],
            "monty_reward.achievement_default",
        )

    for section, allowed in (
        ("achievement_rewards", ACHIEVEMENT_KEYS),
        ("resource_rewards", INVENTORY_KEYS),
        ("action_penalties", MONTY_ACTION_PENALTIES),
    ):
        if section not in source:
            continue
        values = source[section]
        if not isinstance(values, dict):
            raise ValueError(f"monty_reward.{section} must be an object")
        section_values: dict[str, float] = {}
        for key in sorted(values):
            name = str(key)
            if name not in allowed:
                raise ValueError(f"unsupported monty_reward.{section} key: {name}")
            section_values[name] = _finite_float(values[key], f"monty_reward.{section}.{name}")
        resolved[section] = section_values
    return resolved


def _normalize_objective(raw: Any) -> str | None:
    if raw is None:
        return None
    label = str(raw).strip()
    return label or None


def _apply_reward_mode(
    task: dict[str, Any],
    rules: dict[str, Any],
    monty_reward: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, str, str | None]:
    reward_mode = str(task.get("reward_mode", "standard")).strip() or "standard"
    if reward_mode not in REWARD_MODES:
        raise ValueError(f"unsupported reward_mode: {reward_mode}")
    objective = _normalize_objective(task.get("objective"))
    patched_rules = copy.deepcopy(rules)
    patched_monty = copy.deepcopy(monty_reward) if monty_reward is not None else None

    if reward_mode == "standard":
        return patched_rules, patched_monty, reward_mode, objective

    if objective is None:
        raise ValueError("reward_mode goal_binary requires objective")
    if objective not in ACHIEVEMENT_KEYS:
        raise ValueError(f"unsupported objective: {objective}")

    reward_overrides = dict(patched_rules.get("rewards", {}))
    reward_overrides["achievement"] = 0.0
    patched_rules["rewards"] = _resolve_rule_rewards(reward_overrides)

    if patched_monty is None:
        patched_monty = _load_monty_reward_default("goal_binary_v1")
    else:
        patched_monty = _resolve_monty_reward(patched_monty) or patched_monty
    patched_monty = copy.deepcopy(patched_monty)
    patched_monty["achievement_default"] = 0.0
    achievement_rewards = dict(patched_monty.get("achievement_rewards", {}))
    achievement_rewards[objective] = 1.0
    patched_monty["achievement_rewards"] = achievement_rewards
    return patched_rules, patched_monty, reward_mode, objective


def _load_monty_reward_default(name: str) -> dict[str, Any]:
    if name not in MONTY_MODULES:
        raise ValueError(f"unsupported monty_reward.use_default: {name}")
    path = TASK_DIR / "defaults" / "monty_rewards" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"missing monty reward default: {path}")
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"monty reward default must be an object: {path}")
    return raw


def _resolve_position(value: Any, field: str, *, width: int, height: int) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{field} must be a two-item [x, y] array")
    x = _nonnegative_int(value[0], f"{field}[0]")
    y = _nonnegative_int(value[1], f"{field}[1]")
    if x >= width or y >= height:
        raise ValueError(f"{field} must be within the configured world bounds")
    return [x, y]


def _resolve_facing(value: Any, field: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{field} must be a two-item [dx, dy] array")
    dx = _int(value[0], f"{field}[0]")
    dy = _int(value[1], f"{field}[1]")
    if (dx, dy) not in FACING_VALUES:
        raise ValueError(f"{field} must be one of [1,0], [-1,0], [0,1], or [0,-1]")
    return [dx, dy]


def _resolve_rules(rules_spec: dict[str, Any]) -> dict[str, Any]:
    base_name = str(rules_spec.get("base", "classic"))
    merged = _load_rule_default(base_name, seen=set())
    _deep_merge(merged, {key: value for key, value in rules_spec.items() if key not in {"base", "overrides"}})
    overrides = rules_spec.get("overrides")
    if overrides is not None:
        if not isinstance(overrides, dict):
            raise ValueError("rules.overrides must be an object")
        _deep_merge(merged, overrides)
    merged["rewards"] = _resolve_rule_rewards(merged.get("rewards", {}))
    merged["base_ref"] = base_name
    return merged


def _resolve_rule_rewards(raw: Any) -> dict[str, float]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("rules.rewards must be an object")
    unknown = set(raw) - set(RULE_REWARD_DEFAULTS)
    if unknown:
        raise ValueError(f"unsupported rules.rewards keys: {', '.join(sorted(unknown))}")
    return {
        key: _finite_float(raw.get(key, default), f"rules.rewards.{key}")
        for key, default in RULE_REWARD_DEFAULTS.items()
    }


def _load_rule_default(name: str, *, seen: set[str]) -> dict[str, Any]:
    if name in seen:
        raise ValueError(f"rules base cycle: {name}")
    seen.add(name)
    path = TASK_DIR / "defaults" / "rules" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"missing rules default: {path}")
    doc = json.loads(path.read_text())
    parent = doc.get("base")
    if parent:
        merged = _load_rule_default(str(parent), seen=seen)
        _deep_merge(merged, {key: value for key, value in doc.items() if key != "base"})
        return merged
    return doc


def _resolve_readouts(readout_spec: Any) -> dict[str, Any]:
    profiles = json.loads((TASK_DIR / "defaults" / "readouts.json").read_text())["profiles"]
    if isinstance(readout_spec, str):
        base = copy.deepcopy(profiles[readout_spec])
        base["profile_ref"] = readout_spec
        return base
    spec = dict(readout_spec or {})
    symbolic = spec.get("symbolic", "symbolic_compact")
    if isinstance(symbolic, str):
        base = copy.deepcopy(profiles[symbolic])
        base["profile_ref"] = symbolic
    else:
        base = copy.deepcopy(profiles["symbolic_compact"])
    if isinstance(spec.get("visual"), str):
        base["visual_profile_ref"] = spec["visual"]
        base["visual"] = True
    elif "visual" in spec:
        base["visual"] = bool(spec["visual"])
    _deep_merge(base, {key: value for key, value in spec.items() if key not in {"symbolic", "visual"}})
    return base


def _adapter_hooks(rules: dict[str, Any]) -> dict[str, Any]:
    return {
        "freeze_hunger": False,
        "freeze_thirst": False,
        "freeze_fatigue": False,
        "suppress_mobs": False,
        "suppress_hostile_mobs": False,
        "freeze_daylight": False,
    }


def _unsupported_rules(world: dict[str, Any], rules: dict[str, Any], adapter_hooks: dict[str, Any]) -> list[str]:
    unsupported: list[str] = []
    craftax = dict(rules.get("craftax", {}))
    if craftax.get("enabled") is False and rules.get("substrate_profile") == "craftax_partial":
        unsupported.append("craftax.enabled=false with craftax_partial substrate")
    return unsupported


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _finite_float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _nonnegative_float(value: Any, field: str) -> float:
    number = _finite_float(value, field)
    if number < 0:
        raise ValueError(f"{field} must be nonnegative")
    return number
