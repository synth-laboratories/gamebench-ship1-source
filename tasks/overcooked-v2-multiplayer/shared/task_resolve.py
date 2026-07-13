"""Task resolution for Overcooked v2 multiplayer symbolic gold."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from layout import ParsedLayout, load_layout


DEFAULTS_DIR = Path(__file__).resolve().parent.parent / "defaults"

RECIPE_TABLE: dict[str, dict[str, Any]] = {
    "simple_soup": {"ingredients": [0], "cook_time": 2},
    "trio_soup": {"ingredients": [0, 0, 0], "cook_time": 3},
    "mixed_soup": {"ingredients": [0, 1, 1], "cook_time": 3},
    "tomato_trio": {"ingredients": [1, 1, 1], "cook_time": 3},
    "fun_coord_0": {"ingredients": [0, 0, 2], "cook_time": 3},
    "fun_coord_1": {"ingredients": [1, 1, 3], "cook_time": 3},
    "more_fun_coord_1": {"ingredients": [0, 2, 2], "cook_time": 3},
}


@dataclass(frozen=True)
class ResolvedTask:
    task_id: str
    scenario_id: str
    seed: int
    layout: ParsedLayout
    agent_ids: tuple[str, ...]
    recipe_id: str
    recipe_ingredients: tuple[int, ...]
    required_onions: int
    cook_time: int
    max_steps: int
    partial_obs: bool
    view_radius: int
    hidden_recipe: bool
    stochastic_spawn: bool
    recipe_pool: tuple[str, ...]
    resample_on_delivery: bool
    target_deliveries: int
    wrong_delivery_penalty: float
    observation_profile: str
    indicator_activation_time: int
    indicator_activation_cost: float
    start_cooking_interaction: bool
    op_ingredient_permutations: bool
    indicate_successful_delivery: bool
    shaped_rewards: bool
    random_reset: bool
    urgency_cutoff: int
    config_hash: str
    episode_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "layout_id": self.layout.layout_id,
            "agent_ids": list(self.agent_ids),
            "recipe_id": self.recipe_id,
            "recipe_ingredients": list(self.recipe_ingredients),
            "required_onions": self.required_onions,
            "cook_time": self.cook_time,
            "max_steps": self.max_steps,
            "partial_obs": self.partial_obs,
            "view_radius": self.view_radius,
            "hidden_recipe": self.hidden_recipe,
            "stochastic_spawn": self.stochastic_spawn,
            "recipe_pool": list(self.recipe_pool),
            "resample_on_delivery": self.resample_on_delivery,
            "target_deliveries": self.target_deliveries,
            "wrong_delivery_penalty": self.wrong_delivery_penalty,
            "observation_profile": self.observation_profile,
            "indicator_activation_time": self.indicator_activation_time,
            "indicator_activation_cost": self.indicator_activation_cost,
            "start_cooking_interaction": self.start_cooking_interaction,
            "op_ingredient_permutations": self.op_ingredient_permutations,
            "indicate_successful_delivery": self.indicate_successful_delivery,
            "shaped_rewards": self.shaped_rewards,
            "random_reset": self.random_reset,
            "urgency_cutoff": self.urgency_cutoff,
            "config_hash": self.config_hash,
            "episode_id": self.episode_id,
        }


def _stable_hash(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def resolve_layout(task: dict[str, Any]) -> tuple[ParsedLayout, dict[str, Any]]:
    if task.get("layout"):
        layout_dict = dict(task["layout"])
        return load_layout(layout_dict), layout_dict
    layout_id = str(task.get("layout_id", "demo_tiny"))
    path = DEFAULTS_DIR / "layouts" / f"{layout_id}.json"
    layout_dict = {"layout_id": layout_id, **json.loads(path.read_text())}
    return load_layout(layout_dict), layout_dict


def recipe_params(recipe_id: str, overrides: dict[str, Any]) -> tuple[str, tuple[int, ...], int, int]:
    base = RECIPE_TABLE.get(recipe_id, RECIPE_TABLE["simple_soup"])
    ingredients_raw = overrides.get("recipe_ingredients", base.get("ingredients", [0]))
    ingredients = tuple(int(item) for item in ingredients_raw)
    cook_time = int(overrides.get("cook_time", base["cook_time"]))
    return recipe_id, ingredients, cook_time


def resolve_rules(task: dict[str, Any]) -> dict[str, Any]:
    rules = dict(task.get("rules", {"base": "cooperative_full_obs"}))
    base_name = str(rules.get("base", "cooperative_full_obs"))
    base_path = DEFAULTS_DIR / "rules" / f"{base_name}.json"
    merged: dict[str, Any] = {}
    if base_path.is_file():
        merged.update(json.loads(base_path.read_text()))
    merged.update(rules)
    overrides = dict(merged.get("overrides", {}))
    merged["overrides"] = overrides
    return merged


def resolve_task(task: dict[str, Any], seed_override: int | None = None) -> ResolvedTask:
    task_id = str(task.get("task_id", task.get("scenario_id", "manual")))
    scenario_id = str(task.get("scenario_id", task_id))
    seed = int(seed_override if seed_override is not None else task.get("seed", 0))
    layout, layout_doc = resolve_layout(task)
    agent_ids = tuple(sorted(layout.agent_starts.keys()))
    if not agent_ids:
        agent_ids = ("agent_0", "agent_1")

    rules = resolve_rules(task)
    overrides = dict(rules.get("overrides", {}))
    recipe_id = str(rules.get("recipe_id", overrides.get("recipe_id", "simple_soup")))
    if layout_doc.get("recipe_pool") and "recipe_pool" not in overrides and "recipe_pool" not in rules:
        overrides["recipe_pool"] = layout_doc["recipe_pool"]
    if layout_doc.get("recipe_pool") and recipe_id == "simple_soup" and "recipe_id" not in rules:
        recipe_id = str(layout_doc["recipe_pool"][0])
    recipe_id, recipe_ingredients, cook_time = recipe_params(recipe_id, overrides)
    required_onions = int(
        overrides.get(
            "required_onions",
            sum(1 for index in recipe_ingredients if index == 0),
        )
    )
    max_steps = int(overrides.get("max_steps", task.get("max_steps", 64)))
    partial_obs = bool(overrides.get("partial_obs", rules.get("partial_obs", False)))
    view_radius = int(overrides.get("view_radius", rules.get("view_radius", 2 if partial_obs else 0)))
    hidden_recipe = bool(overrides.get("hidden_recipe", rules.get("hidden_recipe", False)))
    stochastic_spawn = bool(overrides.get("stochastic_spawn", rules.get("stochastic_spawn", False)))
    pool_raw = overrides.get("recipe_pool", rules.get("recipe_pool"))
    recipe_pool = tuple(str(item) for item in pool_raw) if pool_raw else (recipe_id,)
    resample_on_delivery = bool(overrides.get("resample_on_delivery", rules.get("resample_on_delivery", False)))
    target_deliveries = int(overrides.get("target_deliveries", rules.get("target_deliveries", 1)))
    wrong_delivery_penalty = float(overrides.get("wrong_delivery_penalty", rules.get("wrong_delivery_penalty", 0.0)))
    readouts = dict(task.get("readouts", {}))
    observation_profile = str(
        overrides.get(
            "observation_profile",
            readouts.get("profile", rules.get("observation_profile", "symbolic_compact")),
        )
    )
    indicator_activation_time = int(
        overrides.get("indicator_activation_time", rules.get("indicator_activation_time", 10))
    )
    indicator_activation_cost = float(
        overrides.get("indicator_activation_cost", rules.get("indicator_activation_cost", 0.0))
    )
    start_cooking_interaction = bool(
        overrides.get("start_cooking_interaction", rules.get("start_cooking_interaction", False))
    )
    op_ingredient_permutations = bool(
        overrides.get("op_ingredient_permutations", rules.get("op_ingredient_permutations", False))
    )
    indicate_successful_delivery = bool(
        overrides.get("indicate_successful_delivery", rules.get("indicate_successful_delivery", False))
    )
    shaped_rewards = bool(overrides.get("shaped_rewards", rules.get("shaped_rewards", False)))
    random_reset = bool(overrides.get("random_reset", rules.get("random_reset", False)))
    urgency_cutoff = int(overrides.get("urgency_cutoff", rules.get("urgency_cutoff", 40)))

    material = (
        f"overcooked-v2:{task_id}:{seed}:{layout.layout_id}:"
        f"{':'.join(agent_ids)}:{recipe_id}:{','.join(map(str, recipe_ingredients))}:{cook_time}:{max_steps}:"
        f"{partial_obs}:{view_radius}:{hidden_recipe}:{stochastic_spawn}:{random_reset}:{urgency_cutoff}:"
        f"{','.join(recipe_pool)}:{resample_on_delivery}:{target_deliveries}:{wrong_delivery_penalty}:"
        f"{observation_profile}:{indicator_activation_time}:{indicator_activation_cost}:"
        f"{start_cooking_interaction}:{op_ingredient_permutations}:{indicate_successful_delivery}:{shaped_rewards}"
    )
    config_hash = _stable_hash(material)
    episode_id = _stable_hash(f"gamebench.overcooked-v2-multiplayer.episode:{task_id}:{seed}:{config_hash}", 32)
    return ResolvedTask(
        task_id=task_id,
        scenario_id=scenario_id,
        seed=seed,
        layout=layout,
        agent_ids=agent_ids,
        recipe_id=recipe_id,
        recipe_ingredients=recipe_ingredients,
        required_onions=required_onions,
        cook_time=cook_time,
        max_steps=max_steps,
        partial_obs=partial_obs,
        view_radius=view_radius,
        hidden_recipe=hidden_recipe,
        stochastic_spawn=stochastic_spawn,
        recipe_pool=recipe_pool,
        resample_on_delivery=resample_on_delivery,
        target_deliveries=target_deliveries,
        wrong_delivery_penalty=wrong_delivery_penalty,
        observation_profile=observation_profile,
        indicator_activation_time=indicator_activation_time,
        indicator_activation_cost=indicator_activation_cost,
        start_cooking_interaction=start_cooking_interaction,
        op_ingredient_permutations=op_ingredient_permutations,
        indicate_successful_delivery=indicate_successful_delivery,
        shaped_rewards=shaped_rewards,
        random_reset=random_reset,
        urgency_cutoff=urgency_cutoff,
        config_hash=config_hash,
        episode_id=episode_id,
    )
