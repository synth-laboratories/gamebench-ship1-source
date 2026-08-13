"""Shared navigation and cooperative task logic for Overcooked v2 code policies."""

from __future__ import annotations

import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any

WAIT = {"kind": "wait"}
# Joint search is exponential in depth. Keep defaults cheap enough that a full
# policy_dev sweep (9 scenarios × 120 steps) finishes in seconds, not hours.
_DEFAULT_SEARCH_DEPTH = 2
_DEFAULT_SEARCH_MAX_JOINT = 24
_DEFAULT_SEARCH_MAX_NODES = 3_000
_DEFAULT_SEARCH_MAX_SECONDS = 0.25
AGENT_SPAWN_CHARS = frozenset({"0", "1", "2", "3"})
DIRECTIONS = {
    "north": (-1, 0),
    "south": (1, 0),
    "east": (0, 1),
    "west": (0, -1),
}
DELTA_TO_DIRECTION = {(-1, 0): "north", (1, 0): "south", (0, 1): "east", (0, -1): "west"}


@dataclass
class KitchenMap:
    walls: set[tuple[int, int]] = field(default_factory=set)
    blocked_tiles: set[tuple[int, int]] = field(default_factory=set)
    onions: set[tuple[int, int]] = field(default_factory=set)
    tomatoes: set[tuple[int, int]] = field(default_factory=set)
    dishes: set[tuple[int, int]] = field(default_factory=set)
    pots: set[tuple[int, int]] = field(default_factory=set)
    serves: set[tuple[int, int]] = field(default_factory=set)
    counters: set[tuple[int, int]] = field(default_factory=set)
    counter_items: dict[tuple[int, int], str] = field(default_factory=dict)


def parse_kitchen_map(readout: dict[str, Any]) -> KitchenMap:
    ascii_rows = str(readout.get("ascii", "")).splitlines()
    public = readout.get("public") or {}
    map_model = KitchenMap()
    for row_index, row in enumerate(ascii_rows):
        for col_index, char in enumerate(row):
            pos = (row_index, col_index)
            if char in {"#", "W"}:
                map_model.walls.add(pos)
                map_model.blocked_tiles.add(pos)
            elif char in {"O", "T", "D", "P", "S", "C"}:
                map_model.blocked_tiles.add(pos)
                if char == "O":
                    map_model.onions.add(pos)
                elif char == "T":
                    map_model.tomatoes.add(pos)
                elif char == "D":
                    map_model.dishes.add(pos)
                elif char == "P":
                    map_model.pots.add(pos)
                elif char == "S":
                    map_model.serves.add(pos)
                elif char == "C":
                    map_model.counters.add(pos)
            elif char in AGENT_SPAWN_CHARS:
                continue
            elif char.isdigit():
                map_model.onions.add(pos)
                map_model.blocked_tiles.add(pos)
    for key, item in (public.get("counter_items") or {}).items():
        row_str, col_str = str(key).split(",", 1)
        map_model.counter_items[(int(row_str), int(col_str))] = str(item)
    return map_model


def kitchen_map_from_engine(engine: Any) -> KitchenMap:
    map_model = KitchenMap()
    map_model.walls = set(engine.layout_walls)
    map_model.pots = set(engine.pots)
    map_model.serves = set(engine.serve_tiles)
    map_model.dishes = set(engine.dish_dispensers)
    map_model.counters = set(engine.counters)
    map_model.counter_items = dict(engine.counter_items)
    for position, ingredient_index in engine.ingredient_pile_map.items():
        if int(ingredient_index) == 0:
            map_model.onions.add(position)
        elif int(ingredient_index) == 1:
            map_model.tomatoes.add(position)
        else:
            map_model.onions.add(position)
    fixture_cells = (
        set(engine.ingredient_pile_map.keys())
        | map_model.dishes
        | map_model.pots
        | map_model.serves
        | map_model.counters
        | set(engine.recipe_indicators)
        | set(engine.button_recipe_indicators)
    )
    map_model.blocked_tiles = set(map_model.walls) | fixture_cells
    return map_model


def resolve_kitchen_map(readout: dict[str, Any], engine: Any | None = None) -> KitchenMap:
    if engine is not None:
        return kitchen_map_from_engine(engine)
    return parse_kitchen_map(readout)


