"""Public/private state split for multiplayer Tic-Tac-Toe (MARL joint-step API)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gold.board import AGENT_IDS, AGENT_MARKS


@dataclass
class PublicState:
    board: list[str]
    current_agent: str
    winner: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "board": list(self.board),
            "current_agent": self.current_agent,
            "turn": AGENT_MARKS[self.current_agent],
            "winner": self.winner,
            "agent_ids": list(AGENT_IDS),
        }

    def diff(self, other: PublicState) -> dict[str, Any]:
        changes: dict[str, Any] = {}
        if self.board != other.board:
            changes["board"] = {"from": other.board, "to": self.board}
        if self.current_agent != other.current_agent:
            changes["current_agent"] = {"from": other.current_agent, "to": self.current_agent}
        if self.winner != other.winner:
            changes["winner"] = {"from": other.winner, "to": self.winner}
        return changes


@dataclass
class PrivateState:
    episode_id: str
    scenario_id: str
    seed: int
    step_index: int
    ply: int
    reward_last: dict[str, float] = field(default_factory=lambda: {"agent_0": 0.0, "agent_1": 0.0})
    total_reward: dict[str, float] = field(default_factory=lambda: {"agent_0": 0.0, "agent_1": 0.0})
    terminated: bool = False
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "step_index": self.step_index,
            "ply": self.ply,
            "reward_last": dict(self.reward_last),
            "total_reward": dict(self.total_reward),
            "terminated": self.terminated,
            "truncated": self.truncated,
        }

    def diff(self, other: PrivateState) -> dict[str, Any]:
        changes: dict[str, Any] = {}
        for key in ("step_index", "ply", "terminated", "truncated"):
            left = getattr(self, key)
            right = getattr(other, key)
            if left != right:
                changes[key] = {"from": right, "to": left}
        for key in ("reward_last", "total_reward"):
            left = getattr(self, key)
            right = getattr(other, key)
            if left != right:
                changes[key] = {"from": dict(right), "to": dict(left)}
        return changes


@dataclass
class SimSnapshot:
    public: PublicState
    private: PrivateState
    nev_events: list[dict[str, Any]] = field(default_factory=list)
