"""MiniHack symbolic public and private state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PublicState:
    player: tuple[int, int]
    boulders: list[tuple[int, int]] = field(default_factory=list)
    monsters: list[tuple[int, int]] = field(default_factory=list)
    lava: list[tuple[int, int]] = field(default_factory=list)
    frozen: list[tuple[int, int]] = field(default_factory=list)
    items_on_ground: list[dict[str, Any]] = field(default_factory=list)
    inventory: list[str] = field(default_factory=list)
    boulders_on_target: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "player": [self.player[0], self.player[1]],
            "boulders": [[row, col] for row, col in sorted(self.boulders)],
            "monsters": [[row, col] for row, col in sorted(self.monsters)],
            "lava": [[row, col] for row, col in sorted(self.lava)],
            "frozen": [[row, col] for row, col in sorted(self.frozen)],
            "items_on_ground": self.items_on_ground,
            "inventory": sorted(self.inventory),
            "boulders_on_target": self.boulders_on_target,
        }


@dataclass
class PrivateState:
    step_index: int = 0
    total_reward: float = 0.0
    terminated: bool = False
    truncated: bool = False
    config_hash: str = ""
    episode_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "total_reward": self.total_reward,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "config_hash": self.config_hash,
            "episode_id": self.episode_id,
        }
