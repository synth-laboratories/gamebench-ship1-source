"""Symbolic Overcooked v2 multiplayer gold engine — full JaxMARL-scope MARL."""

from __future__ import annotations

import json
import random
from typing import Any

from core.nev import NevLog
from constants import POT_COOK_TIME, URGENCY_CUTOFF
from ingredients import (
    add_to_pot,
    can_add_to_pot,
    held_to_index,
    index_to_held,
    normalize_held,
    pot_matches_recipe,
    pot_onion_count,
    pot_total,
)
from layout import walkable_tiles
from observations import build_observation
from state import DIRECTIONS, FACING_OPTIONS, AgentPublic, PrivateState, PublicState
from task_resolve import RECIPE_TABLE, ResolvedTask, resolve_task


WAIT_ACTION = {"kind": "wait"}
DELIVERY_REWARD = 1.0
AGENT_MARKERS = {"agent_0": "0", "agent_1": "1", "agent_2": "2", "agent_3": "3"}
SHAPED_REWARDS = {
    "placement_in_pot": 0.15,
    "pot_start_cooking": 0.25,
    "dish_pickup": 0.25,
    "plate_pickup": 0.15,
}


class OvercookedV2Engine:
    ENV_FAMILY = "overcooked-v2-multiplayer"

    def __init__(self) -> None:
        self.resolved: ResolvedTask | None = None
        self.agent_ids: tuple[str, ...] = ()
        self.layout_walls: set[tuple[int, int]] = set()
        self.ingredient_pile_map: dict[tuple[int, int], int] = {}
        self.dish_dispensers: set[tuple[int, int]] = set()
        self.pots: set[tuple[int, int]] = set()
        self.serve_tiles: set[tuple[int, int]] = set()
        self.counters: set[tuple[int, int]] = set()
        self.recipe_indicators: set[tuple[int, int]] = set()
        self.button_recipe_indicators: set[tuple[int, int]] = set()
        self.agents: dict[str, AgentPublic] = {}
        self.counter_items: dict[tuple[int, int], str] = {}
        self.pot_ingredients: dict[int, int] = {}
        self.cooking_ticks = 0
        self.soup_ready = False
        self.cooked_recipe_id: str | None = None
        self.deliveries = 0
        self.active_recipe_id = "simple_soup"
        self.recipe_ingredients: tuple[int, ...] = (0,)
        self.required_onions = 1
        self.cook_time = 2
        self.button_activation_ticks: dict[str, int] = {}
        self.ingredient_permutations: dict[str, list[int]] = {}
        self.delivery_success_flag = False
        self.public = PublicState(agents={})
        self.private = PrivateState()
        self.nev = NevLog()
        self._rng = random.Random(0)

    def reset(self, resolved: ResolvedTask) -> dict[str, Any]:
        self.resolved = resolved
        self.agent_ids = resolved.agent_ids
        layout = resolved.layout
        self.layout_walls = set(layout.walls)
        self.ingredient_pile_map = {pos: index for pos, index in layout.ingredient_piles}
        self.dish_dispensers = set(layout.dish_dispensers)
        self.pots = set(layout.pots)
        self.serve_tiles = set(layout.serve_tiles)
        self.counters = set(layout.counters)
        self.recipe_indicators = set(layout.recipe_indicators)
        self.button_recipe_indicators = set(layout.button_recipe_indicators)
        self._rng = random.Random(resolved.seed)
        self.counter_items = {}
        self.pot_ingredients = {}
        self.cooking_ticks = 0
        self.soup_ready = False
        self.cooked_recipe_id = None
        self.deliveries = 0
        self.button_activation_ticks = {}
        self.delivery_success_flag = False
        self.ingredient_permutations = {}
        if resolved.op_ingredient_permutations:
            ingredient_count = max(layout.num_ingredients, 1)
            for agent_id in self.agent_ids:
                perm = list(range(ingredient_count))
                self._rng.shuffle(perm)
                self.ingredient_permutations[agent_id] = perm
        if len(resolved.recipe_pool) > 1:
            self._set_active_recipe(self._rng.choice(list(resolved.recipe_pool)))
        else:
            self._set_active_recipe(resolved.recipe_id)
        self.agents = self._initial_agents(layout)
        self.private = PrivateState(
            config_hash=resolved.config_hash,
            episode_id=resolved.episode_id,
        )
        self.nev = NevLog()
        if resolved.random_reset:
            self._apply_random_reset()
        self._sync_public()
        self.nev.append(
            step_index=0,
            episode_id=resolved.episode_id,
            kind="task_resolved",
            message=f"TaskResolved({resolved.task_id},{resolved.config_hash})",
            payload={"task": resolved.to_dict()},
        )
        self.nev.append(
            step_index=0,
            episode_id=resolved.episode_id,
            kind="state_transition",
            message=f"GameStarted({resolved.scenario_id})",
            payload={
                "scenario_id": resolved.scenario_id,
                "seed": resolved.seed,
                "active_recipe_id": self.active_recipe_id,
                "recipe_ingredients": list(self.recipe_ingredients),
            },
        )
        return self.symbolic_readout()

    def reset_from_task(self, task: dict[str, Any], seed_override: int | None = None) -> dict[str, Any]:
        return self.reset(resolve_task(task, seed_override=seed_override))

    def step(self, joint_action: dict[str, Any]) -> dict[str, Any]:
        if self.resolved is None:
            raise RuntimeError("engine must be reset before step")
        if self.private.terminated or self.private.truncated:
            self._blocked(joint_action, "terminal")
            return self.symbolic_readout()

        self.private.step_index += 1
        self.private.reward_last = 0.0
        self.delivery_success_flag = False
        self._decay_button_ticks()
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="state_transition",
            message="JointStepBegin",
            action=joint_action,
            payload={"step_index": self.private.step_index},
        )

        move_intents: dict[str, dict[str, Any]] = {}
        for agent_id in self.agent_ids:
            action = self._normalize_action(joint_action.get(agent_id, WAIT_ACTION))
            if action.get("kind") == "move":
                move_intents[agent_id] = action

        self._resolve_moves(move_intents, joint_action)
        for agent_id in self.agent_ids:
            action = self._normalize_action(joint_action.get(agent_id, WAIT_ACTION))
            if action.get("kind") == "interact":
                self._interact(agent_id, joint_action)

        if self.cooking_ticks > 0 and not self.soup_ready:
            self.cooking_ticks -= 1
            if self.cooking_ticks == 0:
                self.soup_ready = True
                self.cooked_recipe_id = self.active_recipe_id
                self.nev.append(
                    step_index=self.private.step_index,
                    episode_id=self.resolved.episode_id,
                    kind="state_transition",
                    message=f"CookComplete(recipe={self.cooked_recipe_id})",
                    payload={
                        "pot_ingredients": {str(key): value for key, value in self.pot_ingredients.items()},
                        "recipe_id": self.cooked_recipe_id,
                    },
                )

        self._sync_public()
        self._maybe_truncated()
        return self.symbolic_readout()

    def _set_active_recipe(self, recipe_id: str) -> None:
        base = RECIPE_TABLE.get(recipe_id, RECIPE_TABLE["simple_soup"])
        ingredients = tuple(int(item) for item in base.get("ingredients", [0]))
        self.active_recipe_id = recipe_id
        self.recipe_ingredients = ingredients
        self.required_onions = sum(1 for index in ingredients if index == 0)
        self.cook_time = int(base["cook_time"])

    def _apply_shaped_reward(self, key: str) -> None:
        if not self.resolved or not self.resolved.shaped_rewards:
            return
        reward = SHAPED_REWARDS.get(key, 0.0)
        if reward <= 0:
            return
        self._add_reward(reward, f"ShapedReward({key})")

    def _add_reward(self, reward: float, message: str) -> None:
        assert self.resolved is not None
        self.private.reward_last += reward
        self.private.total_reward += reward
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="resource_delta",
            message=message,
            payload={"reward": reward, "total_reward": self.private.total_reward},
        )

    def _decay_button_ticks(self) -> None:
        updated: dict[str, int] = {}
        for key, ticks in self.button_activation_ticks.items():
            if ticks > 1:
                updated[key] = ticks - 1
        self.button_activation_ticks = updated

    def _initial_agents(self, layout: Any) -> dict[str, AgentPublic]:
        agents: dict[str, AgentPublic] = {}
        if self.resolved and self.resolved.stochastic_spawn:
            walkable = [pos for pos in walkable_tiles(layout) if pos not in layout.counters]
            self._rng.shuffle(walkable)
            for agent_id in self.agent_ids:
                position = walkable.pop()
                facing = self._rng.choice(FACING_OPTIONS)
                agents[agent_id] = AgentPublic(agent_id=agent_id, position=position, facing=facing, held=None)
            return agents
        for agent_id in self.agent_ids:
            agents[agent_id] = AgentPublic(
                agent_id=agent_id,
                position=layout.agent_starts[agent_id],
                facing="south",
                held=None,
            )
        return agents

    def steps_remaining(self) -> int:
        if self.resolved is None:
            return 0
        return max(0, self.resolved.max_steps - self.private.step_index)

    def urgency_active(self) -> bool:
        if self.resolved is None:
            return False
        return self.steps_remaining() < self.resolved.urgency_cutoff

    def _apply_random_reset(self) -> None:
        assert self.resolved is not None
        layout = self.resolved.layout
        walkable = [pos for pos in walkable_tiles(layout) if pos not in layout.counters]
        self._rng.shuffle(walkable)
        for agent_id in self.agent_ids:
            position = walkable.pop()
            facing = self._rng.choice(FACING_OPTIONS)
            self.agents[agent_id] = AgentPublic(
                agent_id=agent_id,
                position=position,
                facing=facing,
                held=None,
            )
        ingredient_count = max(layout.num_ingredients, 1)
        for agent_id in self.agent_ids:
            roll = self._rng.random()
            if roll < 0.5:
                held = None
            elif roll < 0.6:
                held = "dish"
            elif roll < 0.85:
                held = index_to_held(self._rng.randint(0, ingredient_count - 1))
            else:
                held = "soup"
            self.agents[agent_id].held = held

        for pot_pos in sorted(self.pots):
            roll = self._rng.random()
            if roll < 0.4:
                break
            if roll < 0.75:
                partial_count = self._rng.randint(1, 3)
                self.pot_ingredients = {}
                for _ in range(partial_count):
                    ingredient_index = self._rng.randint(0, ingredient_count - 1)
                    self.pot_ingredients = add_to_pot(self.pot_ingredients, ingredient_index)
            elif roll < 0.9:
                self.pot_ingredients = {}
                for _ in range(3):
                    ingredient_index = self._rng.randint(0, ingredient_count - 1)
                    self.pot_ingredients = add_to_pot(self.pot_ingredients, ingredient_index)
                self.cooking_ticks = self._rng.randint(1, POT_COOK_TIME)
            else:
                self.pot_ingredients = {}
                for _ in range(3):
                    ingredient_index = self._rng.randint(0, ingredient_count - 1)
                    self.pot_ingredients = add_to_pot(self.pot_ingredients, ingredient_index)
                self.soup_ready = True
                self.cooked_recipe_id = self.active_recipe_id
            break

        for counter_pos in sorted(self.counters):
            roll = self._rng.random()
            if roll < 0.5:
                continue
            if roll < 0.6:
                self.counter_items[counter_pos] = "dish"
            elif roll < 0.9:
                self.counter_items[counter_pos] = index_to_held(self._rng.randint(0, ingredient_count - 1))
            else:
                self.counter_items[counter_pos] = "soup"

        self.nev.append(
            step_index=0,
            episode_id=self.resolved.episode_id,
            kind="state_transition",
            message="RandomResetApplied",
            payload={
                "agents": {agent_id: agent.to_dict() for agent_id, agent in self.agents.items()},
                "pot_ingredients": {str(k): v for k, v in self.pot_ingredients.items()},
                "counter_items": {
                    f"{row},{col}": item for (row, col), item in self.counter_items.items()
                },
            },
        )

    def _resolve_moves(self, move_intents: dict[str, dict[str, Any]], joint_action: dict[str, Any]) -> None:
        if not move_intents:
            return
        targets: dict[str, tuple[int, int]] = {}
        for agent_id, action in move_intents.items():
            agent = self.agents[agent_id]
            direction = str(action["direction"])
            dr, dc = DIRECTIONS[direction]
            targets[agent_id] = (agent.position[0] + dr, agent.position[1] + dc)

        blocked: set[str] = set()
        target_cells = list(targets.values())
        if len(target_cells) != len(set(target_cells)):
            blocked = set(move_intents)

        intent_ids = list(move_intents)
        for left_index in range(len(intent_ids)):
            for right_index in range(left_index + 1, len(intent_ids)):
                a0, a1 = intent_ids[left_index], intent_ids[right_index]
                if (
                    targets[a0] == self.agents[a1].position
                    and targets[a1] == self.agents[a0].position
                ):
                    blocked.add(a0)
                    blocked.add(a1)

        for agent_id, target in targets.items():
            if agent_id in blocked:
                continue
            if self._agent_at(target) is not None or not self._is_walkable(target):
                blocked.add(agent_id)

        for agent_id, action in move_intents.items():
            if agent_id in blocked:
                direction = str(action["direction"])
                target = targets[agent_id]
                if self._is_fixture(target) and self._agent_at(target) is None:
                    self.agents[agent_id].facing = direction
                    self.nev.append(
                        step_index=self.private.step_index,
                        episode_id=self.resolved.episode_id,
                        kind="action_applied",
                        message=f"FaceApplied({agent_id},{direction})",
                        action=joint_action,
                        transition="face",
                    )
                    continue
                self.nev.append(
                    step_index=self.private.step_index,
                    episode_id=self.resolved.episode_id,
                    kind="rule_violation",
                    message=f"MoveBlocked({agent_id})",
                    action=joint_action,
                    severity="warn",
                )
                continue
            agent = self.agents[agent_id]
            direction = str(action["direction"])
            agent.position = targets[agent_id]
            agent.facing = direction
            self.nev.append(
                step_index=self.private.step_index,
                episode_id=self.resolved.episode_id,
                kind="action_applied",
                message=f"MoveApplied({agent_id},{direction})",
                action=joint_action,
                transition="move",
            )

    def _interact(self, agent_id: str, joint_action: dict[str, Any]) -> None:
        assert self.resolved is not None
        agent = self.agents[agent_id]
        dr, dc = DIRECTIONS[agent.facing]
        target = (agent.position[0] + dr, agent.position[1] + dc)

        if target in self.ingredient_pile_map and agent.held is None:
            ingredient_index = self.ingredient_pile_map[target]
            agent.held = index_to_held(ingredient_index)
            self.nev.append(
                step_index=self.private.step_index,
                episode_id=self.resolved.episode_id,
                kind="action_applied",
                message=f"ItemPicked({agent_id},{agent.held})",
                action=joint_action,
                transition="pickup",
            )
            return

        if target in self.dish_dispensers and agent.held is None:
            agent.held = "dish"
            self._apply_shaped_reward("dish_pickup")
            self.nev.append(
                step_index=self.private.step_index,
                episode_id=self.resolved.episode_id,
                kind="action_applied",
                message=f"ItemPicked({agent_id},dish)",
                action=joint_action,
                transition="pickup",
            )
            return

        if target in self.button_recipe_indicators and agent.held is None:
            self._activate_button(target, agent_id, joint_action)
            return

        if target in self.pots:
            held_index = held_to_index(normalize_held(agent.held))
            if held_index is not None and not self.soup_ready and self.cooking_ticks == 0:
                if can_add_to_pot(self.pot_ingredients, held_index):
                    self.pot_ingredients = add_to_pot(self.pot_ingredients, held_index)
                    agent.held = None
                    self._apply_shaped_reward("placement_in_pot")
                    self.nev.append(
                        step_index=self.private.step_index,
                        episode_id=self.resolved.episode_id,
                        kind="state_transition",
                        message=f"PotIngredientAdded(index={held_index},pot={{{', '.join(f'{k}:{v}' for k, v in sorted(self.pot_ingredients.items()))}}})",
                        action=joint_action,
                    )
                    if (
                        not self.resolved.start_cooking_interaction
                        and pot_matches_recipe(self.pot_ingredients, self.recipe_ingredients)
                    ):
                        self._start_cooking(joint_action)
                return
            if (
                self.resolved.start_cooking_interaction
                and agent.held is None
                and not self.soup_ready
                and self.cooking_ticks == 0
                and pot_matches_recipe(self.pot_ingredients, self.recipe_ingredients)
            ):
                self._start_cooking(joint_action)
                return
            if self.soup_ready and agent.held is None:
                agent.held = "soup"
                self.soup_ready = False
                self.pot_ingredients = {}
                self.nev.append(
                    step_index=self.private.step_index,
                    episode_id=self.resolved.episode_id,
                    kind="action_applied",
                    message=f"ItemPicked({agent_id},soup)",
                    action=joint_action,
                    transition="pickup",
                )
                return
            if self.soup_ready and agent.held == "dish":
                agent.held = "plated_soup"
                self.soup_ready = False
                self.pot_ingredients = {}
                self.cooked_recipe_id = self.active_recipe_id
                self._apply_shaped_reward("plate_pickup")
                self.nev.append(
                    step_index=self.private.step_index,
                    episode_id=self.resolved.episode_id,
                    kind="action_applied",
                    message=f"ItemPlated({agent_id},soup)",
                    action=joint_action,
                    transition="plate",
                )
                return

        if target in self.serve_tiles and agent.held in {"soup", "plated_soup"}:
            self._handle_delivery(agent_id, joint_action)
            return

        if target in self.counters:
            self._interact_counter(agent_id, target, joint_action)
            return

        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="rule_violation",
            message=f"InteractNoEffect({agent_id})",
            action=joint_action,
            severity="warn",
        )

    def _start_cooking(self, joint_action: dict[str, Any]) -> None:
        assert self.resolved is not None
        self.cooking_ticks = self.cook_time
        self._apply_shaped_reward("pot_start_cooking")
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="state_transition",
            message=f"CookStart(recipe={self.active_recipe_id},ticks={self.cooking_ticks})",
            action=joint_action,
        )

    def _activate_button(
        self,
        target: tuple[int, int],
        agent_id: str,
        joint_action: dict[str, Any],
    ) -> None:
        assert self.resolved is not None
        key = f"{target[0]},{target[1]}"
        self.button_activation_ticks[key] = self.resolved.indicator_activation_time
        if self.resolved.indicator_activation_cost > 0:
            penalty = -self.resolved.indicator_activation_cost
            self._add_reward(penalty, f"ButtonActivationCost({penalty})")
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="state_transition",
            message=f"ButtonActivated({agent_id},{key})",
            action=joint_action,
            payload={"ticks": self.resolved.indicator_activation_time},
        )

    def _interact_counter(self, agent_id: str, target: tuple[int, int], joint_action: dict[str, Any]) -> None:
        assert self.resolved is not None
        agent = self.agents[agent_id]
        on_counter = self.counter_items.get(target)
        if agent.held is not None and on_counter is None:
            self.counter_items[target] = agent.held
            agent.held = None
            self.nev.append(
                step_index=self.private.step_index,
                episode_id=self.resolved.episode_id,
                kind="action_applied",
                message=f"ItemPlaced({agent_id},counter,{self.counter_items[target]})",
                action=joint_action,
                transition="place",
            )
            return
        if agent.held is None and on_counter is not None:
            agent.held = on_counter
            del self.counter_items[target]
            self.nev.append(
                step_index=self.private.step_index,
                episode_id=self.resolved.episode_id,
                kind="action_applied",
                message=f"ItemPicked({agent_id},{on_counter},counter)",
                action=joint_action,
                transition="pickup",
            )
            return
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="rule_violation",
            message=f"InteractBlocked({agent_id},counter)",
            action=joint_action,
            severity="warn",
        )

    def _handle_delivery(self, agent_id: str, joint_action: dict[str, Any]) -> None:
        assert self.resolved is not None
        agent = self.agents[agent_id]
        delivered_recipe = self.cooked_recipe_id or self.active_recipe_id
        correct = delivered_recipe == self.active_recipe_id
        if not correct and self.resolved.wrong_delivery_penalty < 0:
            penalty = self.resolved.wrong_delivery_penalty
            agent.held = None
            self._add_reward(penalty, f"WrongDelivery({delivered_recipe}!={self.active_recipe_id})")
            self.nev.append(
                step_index=self.private.step_index,
                episode_id=self.resolved.episode_id,
                kind="rule_violation",
                message=f"WrongDelivery({agent_id},{delivered_recipe}!={self.active_recipe_id})",
                action=joint_action,
                severity="warn",
            )
            return

        self.deliveries += 1
        agent.held = None
        self.cooked_recipe_id = None
        self.delivery_success_flag = True
        self._add_reward(DELIVERY_REWARD, f"RewardDelta({DELIVERY_REWARD:.2f},total={self.private.total_reward:.2f})")
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="achievement",
            message=f"Delivery({agent_id},{self.active_recipe_id})",
            action=joint_action,
            payload={"deliveries": self.deliveries},
        )
        if self.deliveries >= self.resolved.target_deliveries:
            self._terminate_success()
        elif self.resolved.resample_on_delivery:
            self._resample_recipe()

    def _resample_recipe(self) -> None:
        assert self.resolved is not None
        if len(self.resolved.recipe_pool) <= 1:
            return
        choices = [recipe for recipe in self.resolved.recipe_pool if recipe != self.active_recipe_id]
        if not choices:
            choices = list(self.resolved.recipe_pool)
        next_recipe = self._rng.choice(choices)
        self._set_active_recipe(next_recipe)
        self.pot_ingredients = {}
        self.cooking_ticks = 0
        self.soup_ready = False
        self.cooked_recipe_id = None
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="state_transition",
            message=f"RecipeResampled({next_recipe})",
            payload={"active_recipe_id": next_recipe, "recipe_ingredients": list(self.recipe_ingredients)},
        )

    def _terminate_success(self) -> None:
        assert self.resolved is not None
        self.private.terminated = True
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="terminal",
            message="Terminal(success)",
            transition="success",
        )

    def _maybe_truncated(self) -> None:
        assert self.resolved is not None
        if self.private.terminated:
            return
        if self.private.step_index >= self.resolved.max_steps:
            self.private.truncated = True
            self.nev.append(
                step_index=self.private.step_index,
                episode_id=self.resolved.episode_id,
                kind="terminal",
                message="Terminal(truncated)",
                transition="truncated",
            )

    def _blocked(self, joint_action: dict[str, Any], reason: str) -> None:
        assert self.resolved is not None
        self.private.invalid_action_count += 1
        self.nev.append(
            step_index=self.private.step_index,
            episode_id=self.resolved.episode_id,
            kind="rule_violation",
            message=f"Blocked({reason})",
            action=joint_action,
            severity="error",
        )

    def _is_walkable(self, pos: tuple[int, int]) -> bool:
        if pos in self.layout_walls or pos in self.counter_items:
            return False
        return not self._is_fixture(pos)

    def _is_fixture(self, pos: tuple[int, int]) -> bool:
        return (
            pos in self.ingredient_pile_map
            or pos in self.dish_dispensers
            or pos in self.pots
            or pos in self.serve_tiles
            or pos in self.counters
            or pos in self.recipe_indicators
            or pos in self.button_recipe_indicators
        )

    def _agent_at(self, pos: tuple[int, int]) -> str | None:
        for agent_id, agent in self.agents.items():
            if agent.position == pos:
                return agent_id
        return None

    def _normalize_action(self, action: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(action, str):
            if action in DIRECTIONS:
                return {"kind": "move", "direction": action}
            if action in {"interact", "noop", "wait"}:
                return {"kind": "interact"} if action == "interact" else WAIT_ACTION
            return WAIT_ACTION
        parsed = dict(action)
        if parsed.get("kind") == "noop":
            parsed["kind"] = "wait"
        return parsed

    def _sync_public(self) -> None:
        assert self.resolved is not None
        self.public = PublicState(
            agents={
                agent_id: AgentPublic(
                    agent_id=agent.agent_id,
                    position=agent.position,
                    facing=agent.facing,
                    held=normalize_held(agent.held),
                )
                for agent_id, agent in self.agents.items()
            },
            pot_ingredients=dict(self.pot_ingredients),
            pot_onions=pot_onion_count(self.pot_ingredients),
            cooking_ticks=self.cooking_ticks,
            soup_ready=self.soup_ready,
            deliveries=self.deliveries,
            recipe_id=self.active_recipe_id,
            active_recipe_id=self.active_recipe_id,
            recipe_ingredients=list(self.recipe_ingredients),
            cooked_recipe_id=self.cooked_recipe_id,
            counter_items=dict(self.counter_items),
            button_activation_ticks=dict(self.button_activation_ticks),
            delivery_success_flag=self.delivery_success_flag,
            done=self.private.terminated,
        )

    def _chebyshev(self, left: tuple[int, int], right: tuple[int, int]) -> int:
        return max(abs(left[0] - right[0]), abs(left[1] - right[1]))

    def _in_view(self, observer: tuple[int, int], target: tuple[int, int]) -> bool:
        assert self.resolved is not None
        if not self.resolved.partial_obs:
            return True
        radius = self.resolved.view_radius
        if radius <= 0:
            return True
        return self._chebyshev(observer, target) <= radius

    def _recipe_visible_for(self, agent_id: str) -> bool:
        assert self.resolved is not None
        agent = self.agents[agent_id]
        if not self.resolved.hidden_recipe:
            return True
        if self._indicator_visible(agent.position):
            return True
        for pos in self.button_recipe_indicators:
            key = f"{pos[0]},{pos[1]}"
            if self.button_activation_ticks.get(key, 0) > 0 and self._in_view(agent.position, pos):
                return True
        return False

    def _indicator_visible(self, agent_position: tuple[int, int]) -> bool:
        if not self.recipe_indicators:
            return not self.resolved.hidden_recipe if self.resolved else True
        return any(self._in_view(agent_position, indicator) for indicator in self.recipe_indicators)

    def _mask_ascii(self, ascii_rows: list[str], observer: tuple[int, int]) -> str:
        assert self.resolved is not None
        if not self.resolved.partial_obs:
            return "\n".join(ascii_rows)
        masked: list[str] = []
        for row_index, row in enumerate(ascii_rows):
            chars: list[str] = []
            for col_index, char in enumerate(row):
                if self._in_view(observer, (row_index, col_index)):
                    chars.append(char)
                else:
                    chars.append("#")
            masked.append("".join(chars))
        return "\n".join(masked)

    def _render_ascii_rows(self) -> list[str]:
        assert self.resolved is not None
        ascii_rows: list[str] = []
        for row_index in range(self.resolved.layout.height):
            chars: list[str] = []
            for col_index in range(self.resolved.layout.width):
                pos = (row_index, col_index)
                char = "."
                if pos in self.layout_walls:
                    char = "#"
                elif pos in self.ingredient_pile_map:
                    char = str(self.ingredient_pile_map[pos])
                elif pos in self.dish_dispensers:
                    char = "D"
                elif pos in self.pots:
                    char = "P"
                elif pos in self.serve_tiles:
                    char = "S"
                elif pos in self.recipe_indicators:
                    char = "R"
                elif pos in self.button_recipe_indicators:
                    key = f"{pos[0]},{pos[1]}"
                    char = "L" if self.button_activation_ticks.get(key, 0) > 0 else "l"
                elif pos in self.counters:
                    char = "C"
                elif pos in self.counter_items:
                    item = self.counter_items[pos]
                    held_index = held_to_index(normalize_held(item))
                    char = str(held_index) if held_index is not None else item[0]
                agent_here = self._agent_at(pos)
                if agent_here is not None:
                    char = AGENT_MARKERS.get(agent_here, "?")
                chars.append(char)
            ascii_rows.append("".join(chars))
        return ascii_rows

    def symbolic_readout(self) -> dict[str, Any]:
        assert self.resolved is not None
        ascii_rows = self._render_ascii_rows()
        observations = {
            agent_id: build_observation(self, agent_id, ascii_rows)
            for agent_id in self.agent_ids
        }
        agent_count = max(len(self.agent_ids), 1)
        rewards = {agent_id: self.private.reward_last / agent_count for agent_id in self.agent_ids}
        dones = {agent_id: self.private.terminated or self.private.truncated for agent_id in self.agent_ids}
        dones["__all__"] = self.private.terminated or self.private.truncated
        return {
            "schema": "gamebench.overcooked_v2.readout.v2",
            "env_family": self.ENV_FAMILY,
            "task_id": self.resolved.task_id,
            "scenario_id": self.resolved.scenario_id,
            "observation_profile": self.resolved.observation_profile,
            "public": self.public.to_dict(),
            "private": self.private.to_dict(),
            "observations": observations,
            "rewards": rewards,
            "dones": dones,
            "ascii": "\n".join(ascii_rows),
            "grid_hash": self.resolved.config_hash,
            "nev_cursor": self.nev.cursor(),
            "joint_valid_actions": self.joint_valid_actions(),
        }

    def _observation_symbolic(self, agent_id: str, ascii_rows: list[str]) -> dict[str, Any]:
        assert self.resolved is not None
        agent = self.agents[agent_id]
        recipe_visible = self._recipe_visible_for(agent_id)
        visible_agents: dict[str, Any] = {}
        for other_id, other in self.agents.items():
            if self._in_view(agent.position, other.position):
                visible_agents[other_id] = other.to_dict()
        pot_visible = any(self._in_view(agent.position, pot) for pot in self.pots)
        return {
            "agent_id": agent_id,
            "agent_index": int(agent_id.split("_")[1]) if "_" in agent_id else 0,
            "ascii": self._mask_ascii(ascii_rows, agent.position),
            "position": [agent.position[0], agent.position[1]],
            "facing": agent.facing,
            "held": normalize_held(agent.held),
            "pot_ingredients": dict(self.pot_ingredients) if pot_visible else None,
            "pot_onions": pot_onion_count(self.pot_ingredients) if pot_visible else None,
            "cooking_ticks": self.cooking_ticks,
            "soup_ready": self.soup_ready,
            "recipe_id": self.active_recipe_id if recipe_visible else None,
            "recipe_ingredients": list(self.recipe_ingredients) if recipe_visible else None,
            "required_onions": self.required_onions if recipe_visible else None,
            "recipe_indicator_visible": recipe_visible,
            "delivery_success_flag": self.delivery_success_flag if self.resolved.indicate_successful_delivery else None,
            "urgency_active": self.urgency_active(),
            "steps_remaining": self.steps_remaining(),
            "partial_obs": self.resolved.partial_obs,
            "view_radius": self.resolved.view_radius,
            "visible_agents": visible_agents,
            "valid_actions": self.valid_actions(agent_id),
        }

    def valid_actions(self, agent_id: str) -> list[dict[str, Any]]:
        if self.private.terminated or self.private.truncated:
            return []
        actions: list[dict[str, Any]] = [WAIT_ACTION]
        agent = self.agents[agent_id]
        for direction in DIRECTIONS:
            dr, dc = DIRECTIONS[direction]
            target = (agent.position[0] + dr, agent.position[1] + dc)
            if self._agent_at(target) is not None:
                continue
            if self._is_walkable(target) or self._is_fixture(target):
                actions.append({"kind": "move", "direction": direction})
        actions.append({"kind": "interact"})
        return actions

    def joint_valid_actions(self) -> dict[str, list[dict[str, Any]]]:
        return {agent_id: self.valid_actions(agent_id) for agent_id in self.agent_ids}

    def checkpoint_bytes(self) -> bytes:
        assert self.resolved is not None
        payload = {
            "schema_version": "gamebench.checkpoint.v1",
            "env_family": self.ENV_FAMILY,
            "episode_id": self.resolved.episode_id,
            "step_index": self.private.step_index,
            "nev_cursor": self.nev.cursor(),
            "config_hash": self.resolved.config_hash,
            "sim": {
                "resolved": self.resolved.to_dict(),
                "agents": {
                    agent_id: {
                        "position": list(agent.position),
                        "facing": agent.facing,
                        "held": normalize_held(agent.held),
                    }
                    for agent_id, agent in self.agents.items()
                },
                "counter_items": {
                    f"{row},{col}": item for (row, col), item in self.counter_items.items()
                },
                "pot_ingredients": {str(key): value for key, value in self.pot_ingredients.items()},
                "pot_onions": pot_onion_count(self.pot_ingredients),
                "cooking_ticks": self.cooking_ticks,
                "soup_ready": self.soup_ready,
                "cooked_recipe_id": self.cooked_recipe_id,
                "deliveries": self.deliveries,
                "active_recipe_id": self.active_recipe_id,
                "recipe_ingredients": list(self.recipe_ingredients),
                "required_onions": self.required_onions,
                "cook_time": self.cook_time,
                "button_activation_ticks": dict(self.button_activation_ticks),
                "ingredient_permutations": self.ingredient_permutations,
                "delivery_success_flag": self.delivery_success_flag,
                "rng_state": list(self._rng.getstate()),
                "public": self.public.to_dict(),
                "private": self.private.to_dict(),
                "events": self.nev.export(),
            },
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def restore_checkpoint(self, blob: bytes) -> int:
        payload = json.loads(blob.decode("utf-8"))
        sim = payload["sim"]
        resolved_data = sim["resolved"]
        self.resolved = resolve_task(
            {
                "task_id": resolved_data["task_id"],
                "scenario_id": resolved_data["scenario_id"],
                "seed": resolved_data["seed"],
                "layout_id": resolved_data["layout_id"],
                "rules": {
                    "recipe_id": resolved_data["recipe_id"],
                    "overrides": {
                        "recipe_ingredients": resolved_data.get(
                            "recipe_ingredients", [resolved_data.get("required_onions", 1)]
                        ),
                        "required_onions": resolved_data["required_onions"],
                        "cook_time": resolved_data["cook_time"],
                        "max_steps": resolved_data["max_steps"],
                        "partial_obs": resolved_data.get("partial_obs", False),
                        "view_radius": resolved_data.get("view_radius", 0),
                        "hidden_recipe": resolved_data.get("hidden_recipe", False),
                        "stochastic_spawn": resolved_data.get("stochastic_spawn", False),
                        "recipe_pool": resolved_data.get("recipe_pool", [resolved_data["recipe_id"]]),
                        "resample_on_delivery": resolved_data.get("resample_on_delivery", False),
                        "target_deliveries": resolved_data.get("target_deliveries", 1),
                        "wrong_delivery_penalty": resolved_data.get("wrong_delivery_penalty", 0.0),
                        "observation_profile": resolved_data.get("observation_profile", "symbolic_compact"),
                        "indicator_activation_time": resolved_data.get("indicator_activation_time", 10),
                        "indicator_activation_cost": resolved_data.get("indicator_activation_cost", 0.0),
                        "start_cooking_interaction": resolved_data.get("start_cooking_interaction", False),
                        "op_ingredient_permutations": resolved_data.get("op_ingredient_permutations", False),
                        "indicate_successful_delivery": resolved_data.get("indicate_successful_delivery", False),
                        "shaped_rewards": resolved_data.get("shaped_rewards", False),
                        "random_reset": resolved_data.get("random_reset", False),
                        "urgency_cutoff": resolved_data.get("urgency_cutoff", URGENCY_CUTOFF),
                    },
                },
            },
            seed_override=int(resolved_data["seed"]),
        )
        self.agent_ids = self.resolved.agent_ids
        layout = self.resolved.layout
        self.layout_walls = set(layout.walls)
        self.ingredient_pile_map = {pos: index for pos, index in layout.ingredient_piles}
        self.dish_dispensers = set(layout.dish_dispensers)
        self.pots = set(layout.pots)
        self.serve_tiles = set(layout.serve_tiles)
        self.counters = set(layout.counters)
        self.recipe_indicators = set(layout.recipe_indicators)
        self.button_recipe_indicators = set(layout.button_recipe_indicators)
        self.counter_items = {}
        for key, item in sim.get("counter_items", {}).items():
            row_str, col_str = str(key).split(",", 1)
            self.counter_items[(int(row_str), int(col_str))] = str(item)
        self.agents = {}
        for agent_id, data in sim["agents"].items():
            self.agents[agent_id] = AgentPublic(
                agent_id=agent_id,
                position=(int(data["position"][0]), int(data["position"][1])),
                facing=str(data["facing"]),
                held=normalize_held(data.get("held")),
            )
        pot_raw = sim.get("pot_ingredients", {})
        if pot_raw:
            self.pot_ingredients = {int(key): int(value) for key, value in pot_raw.items()}
        else:
            legacy_onions = int(sim.get("pot_onions", 0))
            self.pot_ingredients = {0: legacy_onions} if legacy_onions else {}
        self.cooking_ticks = int(sim["cooking_ticks"])
        self.soup_ready = bool(sim["soup_ready"])
        self.cooked_recipe_id = sim.get("cooked_recipe_id")
        self.deliveries = int(sim["deliveries"])
        self.active_recipe_id = str(sim.get("active_recipe_id", self.resolved.recipe_id))
        self.recipe_ingredients = tuple(
            int(item) for item in sim.get("recipe_ingredients", list(self.resolved.recipe_ingredients))
        )
        self.required_onions = int(sim.get("required_onions", self.resolved.required_onions))
        self.cook_time = int(sim.get("cook_time", self.resolved.cook_time))
        self.button_activation_ticks = dict(sim.get("button_activation_ticks", {}))
        self.ingredient_permutations = dict(sim.get("ingredient_permutations", {}))
        self.delivery_success_flag = bool(sim.get("delivery_success_flag", False))
        if "rng_state" in sim:
            self._rng = random.Random()
            self._rng.setstate(self._tupleize_state(sim["rng_state"]))
        private = sim["private"]
        self.private = PrivateState(
            step_index=int(private["step_index"]),
            total_reward=float(private["total_reward"]),
            reward_last=float(private.get("reward_last", 0.0)),
            terminated=bool(private["terminated"]),
            truncated=bool(private["truncated"]),
            config_hash=str(private["config_hash"]),
            episode_id=str(private["episode_id"]),
            invalid_action_count=int(private.get("invalid_action_count", 0)),
        )
        self.nev = NevLog.from_export(sim["events"])
        self._sync_public()
        return self.nev.cursor()

    def clone_for_sim(self) -> "OvercookedV2Engine":
        clone = OvercookedV2Engine()
        clone.restore_checkpoint(self.checkpoint_bytes())
        return clone

    @staticmethod
    def _tupleize_state(value: Any) -> Any:
        if isinstance(value, list):
            return tuple(OvercookedV2Engine._tupleize_state(item) for item in value)
        return value