def recipe_required_total(readout: dict[str, Any], agent_id: str) -> int:
    public = readout.get("public") or {}
    obs = (readout.get("observations") or {}).get(agent_id) or {}
    required_onions = obs.get("required_onions", public.get("required_onions"))
    if required_onions is not None and int(required_onions) > 0:
        return int(required_onions)
    ingredients = obs.get("recipe_ingredients") or public.get("recipe_ingredients")
    if isinstance(ingredients, list) and ingredients:
        return len(ingredients)
    return 1


def pot_ingredient_total(public: dict[str, Any]) -> int:
    pot_ingredients = public.get("pot_ingredients") or {}
    if pot_ingredients:
        return sum(int(value) for value in pot_ingredients.values())
    return int(public.get("pot_onions", 0) or 0)


def agent_positions(readout: dict[str, Any]) -> dict[str, tuple[int, int]]:
    public = readout.get("public") or {}
    positions: dict[str, tuple[int, int]] = {}
    for agent_id, agent in (public.get("agents") or {}).items():
        positions[agent_id] = tuple(agent.get("position", [0, 0]))
    return positions


def bfs_path(
    start: tuple[int, int],
    goals: set[tuple[int, int]],
    walls: set[tuple[int, int]],
    blocked: set[tuple[int, int]],
    fixtures: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    if start in goals:
        return [start]
    queue: deque[tuple[tuple[int, int], list[tuple[int, int]]]] = deque([(start, [start])])
    seen = {start}
    while queue:
        pos, path = queue.popleft()
        if pos in goals:
            return path
        for dr, dc in DIRECTIONS.values():
            npos = (pos[0] + dr, pos[1] + dc)
            if npos in seen or npos in walls or npos in blocked or npos in fixtures:
                continue
            seen.add(npos)
            queue.append((npos, path + [npos]))
    return [start]


def adjacent_walkable_goals(
    fixture_goals: set[tuple[int, int]],
    walls: set[tuple[int, int]],
    blocked: set[tuple[int, int]],
    fixtures: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    goals: set[tuple[int, int]] = set()
    for fixture in fixture_goals:
        for dr, dc in DIRECTIONS.values():
            cell = (fixture[0] + dr, fixture[1] + dc)
            if cell in walls or cell in fixtures:
                continue
            if cell not in blocked:
                goals.add(cell)
    return goals


def face_action(direction: str, valid: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidate = {"kind": "move", "direction": direction}
    return candidate if candidate in valid else None


def interact_toward(
    position: tuple[int, int],
    facing: str,
    target: tuple[int, int],
    valid: list[dict[str, Any]],
) -> dict[str, Any]:
    for direction, (dr, dc) in DIRECTIONS.items():
        cell = (position[0] + dr, position[1] + dc)
        if cell != target:
            continue
        if direction == facing and {"kind": "interact"} in valid:
            return {"kind": "interact"}
        face = face_action(direction, valid)
        if face is not None:
            return face
        if {"kind": "interact"} in valid:
            return {"kind": "interact"}
    return WAIT


def move_toward_fixture(
    position: tuple[int, int],
    fixture_goals: set[tuple[int, int]],
    valid: list[dict[str, Any]],
    map_model: KitchenMap,
    blocked: set[tuple[int, int]],
) -> dict[str, Any]:
    goals = adjacent_walkable_goals(fixture_goals, map_model.walls, blocked, map_model.blocked_tiles)
    if not goals:
        return WAIT
    path = bfs_path(position, goals, map_model.walls, blocked, map_model.blocked_tiles)
    if len(path) < 2:
        return WAIT
    dr = path[1][0] - path[0][0]
    dc = path[1][1] - path[0][1]
    direction = DELTA_TO_DIRECTION[(dr, dc)]
    candidate = {"kind": "move", "direction": direction}
    return candidate if candidate in valid else WAIT


def nearest_fixture(
    position: tuple[int, int],
    fixtures: set[tuple[int, int]],
    map_model: KitchenMap,
    blocked: set[tuple[int, int]],
) -> tuple[int, int] | None:
    if not fixtures:
        return None
    best: tuple[int, int] | None = None
    best_dist = 10_000
    for fixture in fixtures:
        goals = adjacent_walkable_goals({fixture}, map_model.walls, blocked, map_model.blocked_tiles)
        if not goals:
            continue
        path = bfs_path(position, goals, map_model.walls, blocked, map_model.blocked_tiles)
        dist = len(path) - 1
        if dist < best_dist:
            best_dist = dist
            best = fixture
    return best


def pot_access_cells(map_model: KitchenMap) -> set[tuple[int, int]]:
    return adjacent_walkable_goals(map_model.pots, map_model.walls, set(), map_model.blocked_tiles)


def helper_blocks_path(
    actor_position: tuple[int, int],
    goals: set[tuple[int, int]],
    helper_position: tuple[int, int],
    map_model: KitchenMap,
    blocked: set[tuple[int, int]],
) -> bool:
    if helper_position in goals:
        return True
    with_helper = bfs_path(actor_position, goals, map_model.walls, blocked | {helper_position}, map_model.blocked_tiles)
    without_helper = bfs_path(actor_position, goals, map_model.walls, blocked, map_model.blocked_tiles)
    return len(without_helper) < len(with_helper)


def clear_pot_blocker_action(
    position: tuple[int, int],
    valid: list[dict[str, Any]],
    map_model: KitchenMap,
    pot_cells: set[tuple[int, int]],
) -> dict[str, Any]:
    if position not in pot_cells:
        return WAIT
    pot_center = next(iter(map_model.pots))
    best_action = WAIT
    best_distance = -1
    for direction, (dr, dc) in DIRECTIONS.items():
        candidate = {"kind": "move", "direction": direction}
        if candidate not in valid:
            continue
        npos = (position[0] + dr, position[1] + dc)
        if npos in map_model.blocked_tiles or npos in map_model.walls:
            continue
        distance = abs(npos[0] - pot_center[0]) + abs(npos[1] - pot_center[1])
        if distance > best_distance:
            best_distance = distance
            best_action = candidate
    return best_action


def clear_path_blocker_action(
    position: tuple[int, int],
    valid: list[dict[str, Any]],
    map_model: KitchenMap,
    anchor: tuple[int, int],
) -> dict[str, Any]:
    best_action = WAIT
    best_distance = -1
    for direction, (dr, dc) in DIRECTIONS.items():
        candidate = {"kind": "move", "direction": direction}
        if candidate not in valid:
            continue
        npos = (position[0] + dr, position[1] + dc)
        if npos in map_model.blocked_tiles or npos in map_model.walls:
            continue
        distance = abs(npos[0] - anchor[0]) + abs(npos[1] - anchor[1])
        if distance > best_distance:
            best_distance = distance
            best_action = candidate
    return best_action


def ingredients_still_needed(readout: dict[str, Any], agent_id: str, public: dict[str, Any]) -> list[int]:
    obs = (readout.get("observations") or {}).get(agent_id) or {}
    recipe = obs.get("recipe_ingredients") or public.get("recipe_ingredients") or [0]
    needed_counts = Counter(int(index) for index in recipe)
    pot_ingredients = public.get("pot_ingredients") or {}
    for key, value in pot_ingredients.items():
        needed_counts[int(key)] -= int(value)
    missing: list[int] = []
    for index, count in sorted(needed_counts.items()):
        for _ in range(max(count, 0)):
            missing.append(index)
    return missing


def ingredient_sources_for_index(map_model: KitchenMap, ingredient_index: int) -> set[tuple[int, int]]:
    sources: set[tuple[int, int]] = set()
    if ingredient_index == 0:
        sources |= map_model.onions
    elif ingredient_index == 1:
        sources |= map_model.tomatoes
    for position, item in map_model.counter_items.items():
        if item == f"ing_{ingredient_index}":
            sources.add(position)
    return sources


def counter_ingredient_sources(map_model: KitchenMap, ingredient_prefix: str = "ing_") -> set[tuple[int, int]]:
    sources: set[tuple[int, int]] = set()
    for pos, item in map_model.counter_items.items():
        if item == "onion" or item == "ing_0" or item.startswith(ingredient_prefix):
            sources.add(pos)
    return sources


def choose_worker_action(
    agent_id: str,
    readout: dict[str, Any],
    valid_actions: list[dict[str, Any]],
    map_model: KitchenMap,
    blocked: set[tuple[int, int]],
) -> dict[str, Any]:
    if not valid_actions:
        return WAIT
    obs = (readout.get("observations") or {}).get(agent_id) or {}
    public = readout.get("public") or {}
    position = tuple(obs.get("position", [0, 0]))
    facing = str(obs.get("facing", "south"))
    held = obs.get("held")

    soup_ready = bool(public.get("soup_ready"))
    cooking_ticks = int(public.get("cooking_ticks", 0) or 0)
    required_total = recipe_required_total(readout, agent_id)
    pot_total = pot_ingredient_total(public)

    if held in {"soup", "plated_soup"} and map_model.serves:
        target = nearest_fixture(position, map_model.serves, map_model, blocked)
        if target is not None:
            action = interact_toward(position, facing, target, valid_actions)
            if action != WAIT:
                return action
            return move_toward_fixture(position, map_model.serves, valid_actions, map_model, blocked)

    if soup_ready and held == "dish" and map_model.pots:
        target = nearest_fixture(position, map_model.pots, map_model, blocked)
        if target is not None:
            action = interact_toward(position, facing, target, valid_actions)
            if action != WAIT:
                return action
            return move_toward_fixture(position, map_model.pots, valid_actions, map_model, blocked)

    if soup_ready and held is None and map_model.pots:
        target = nearest_fixture(position, map_model.pots, map_model, blocked)
        if target is not None:
            action = interact_toward(position, facing, target, valid_actions)
            if action != WAIT:
                return action
            return move_toward_fixture(position, map_model.pots, valid_actions, map_model, blocked)

    if soup_ready and held is None and map_model.dishes:
        target = nearest_fixture(position, map_model.dishes, map_model, blocked)
        if target is not None:
            action = interact_toward(position, facing, target, valid_actions)
            if action != WAIT:
                return action
            return move_toward_fixture(position, map_model.dishes, valid_actions, map_model, blocked)

    if cooking_ticks > 0:
        return WAIT

    if held and (held.startswith("ing_") or held in {"onion", "tomato"}) and map_model.pots:
        missing = ingredients_still_needed(readout, agent_id, public)
        held_index = 0 if held in {"onion", "ing_0"} else 1 if held == "tomato" else int(held.split("_", 1)[1])
        if held_index in missing or pot_total < required_total:
            target = nearest_fixture(position, map_model.pots, map_model, blocked)
            if target is not None:
                action = interact_toward(position, facing, target, valid_actions)
                if action != WAIT:
                    return action
                return move_toward_fixture(position, map_model.pots, valid_actions, map_model, blocked)

    if held == "dish":
        return WAIT

    if held is None and pot_total < required_total:
        missing = ingredients_still_needed(readout, agent_id, public)
        if missing:
            sources = ingredient_sources_for_index(map_model, missing[0])
            if sources:
                target = nearest_fixture(position, sources, map_model, blocked)
                if target is not None:
                    action = interact_toward(position, facing, target, valid_actions)
                    if action != WAIT:
                        return action
                    if target in map_model.onions:
                        fixture_set = map_model.onions
                    elif target in map_model.tomatoes:
                        fixture_set = map_model.tomatoes
                    else:
                        fixture_set = {target}
                    return move_toward_fixture(position, fixture_set, valid_actions, map_model, blocked)
        sources = set(map_model.onions) | counter_ingredient_sources(map_model)
        if sources:
            target = nearest_fixture(position, sources, map_model, blocked)
            if target is not None:
                action = interact_toward(position, facing, target, valid_actions)
                if action != WAIT:
                    return action
                fixture_set = map_model.onions if target in map_model.onions else {target}
                return move_toward_fixture(position, fixture_set, valid_actions, map_model, blocked)

    if WAIT in valid_actions:
        return WAIT
    return valid_actions[0]


def cook_needs_pot_access(readout: dict[str, Any], cook_agent_id: str, map_model: KitchenMap) -> bool:
    public = readout.get("public") or {}
    obs = (readout.get("observations") or {}).get(cook_agent_id) or {}
    held = obs.get("held")
    if bool(public.get("soup_ready")):
        return True
    cooking_ticks = int(public.get("cooking_ticks", 0) or 0)
    if cooking_ticks > 0:
        return False
    required_total = recipe_required_total(readout, cook_agent_id)
    pot_total = pot_ingredient_total(public)
    if pot_total < required_total and held and (
        held.startswith("ing_") or held in {"onion", "tomato"}
    ):
        return True
    if pot_total < required_total and held is None:
        return True
    return False


def choose_joint_actions_heuristic(
    readout: dict[str, Any],
    joint_valid: dict[str, list[dict[str, Any]]],
    ply: int,
    engine: Any | None = None,
) -> dict[str, Any]:
    agent_ids = tuple(sorted(joint_valid.keys()))
    map_model = resolve_kitchen_map(readout, engine)
    positions = agent_positions(readout)
    pot_cells = pot_access_cells(map_model)
    cook_agent_id = agent_ids[0] if agent_ids else "agent_0"
    cook_obs = (readout.get("observations") or {}).get(cook_agent_id) or {}
    cook_held = cook_obs.get("held")
    serve_goals = adjacent_walkable_goals(map_model.serves, map_model.walls, set(), map_model.blocked_tiles)
    cook_pos = positions.get(cook_agent_id, (0, 0))
    actions: dict[str, dict[str, Any]] = {agent_id: WAIT for agent_id in agent_ids}

    for agent_id in agent_ids[1:]:
        blocked_for_helper = {pos for other_id, pos in positions.items() if other_id != agent_id}
        helper_valid = list(joint_valid.get(agent_id, [WAIT]))
        helper_pos = positions.get(agent_id, (0, 0))
        if (
            cook_held in {"soup", "plated_soup"}
            and map_model.serves
            and helper_blocks_path(cook_pos, serve_goals, helper_pos, map_model, {cook_pos})
        ):
            clear_action = clear_path_blocker_action(
                helper_pos,
                helper_valid,
                map_model,
                next(iter(map_model.serves)),
            )
            if clear_action != WAIT:
                actions[agent_id] = clear_action
                continue
        if (
            helper_pos in pot_cells
            and cook_needs_pot_access(readout, cook_agent_id, map_model)
            and positions.get(cook_agent_id) != helper_pos
        ):
            clear_action = clear_pot_blocker_action(helper_pos, helper_valid, map_model, pot_cells)
            if clear_action != WAIT:
                actions[agent_id] = clear_action
                continue
        actions[agent_id] = choose_worker_action(
            agent_id,
            readout,
            helper_valid,
            map_model,
            blocked_for_helper,
        )

    cook_blocked = {pos for other_id, pos in positions.items() if other_id != cook_agent_id}
    actions[cook_agent_id] = choose_worker_action(
        cook_agent_id,
        readout,
        list(joint_valid.get(cook_agent_id, [WAIT])),
        map_model,
        cook_blocked,
    )

    return {
        "joint_action": actions,
        "policy_reason": f"kitchen_heuristic ply={ply} deliveries={readout.get('public', {}).get('deliveries', 0)}",
    }


def score_sim_engine(engine: Any) -> float:
    required_total = max(int(engine.required_onions or 1), 1)
    pot_total = sum(int(value) for value in engine.pot_ingredients.values())
    score = float(engine.deliveries) * 200.0 + float(engine.private.total_reward) * 10.0
    score += pot_total / max(required_total, 1) * 5.0
    if engine.soup_ready:
        score += 15.0
    if engine.cooking_ticks > 0:
        score += 5.0
    if engine.private.terminated:
        score += 500.0
    if engine.private.truncated:
        score -= 25.0
    score -= float(engine.private.step_index) * 0.05
    for agent in engine.agents.values():
        if agent.held in {"soup", "plated_soup"}:
            score += 8.0
        elif agent.held and (agent.held.startswith("ing_") or agent.held in {"onion", "tomato"}):
            score += 2.0
    return score


def _action_priority(action: dict[str, Any]) -> int:
    kind = action.get("kind")
    if kind == "interact":
        return 3
    if kind == "move":
        return 2
    return 1


def enumerate_joint_actions(
    joint_valid: dict[str, list[dict[str, Any]]],
    *,
    max_joint: int = 48,
) -> list[dict[str, dict[str, Any]]]:
    agent_ids = sorted(joint_valid.keys())
    if not agent_ids:
        return [{}]

    per_agent: list[list[dict[str, Any]]] = []
    for agent_id in agent_ids:
        valid = list(joint_valid.get(agent_id, [WAIT]))
        ranked = sorted(valid, key=_action_priority, reverse=True)
        trimmed: list[dict[str, Any]] = []
        for action in ranked:
            if action not in trimmed:
                trimmed.append(action)
        if WAIT not in trimmed:
            trimmed.append(WAIT)
        per_agent.append(trimmed[:6])

    joints: list[dict[str, dict[str, Any]]] = []
    stack: list[dict[str, Any]] = [{}]
    for agent_index, agent_id in enumerate(agent_ids):
        next_stack: list[dict[str, Any]] = []
        for partial in stack:
            for action in per_agent[agent_index]:
                joint = dict(partial)
                joint[agent_id] = action
                next_stack.append(joint)
        stack = next_stack

    stack.sort(
        key=lambda joint: sum(_action_priority(joint.get(agent_id, WAIT)) for agent_id in agent_ids),
        reverse=True,
    )
    if len(stack) > max_joint:
        stack = stack[:max_joint]
    return stack


@dataclass
class _SearchBudget:
    max_nodes: int
    deadline: float
    nodes: int = 0
    exhausted: bool = False

    def spend(self) -> bool:
        self.nodes += 1
        if self.nodes > self.max_nodes or time.perf_counter() >= self.deadline:
            self.exhausted = True
            return False
        return True


def search_best_joint_action(
    engine: Any,
    *,
    depth: int = _DEFAULT_SEARCH_DEPTH,
    max_joint: int = _DEFAULT_SEARCH_MAX_JOINT,
    max_nodes: int = _DEFAULT_SEARCH_MAX_NODES,
    max_seconds: float = _DEFAULT_SEARCH_MAX_SECONDS,
) -> dict[str, dict[str, Any]]:
    readout = engine.symbolic_readout()
    joint_valid = readout.get("joint_valid_actions") or engine.joint_valid_actions()
    agent_ids = sorted(joint_valid.keys())
    if not agent_ids:
        return {}

    depth = max(0, int(depth))
    max_joint = max(1, int(max_joint))
    budget = _SearchBudget(
        max_nodes=max(1, int(max_nodes)),
        deadline=time.perf_counter() + max(0.01, float(max_seconds)),
    )
    candidates = enumerate_joint_actions(joint_valid, max_joint=max_joint)
    best_score = float("-inf")
    best_joint: dict[str, dict[str, Any]] = {agent_id: WAIT for agent_id in agent_ids}
    inner_max_joint = min(24, max_joint)

    for joint in candidates:
        if budget.exhausted:
            break
        if all(action == WAIT for action in joint.values()):
            continue
        if not budget.spend():
            break
        sim = engine.clone_for_sim()
        sim.step(joint)
        score = _search_score(sim, depth - 1, budget=budget, max_joint=inner_max_joint)
        if score > best_score:
            best_score = score
            best_joint = dict(joint)

    if all(action == WAIT for action in best_joint.values()):
        heuristic = choose_joint_actions_heuristic(readout, joint_valid, ply=0, engine=engine)
        return heuristic["joint_action"]
    return best_joint


def _search_score(
    engine: Any,
    depth: int,
    *,
    budget: _SearchBudget,
    max_joint: int = 24,
) -> float:
    if depth <= 0 or engine.private.terminated or engine.private.truncated:
        return score_sim_engine(engine)
    if budget.exhausted:
        return score_sim_engine(engine)
    readout = engine.symbolic_readout()
    joint_valid = readout.get("joint_valid_actions") or engine.joint_valid_actions()
    best = score_sim_engine(engine)
    for joint in enumerate_joint_actions(joint_valid, max_joint=max_joint):
        if budget.exhausted:
            break
        if all(action == WAIT for action in joint.values()):
            continue
        if not budget.spend():
            break
        sim = engine.clone_for_sim()
        sim.step(joint)
        best = max(best, _search_score(sim, depth - 1, budget=budget, max_joint=max_joint))
    return best
