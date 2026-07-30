"""FrogsGame public and private state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scoring import Violation


Position = tuple[int, int]


@dataclass
class PublicState:
    board: list[list[str]]
    frogs: list[Position] = field(default_factory=list)
    submitted: bool = False
    violations: list[Violation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "board": self.board,
            "frogs": [[row, col] for row, col in sorted(self.frogs)],
            "submitted": self.submitted,
            "violations": [violation.to_dict() for violation in self.violations],
        }


@dataclass
class PrivateState:
    step_index: int = 0
    tool_call_count: int = 0
    max_tool_calls: int = 200
    total_reward: float = 0.0
    terminated: bool = False
    truncated: bool = False
    config_hash: str = ""
    episode_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "tool_call_count": self.tool_call_count,
            "max_tool_calls": self.max_tool_calls,
            "total_reward": self.total_reward,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "config_hash": self.config_hash,
            "episode_id": self.episode_id,
        }
