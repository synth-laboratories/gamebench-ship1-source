"""Public/private state for Overcooked v2 symbolic MARL gold."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_AGENT_IDS = ("agent_0", "agent_1")
DIRECTIONS = {
    "north": (-1, 0),
    "south": (1, 0),
    "east": (0, 1),
    "west": (0, -1),
}
FACING_OPTIONS = tuple(DIRECTIONS.keys())


@dataclass
class AgentPublic:
    agent_id: str
    position: tuple[int, int]
    facing: str
    held: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "position": [self.position[0], self.position[1]],
            "facing": self.facing,
            "held": self.held,
        }


@dataclass
class PublicState:
    agents: dict[str, AgentPublic]
    pot_ingredients: dict[int, int] = field(default_factory=dict)
    pot_onions: int = 0
    cooking_ticks: int = 0
    soup_ready: bool = False
    deliveries: int = 0
    recipe_id: str = "simple_soup"
    active_recipe_id: str = "simple_soup"
    recipe_ingredients: list[int] = field(default_factory=lambda: [0])
    cooked_recipe_id: str | None = None
    counter_items: dict[tuple[int, int], str] = field(default_factory=dict)
    button_activation_ticks: dict[str, int] = field(default_factory=dict)
    delivery_success_flag: bool = False
    done: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "agents": {agent_id: agent.to_dict() for agent_id, agent in self.agents.items()},
            "pot_ingredients": {str(key): int(value) for key, value in sorted(self.pot_ingredients.items())},
            "pot_onions": self.pot_onions,
            "cooking_ticks": self.cooking_ticks,
            "soup_ready": self.soup_ready,
            "deliveries": self.deliveries,
            "recipe_id": self.recipe_id,
            "active_recipe_id": self.active_recipe_id,
            "recipe_ingredients": list(self.recipe_ingredients),
            "cooked_recipe_id": self.cooked_recipe_id,
            "counter_items": {
                f"{row},{col}": item
                for (row, col), item in sorted(self.counter_items.items())
            },
            "button_activation_ticks": dict(self.button_activation_ticks),
            "delivery_success_flag": self.delivery_success_flag,
            "done": self.done,
        }


@dataclass
class PrivateState:
    step_index: int = 0
    total_reward: float = 0.0
    reward_last: float = 0.0
    terminated: bool = False
    truncated: bool = False
    config_hash: str = ""
    episode_id: str = ""
    invalid_action_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "total_reward": self.total_reward,
            "reward_last": self.reward_last,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "config_hash": self.config_hash,
            "episode_id": self.episode_id,
            "invalid_action_count": self.invalid_action_count,
        }
