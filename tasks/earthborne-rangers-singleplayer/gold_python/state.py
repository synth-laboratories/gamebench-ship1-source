"""Public/private state split for synthetic Earthborne Rangers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PublicState:
    ranger_id: str
    archetype: str | None
    location_id: str
    day: int
    time: int
    fatigue: int
    hand: list[str]
    play_area: list[str]
    discard: list[str]
    objectives_completed: list[str]
    objective_progress: dict[str, int]
    achievements: dict[str, int] = field(default_factory=dict)
    done: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ranger_id": self.ranger_id,
            "archetype": self.archetype,
            "location_id": self.location_id,
            "day": self.day,
            "time": self.time,
            "fatigue": self.fatigue,
            "hand": list(self.hand),
            "play_area": list(self.play_area),
            "discard": list(self.discard),
            "objectives_completed": list(self.objectives_completed),
            "objective_progress": dict(self.objective_progress),
            "achievements": dict(self.achievements),
            "done": self.done,
        }

    def diff(self, other: "PublicState") -> dict[str, Any]:
        changes: dict[str, Any] = {}
        for key, value in self.to_dict().items():
            previous = other.to_dict()[key]
            if value != previous:
                changes[key] = {"from": previous, "to": value}
        return changes


@dataclass
class PrivateState:
    episode_id: str
    task_id: str
    scenario_id: str
    seed: int
    config_hash: str
    step_index: int = 0
    deck: list[str] = field(default_factory=list)
    deck_index: int = 0
    objective_targets: dict[str, int] = field(default_factory=dict)
    objective_locations: dict[str, str] = field(default_factory=dict)
    fatigue_taken: int = 0
    fatigue_recovered: int = 0
    illegal_action_count: int = 0
    cards_played: list[str] = field(default_factory=list)
    strategy_notes: list[str] = field(default_factory=list)
    exposed_reflections: list[dict[str, Any]] = field(default_factory=list)
    achievements: set[str] = field(default_factory=set)
    obstacle_blocked_seen: bool = False
    day_start_illegal_count: int = 0
    reward_last: float = 0.0
    total_reward: float = 0.0
    objective_count: int = 0
    terminated: bool = False
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "config_hash": self.config_hash,
            "step_index": self.step_index,
            "deck": list(self.deck),
            "deck_index": self.deck_index,
            "objective_targets": dict(self.objective_targets),
            "objective_locations": dict(self.objective_locations),
            "fatigue_taken": self.fatigue_taken,
            "fatigue_recovered": self.fatigue_recovered,
            "illegal_action_count": self.illegal_action_count,
            "cards_played": list(self.cards_played),
            "strategy_notes": list(self.strategy_notes),
            "exposed_reflections": list(self.exposed_reflections),
            "achievements": sorted(self.achievements),
            "obstacle_blocked_seen": self.obstacle_blocked_seen,
            "day_start_illegal_count": self.day_start_illegal_count,
            "reward_last": self.reward_last,
            "total_reward": self.total_reward,
            "objective_count": self.objective_count,
            "terminated": self.terminated,
            "truncated": self.truncated,
        }


@dataclass
class SimSnapshot:
    public: PublicState
    private: PrivateState
    nev_events: list[dict[str, Any]] = field(default_factory=list)
