"""Public/private state split for Crafter."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PublicState:
    observation: dict[str, Any]
    player_pos: tuple[int, int]
    inventory: dict[str, int]
    achievements: dict[str, int]
    done: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation": copy.deepcopy(self.observation),
            "player_pos": list(self.player_pos),
            "inventory": dict(self.inventory),
            "achievements": dict(self.achievements),
            "done": self.done,
        }

    def diff(self, other: "PublicState") -> dict[str, Any]:
        changes: dict[str, Any] = {}
        if self.player_pos != other.player_pos:
            changes["player_pos"] = {"from": list(other.player_pos), "to": list(self.player_pos)}
        if self.inventory != other.inventory:
            changes["inventory"] = {"from": other.inventory, "to": self.inventory}
        if self.achievements != other.achievements:
            changes["achievements"] = {"from": other.achievements, "to": self.achievements}
        if self.done != other.done:
            changes["done"] = {"from": other.done, "to": self.done}
        return changes


@dataclass
class PrivateState:
    episode_id: str
    task_id: str
    scenario_id: str
    seed: int
    config_hash: str
    step_index: int = 0
    reward_last: float = 0.0
    total_reward: float = 0.0
    reward_breakdown: dict[str, Any] = field(default_factory=dict)
    terminated: bool = False
    truncated: bool = False
    achievements: set[str] = field(default_factory=set)
    done_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "config_hash": self.config_hash,
            "step_index": self.step_index,
            "reward_last": self.reward_last,
            "total_reward": self.total_reward,
            "reward_breakdown": dict(self.reward_breakdown),
            "terminated": self.terminated,
            "truncated": self.truncated,
            "achievements": sorted(self.achievements),
            "done_reason": self.done_reason,
        }


@dataclass
class SimSnapshot:
    public: PublicState
    private: PrivateState
    nev_events: list[dict[str, Any]] = field(default_factory=list)
    nev_cursor: int = 0
    nev_tail_events: list[dict[str, Any]] = field(default_factory=list)
    nev_events_truncated: bool = False
