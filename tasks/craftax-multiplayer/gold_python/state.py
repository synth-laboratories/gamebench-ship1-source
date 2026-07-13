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
    armour_slots: list[int] = field(default_factory=lambda: [0] * 4)
    bow: int = 0
    arrows: int = 0
    torches: int = 0
    books: int = 0
    saplings: int = 0
    potions: dict[str, int] = field(default_factory=lambda: {colour: 0 for colour in ("red", "green", "blue", "pink", "cyan", "yellow")})
    dexterity: int = 1
    strength: int = 1
    intelligence: int = 1
    xp: int = 0
    level_points: int = 0
    sword_enchantment: str | None = None
    armour_enchantment: str | None = None
    armour_enchantments: list[str | None] = field(default_factory=lambda: [None] * 4)
    bow_enchantment: str | None = None
    learned_spell: bool = False
    sleeping: bool = False
    resting: bool = False
    recover: float = 0.0
    hunger: float = 0.0
    thirst: float = 0.0
    fatigue: float = 0.0
    recover_mana: float = 0.0
    request_type: str | None = None
    request_duration: int = 0


@dataclass
class Monster:
    id: str
    kind: str
    level: int
    x: int
    y: int
    health: int
    damage: int
    category: str = "melee"
    attack_cooldown: int = 0


@dataclass
class Projectile:
    owner: str
    level: int
    x: int
    y: int
    dx: int
    dy: int
    damage: int
    ttl: int
    kind: str = "arrow"
    hostile: bool = False


@dataclass
class Plant:
    level: int
    x: int
    y: int
    age: int


@dataclass
class WorldState:
    seed: int
    timestep: int
    max_timesteps: int
    players: list[Player]
    maps: list[list[list[str]]]
    monsters: list[Monster]
    item_maps: list[list[list[str | None]]] = field(default_factory=list)
    ladders_up: list[list[list[int]]] = field(default_factory=list)
    ladders_down: list[list[list[int]]] = field(default_factory=list)
    projectiles: list[Projectile] = field(default_factory=list)
    plants: list[Plant] = field(default_factory=list)
    boss_health: int = 8
    boss_progress: int = 0
    boss_wave_timer: int = 7
    chests_opened: list[list[bool]] = field(default_factory=list)
    monsters_killed: list[int] = field(default_factory=lambda: [10] + [0] * 8)
    potion_mapping: list[str] = field(default_factory=lambda: ["health", "strength", "dexterity", "intelligence", "mana", "energy"])
    light_level: float = 1.0
    achievements: dict[str, bool] = field(default_factory=lambda: {a: False for a in ACHIEVEMENTS})
    achievements_by_agent: dict[str, dict[str, bool]] = field(default_factory=dict)
    trade_count: int = 0
    food_trade_count: int = 0
    drink_trade_count: int = 0
    revives: int = 0
    ff_damage_dealt: float = 0.0
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
        data["achievements"]={name:bool(data.get("achievements",{}).get(name,False)) for name in ACHIEVEMENTS}
        if not data.get("item_maps"):
            size=len(data["maps"][0]);data["item_maps"]=[[[None for _ in range(size)] for _ in range(size)] for _ in data["maps"]]
        count=len(data["players"])
        data.setdefault("ladders_up",[[[2+i,2] for i in range(count)] for _ in data["maps"]])
        data.setdefault("ladders_down",[[[len(data["maps"][0])-3-i,len(data["maps"][0])-3] for i in range(count)] for _ in data["maps"]])
        if data.get("chests_opened") and isinstance(data["chests_opened"][0],bool):
            count=len(data["players"]);data["chests_opened"]=[[value]*count for value in data["chests_opened"]]
        data["players"] = [Player(**p) for p in data["players"]]
        data.setdefault("achievements_by_agent",{p.agent_id:dict(data["achievements"]) for p in data["players"]})
        data["achievements_by_agent"]={agent:{name:bool(flags.get(name,False)) for name in ACHIEVEMENTS} for agent,flags in data["achievements_by_agent"].items()}
        data["monsters"] = [Monster(**monster) for monster in data["monsters"]]
        data["projectiles"] = [Projectile(**projectile) for projectile in data["projectiles"]]
        data["plants"] = [Plant(**plant) for plant in data["plants"]]
        if any(player.role not in ("warrior", "forager", "miner") for player in data["players"]):
            raise ValueError("invalid player role in checkpoint")
        if any(player.facing not in ("left", "right", "up", "down") for player in data["players"]):
            raise ValueError("invalid player facing in checkpoint")
        return cls(**data)
