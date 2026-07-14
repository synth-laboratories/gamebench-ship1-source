"""Public/private state split for Sokoban."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PublicState:
    room_state: list[list[int]]
    player: tuple[int, int]
    boxes: list[tuple[int, int]]
    boxes_on_target: int
    done: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_state": self.room_state,
            "player": list(self.player),
            "boxes": [list(pos) for pos in self.boxes],
            "boxes_on_target": self.boxes_on_target,
            "done": self.done,
        }

    def diff(self, other: "PublicState") -> dict[str, Any]:
        changes: dict[str, Any] = {}
        if self.room_state != other.room_state:
            changes["room_state"] = {"from": other.room_state, "to": self.room_state}
        if self.player != other.player:
            changes["player"] = {"from": list(other.player), "to": list(self.player)}
        if self.boxes != other.boxes:
            changes["boxes"] = {"from": [list(p) for p in other.boxes], "to": [list(p) for p in self.boxes]}
        if self.boxes_on_target != other.boxes_on_target:
            changes["boxes_on_target"] = {"from": other.boxes_on_target, "to": self.boxes_on_target}
        if self.done != other.done:
            changes["done"] = {"from": other.done, "to": self.done}
        return changes


@dataclass
class PrivateState:
    episode_id: str
    task_id: str
    puzzle_id: str
    seed: int
    config_hash: str
    step_index: int = 0
    reward_last: float = 0.0
    total_reward: float = 0.0
    terminated: bool = False
    truncated: bool = False
    achievements: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "puzzle_id": self.puzzle_id,
            "seed": self.seed,
            "config_hash": self.config_hash,
            "step_index": self.step_index,
            "reward_last": self.reward_last,
            "total_reward": self.total_reward,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "achievements": sorted(self.achievements),
        }


@dataclass
class SimSnapshot:
    public: PublicState
    private: PrivateState
    nev_events: list[dict[str, Any]] = field(default_factory=list)
