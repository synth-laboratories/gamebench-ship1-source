"""OvercookedAI-compatible featurized observation vectors (pure Python)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ingredients import held_to_index, normalize_held
from reachability import adjacent_cells, bfs_closest_delta, flood_fill_region, wall_features
from state import DIRECTIONS

if TYPE_CHECKING:
    from engine import OvercookedV2Engine


NUM_POTS = 2
DIRECTION_INDEX = {"north": 0, "south": 1, "east": 2, "west": 3}


def featurized_vector_length(num_agents: int, num_pots: int = NUM_POTS) -> int:
    player_len = num_pots * 10 + 28
    other_len = num_pots * 10 + 24
    return player_len + (num_agents - 1) * other_len + (num_agents - 1) * 2 + 2


def build_featurized_vector(engine: "OvercookedV2Engine", agent_id: str) -> list[float]:
    assert engine.resolved is not None
    num_agents = len(engine.agent_ids)
    agent = engine.agents[agent_id]
    all_features = {
        other_id: _player_features(
            engine,
            other_id,
            num_pots=NUM_POTS,
            include_walls=other_id == agent_id,
        )
        for other_id in engine.agent_ids
    }
    agent_features = all_features[agent_id]
    other_ids = [other_id for other_id in engine.agent_ids if other_id != agent_id]
    other_player_features: list[float] = []
    for other_id in other_ids:
        other_player_features.extend(all_features[other_id])
    dist_features: list[float] = []
    for other_id in other_ids:
        other = engine.agents[other_id]
        dist_features.extend(
            [
                float(other.position[0] - agent.position[0]),
                float(other.position[1] - agent.position[1]),
            ]
        )
    position_features = [float(agent.position[0]), float(agent.position[1])]
    return [
        *[float(value) for value in agent_features],
        *[float(value) for value in other_player_features],
        *dist_features,
        *position_features,
    ]


def _player_features(
    engine: "OvercookedV2Engine",
    agent_id: str,
    num_pots: int,
    include_walls: bool = True,
) -> list[float]:
    assert engine.resolved is not None
    layout = engine.resolved.layout
    agent = engine.agents[agent_id]
    position = agent.position
    height = layout.height
    width = layout.width

    def is_wall(pos: tuple[int, int]) -> bool:
        return pos in engine.layout_walls

    def is_walkable(pos: tuple[int, int]) -> bool:
        if pos in engine.layout_walls:
            return False
        if pos in engine.counter_items:
            return False
        return True

    reachable = flood_fill_region(position, height, width, lambda pos: not is_walkable(pos))
    blocked_agents = {other.position for other_id, other in engine.agents.items() if other_id != agent_id}

    facing = agent.facing
    direction_index = DIRECTION_INDEX.get(facing, 0)
    dir_features = [1.0 if index == direction_index else 0.0 for index in range(4)]

    held = normalize_held(agent.held)
    held_index = held_to_index(held)
    inv_items = ["ing_0", "soup", "dish", "ing_1"]
    inv_features = [
        1.0 if held == item or (item == "ing_0" and held == "onion") else 0.0 for item in inv_items
    ]

    onion_targets = set(engine.ingredient_pile_map.keys())
    onion_targets |= {pos for pos, item in engine.counter_items.items() if held_to_index(normalize_held(item)) == 0}
    tomato_targets = {pos for pos, index in engine.ingredient_pile_map.items() if index == 1}
    tomato_targets |= {pos for pos, item in engine.counter_items.items() if held_to_index(normalize_held(item)) == 1}
    dish_targets = set(engine.dish_dispensers)
    dish_targets |= {pos for pos, item in engine.counter_items.items() if normalize_held(item) == "dish"}
    soup_targets = {pos for pos, item in engine.counter_items.items() if normalize_held(item) in {"soup", "plated_soup"}}
    serve_targets = set(engine.serve_tiles)
    counter_targets = set(engine.counters)

    if held_index == 0:
        onion_delta = (0.0, 0.0)
    else:
        onion_delta, _ = _closest_delta(position, onion_targets, reachable, blocked_agents)
    if held_index == 1:
        tomato_delta = (0.0, 0.0)
    else:
        tomato_delta, _ = _closest_delta(position, tomato_targets, reachable, blocked_agents)
    if held == "dish":
        dish_delta = (0.0, 0.0)
    else:
        dish_delta, _ = _closest_delta(position, dish_targets, reachable, blocked_agents)
    if held in {"soup", "plated_soup"}:
        soup_delta = (0.0, 0.0)
    else:
        soup_delta, _ = _closest_delta(position, soup_targets, reachable, blocked_agents)
    serving_delta, _ = _closest_delta(position, serve_targets, reachable, blocked_agents)
    empty_counter_delta, _ = _closest_delta(position, counter_targets, reachable, blocked_agents)

    soup_onions = 3.0 if held in {"soup", "plated_soup"} or engine.soup_ready else 0.0
    soup_tomatoes = 0.0

    pot_feature_blocks: list[float] = []
    pot_positions = sorted(engine.pots)
    remaining_pots = set(pot_positions)
    for _ in range(num_pots):
        if not remaining_pots:
            pot_feature_blocks.extend([0.0] * 10)
            continue
        closest_pos = None
        closest_dist = None
        closest_delta = (0, 0)
        for pot_pos in remaining_pots:
            delta, ok = _closest_delta(position, {pot_pos}, reachable, blocked_agents)
            if not ok:
                continue
            dist = abs(delta[0]) + abs(delta[1])
            if closest_dist is None or dist < closest_dist:
                closest_dist = dist
                closest_pos = pot_pos
                closest_delta = delta
        if closest_pos is None:
            pot_feature_blocks.extend([0.0] * 10)
            continue
        remaining_pots.remove(closest_pos)
        pot_exists = 1.0
        pot_empty = 1.0 if not engine.pot_ingredients else 0.0
        pot_count = sum(engine.pot_ingredients.values())
        pot_full = 1.0 if pot_count >= 3 else 0.0
        pot_cooking = 1.0 if engine.cooking_ticks > 0 else 0.0
        pot_ready = 1.0 if engine.soup_ready else 0.0
        num_onions = float(engine.pot_ingredients.get(0, 0))
        num_tomatoes = float(engine.pot_ingredients.get(1, 0))
        cook_time = float(engine.cooking_ticks if engine.cooking_ticks > 0 else -1)
        pot_feature_blocks.extend(
            [
                pot_exists,
                pot_empty,
                pot_full,
                pot_cooking,
                pot_ready,
                num_onions,
                num_tomatoes,
                cook_time,
                float(closest_delta[0]),
                float(closest_delta[1]),
            ]
        )

    walls = wall_features(position, height, width, is_wall)

    features: list[float] = []
    features.extend(dir_features)
    features.extend(inv_features)
    features.extend([float(onion_delta[0]), float(onion_delta[1])])
    features.extend([float(tomato_delta[0]), float(tomato_delta[1])])
    features.extend([float(dish_delta[0]), float(dish_delta[1])])
    features.extend([float(soup_delta[0]), float(soup_delta[1])])
    features.extend([soup_onions, soup_tomatoes])
    features.extend([float(serving_delta[0]), float(serving_delta[1])])
    features.extend([float(empty_counter_delta[0]), float(empty_counter_delta[1])])
    features.extend(pot_feature_blocks)
    if include_walls:
        features.extend(walls)

    player_len = num_pots * 10 + (28 if include_walls else 24)
    while len(features) < player_len:
        features.append(0.0)
    return features[:player_len]


def _closest_delta(
    position: tuple[int, int],
    targets: set[tuple[int, int]],
    reachable: set[tuple[int, int]],
    blocked: set[tuple[int, int]],
) -> tuple[tuple[int, int], bool]:
    adj_targets: set[tuple[int, int]] = set()
    for target in targets:
        row, col = target
        for dr, dc in DIRECTIONS.values():
            adj = (row + dr, col + dc)
            if adj in reachable and adj not in blocked:
                adj_targets.add(adj)
    return bfs_closest_delta(position, adj_targets, reachable, blocked)
