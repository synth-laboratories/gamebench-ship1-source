from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .constants import ACHIEVEMENTS, RESOURCES


@dataclass
class Player:
    agent_id: str
    role: str
    x: int
    y: int
    level: int = 0
    health: int = 9
    food: int = 9
    drink: int = 9
    energy: int = 9
    mana: int = 9
    alive: bool = True
    facing: str = "down"
    inventory: dict[str, int] = field(default_factory=lambda: {r: 0 for r in RESOURCES})
    pickaxe: int = 0
    sword: int = 0
    armour: int = 0
    arrows: int = 0
    torches: int = 0
    books: int = 0
    saplings: int = 0
    potions: dict[str, int] = field(default_factory=lambda: {colour: 0 for colour in ("red", "green", "blue", "pink", "cyan", "yellow")})
    dexterity: int = 0
    strength: int = 0
    intelligence: int = 0
    xp: int = 0
    level_points: int = 0
    sword_enchantment: str | None = None
    armour_enchantment: str | None = None
    bow_enchantment: str | None = None
    sleeping: bool = False
    request_type: str | None = None
    request_duration: int = 0


@dataclass
class WorldState:
    seed: int
    timestep: int
    max_timesteps: int
    players: list[Player]
    maps: list[list[list[str]]]
    monsters: list[dict[str, Any]]
    projectiles: list[dict[str, Any]] = field(default_factory=list)
    plants: list[dict[str, Any]] = field(default_factory=list)
    boss_health: int = 24
    boss_progress: int = 0
    boss_wave_timer: int = 0
    light_level: float = 1.0
    achievements: dict[str, bool] = field(default_factory=lambda: {a: False for a in ACHIEVEMENTS})
    trade_count: int = 0
    terminated: bool = False
    termination_reason: str | None = None
    nev: list[dict[str, Any]] = field(default_factory=list)
    legacy_nev: list[str] = field(default_factory=list)
    last_joint_event: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorldState":
        data = dict(raw)
        data["players"] = [Player(**p) for p in data["players"]]
        return cls(**data)
