"""Observation profiles for Overcooked v2 symbolic gold."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from featurized_obs import build_featurized_vector, featurized_vector_length
from ingredients import held_to_index, index_to_held, normalize_held

if TYPE_CHECKING:
    from engine import OvercookedV2Engine


PROFILE_SYMBOLIC = "symbolic_compact"
PROFILE_SPATIAL = "spatial_tensor"
PROFILE_FEATURIZED = "featurized"
PROFILE_PIXEL = "pixel_rgb"
PROFILE_ALIASES = {
    "jaxmarl_default": PROFILE_SPATIAL,
    "jaxmarl_featurized": PROFILE_FEATURIZED,
}


def normalize_profile(profile: str) -> str:
    return PROFILE_ALIASES.get(profile, profile)


def build_observation(engine: "OvercookedV2Engine", agent_id: str, ascii_rows: list[str]) -> dict[str, Any]:
    profile = normalize_profile(engine.resolved.observation_profile if engine.resolved else PROFILE_SYMBOLIC)
    base = engine._observation_symbolic(agent_id, ascii_rows)
    base["observation_profile"] = profile
    if profile == PROFILE_SYMBOLIC:
        return base
    if profile == PROFILE_SPATIAL:
        base["tensor"] = build_spatial_tensor(engine, agent_id)
        return base
    if profile == PROFILE_FEATURIZED:
        base["features"] = build_featurized_vector(engine, agent_id)
        base["feature_length"] = len(base["features"])
        base["feature_schema"] = "overcooked_ai.featurized.v1"
        return base
    if profile == PROFILE_PIXEL:
        from render import render_pixel_rgb

        base["pixel_rgb"] = render_pixel_rgb(engine)
        return base
    return base


def permute_ingredient_index(engine: "OvercookedV2Engine", agent_id: str, ingredient_index: int) -> int:
    perm = engine.ingredient_permutations.get(agent_id)
    if perm is None:
        return ingredient_index
    if ingredient_index < len(perm):
        return int(perm[ingredient_index])
    return ingredient_index


def build_spatial_tensor(engine: "OvercookedV2Engine", agent_id: str) -> list[list[list[float]]]:
    assert engine.resolved is not None
    layout = engine.resolved.layout
    height = layout.height
    width = layout.width
    num_ingredients = max(layout.num_ingredients, 1)
    num_layers = 17 + num_ingredients + 4 * (num_ingredients + 2)
    if engine.resolved.indicate_successful_delivery:
        num_layers += 1
    num_layers += 1  # urgency layer
    channels: list[list[list[float]]] = [
        [[0.0 for _ in range(width)] for _ in range(height)] for _ in range(num_layers)
    ]

    def set_layer(row: int, col: int, layer: int, value: float = 1.0) -> None:
        if 0 <= row < height and 0 <= col < width:
            channels[layer][row][col] = value

    layer = 0
    for row in range(height):
        for col in range(width):
            if (row, col) in engine.layout_walls:
                set_layer(row, col, layer, 1.0)
    layer += 1

    for pile_pos, ing_index in engine.ingredient_pile_map.items():
        set_layer(pile_pos[0], pile_pos[1], 1 + ing_index, 1.0)

    for pos in engine.pots:
        set_layer(pos[0], pos[1], 1 + num_ingredients, 1.0)
    for pos in engine.dish_dispensers:
        set_layer(pos[0], pos[1], 1 + num_ingredients + 1, 1.0)
    for pos in engine.serve_tiles:
        set_layer(pos[0], pos[1], 1 + num_ingredients + 2, 1.0)
    for pos in engine.recipe_indicators:
        set_layer(pos[0], pos[1], 1 + num_ingredients + 3, 1.0)
    for pos in engine.button_recipe_indicators:
        ticks = engine.button_activation_ticks.get(f"{pos[0]},{pos[1]}", 0)
        set_layer(pos[0], pos[1], 1 + num_ingredients + 4, 1.0 if ticks > 0 else 0.5)

    agent_layer_base = 1 + num_ingredients + 5
    for other_id, agent in engine.agents.items():
        agent_index = int(other_id.split("_")[1]) if "_" in other_id else 0
        row, col = agent.position
        set_layer(row, col, agent_layer_base + agent_index * 5, 1.0)
        facing_offset = {"north": 1, "south": 2, "east": 3, "west": 4}.get(agent.facing, 0)
        if facing_offset:
            set_layer(row, col, agent_layer_base + agent_index * 5 + facing_offset, 1.0)
        held_index = held_to_index(normalize_held(agent.held))
        if held_index is not None:
            perm_index = permute_ingredient_index(engine, agent_id, held_index)
            set_layer(row, col, agent_layer_base + num_ingredients * 5 + perm_index, 1.0)
        elif agent.held == "dish":
            set_layer(row, col, agent_layer_base + num_ingredients * 5 + num_ingredients, 1.0)
        elif agent.held in {"soup", "plated_soup"}:
            set_layer(row, col, agent_layer_base + num_ingredients * 5 + num_ingredients + 1, 1.0)

    if engine.pots:
        pot_pos = next(iter(engine.pots))
        if engine.cooking_ticks > 0:
            set_layer(pot_pos[0], pot_pos[1], num_layers - 3, min(1.0, engine.cooking_ticks / 20.0))
        if engine.soup_ready:
            set_layer(pot_pos[0], pot_pos[1], num_layers - 2, 1.0)

    if engine.resolved.indicate_successful_delivery and engine.delivery_success_flag:
        agent = engine.agents[agent_id]
        row, col = agent.position
        set_layer(row, col, num_layers - 2, 1.0)

    urgency_value = 1.0 if engine.urgency_active() else 0.0
    for row in range(height):
        for col in range(width):
            set_layer(row, col, num_layers - 1, urgency_value)

    return channels


def expected_featurized_length(num_agents: int) -> int:
    return featurized_vector_length(num_agents)
