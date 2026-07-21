"""Source-faithful Rogue monster attack side-effect slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_combat import R_PROTECT, VS_MAGIC, VS_POISON, SourceRing, SourceStats, roll_em, save
from source_rogue import AMULET, ARMOR, BORE_LEVEL, POTION, RING, SCROLL, STICK, WEAPON, RogueRng


ISBLIND = 0o000004
ISCANC = 0o000010
ISTARGET = 0o000200
ISHELD = 0o000400
ISHALU = 0o004000
ISRUN = 0o020000

E_LEVELS = [
    10,
    20,
    40,
    80,
    160,
    320,
    640,
    1300,
    2600,
    5200,
    13000,
    26000,
    50000,
    100000,
    200000,
    400000,
    800000,
    2000000,
    4000000,
    8000000,
    0,
]


@dataclass
class AttackItem:
    name: str
    obj_type: str
    magic: bool = False
    equipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.obj_type, "magic": self.magic, "equipped": self.equipped}


@dataclass
class AttackMonster:
    monster_type: str
    stats: SourceStats
    flags: int = ISRUN
    disguise: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.monster_type, "flags": self.flags, "disguise": self.disguise, "stats": self.stats.to_dict()}


@dataclass
class AttackWorld:
    rng: RogueRng
    player: SourceStats
    player_flags: int = ISRUN
    current_armor_arm: int | None = 6
    left_ring: SourceRing | None = None
    right_ring: SourceRing | None = None
    sustain_strength: bool = False
    running: bool = True
    count: int = 4
    quiet: int = 7
    to_death: bool = False
    kamikaze: bool = False
    has_hit: bool = False
    max_hit: int = 0
    no_command: int = 0
    purse: int = 200
    level: int = 1
    max_hp: int = 30
    vf_hit: int = 0
    fight_flush: bool = True
    pack: list[AttackItem] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rng_seed": self.rng.seed,
            "player": self.player.to_dict(),
            "player_flags": self.player_flags,
            "running": self.running,
            "count": self.count,
            "quiet": self.quiet,
            "to_death": self.to_death,
            "kamikaze": self.kamikaze,
            "has_hit": self.has_hit,
            "max_hit": self.max_hit,
            "no_command": self.no_command,
            "purse": self.purse,
            "level": self.level,
            "max_hp": self.max_hp,
            "vf_hit": self.vf_hit,
            "pack": [item.to_dict() for item in self.pack],
            "markers": self.markers,
            "trace": self.trace,
        }


def attack(world: AttackWorld, monster: AttackMonster) -> int:
    world.running = False
    world.count = 0
    world.quiet = 0
    if world.to_death and not (monster.flags & ISTARGET):
        world.to_death = False
        world.kamikaze = False
        world.trace["target_cancelled"] = True
    if monster.monster_type == "X" and monster.disguise != "X" and not (world.player_flags & ISBLIND):
        monster.disguise = "X"
        world.markers.append("xeroc_reveal")
        if world.player_flags & ISHALU:
            hallu = chr(world.rng.rnd(26) + ord("A"))
            world.trace["xeroc_hallu"] = hallu

    oldhp = world.player.hp
    result = roll_em(
        world.rng.seed,
        monster.stats,
        world.player,
        defender_is_player=True,
        current_armor_arm=world.current_armor_arm,
        left_ring=world.left_ring,
        right_ring=world.right_ring,
    )
    world.rng.seed = result.rng_seed
    world.player = result.defender
    world.trace["roll_hit"] = result.did_hit
    world.trace["roll_rng"] = result.rng_seed

    monster_removed = False
    if result.did_hit:
        if monster.monster_type != "I":
            if world.has_hit:
                world.markers.append("addmsg_join")
            world.markers.append("hit")
        elif world.has_hit:
            world.markers.append("endmsg")
        world.has_hit = False
        if world.player.hp <= 0:
            world.markers.append(f"death:{monster.monster_type}")
        elif not world.kamikaze:
            damage = oldhp - world.player.hp
            if damage > world.max_hit:
                world.max_hit = damage
            if world.player.hp <= world.max_hit:
                world.to_death = False
        if not (monster.flags & ISCANC):
            monster_removed = _special_hit(world, monster)
    elif monster.monster_type != "I":
        if world.has_hit:
            world.markers.append("addmsg_join")
            world.has_hit = False
        if monster.monster_type == "F":
            world.player.hp -= world.vf_hit
            if world.player.hp <= 0:
                world.markers.append("death:F")
        world.markers.append("miss")

    if world.fight_flush and not world.to_death:
        world.markers.append("flush_type")
    world.count = 0
    world.markers.append("status")
    return -1 if monster_removed else 0


def source_attack_report() -> dict[str, Any]:
    return {"schema": "gamebench.rogue.source_attack.v1", "cases": [_run_case(case) for case in _cases()]}


def _special_hit(world: AttackWorld, monster: AttackMonster) -> bool:
    if monster.monster_type == "A":
        world.markers.append("rust_armor")
    elif monster.monster_type == "I":
        world.player_flags &= ~ISRUN
        if world.no_command == 0:
            world.markers.append("freeze_msg")
        freeze_roll = world.rng.rnd(2) + 2
        world.trace["ice_roll"] = freeze_roll
        world.no_command += freeze_roll
        if world.no_command > BORE_LEVEL:
            world.markers.append("death:h")
    elif monster.monster_type == "R":
        payload = save(world.rng, VS_POISON, world.player, world.left_ring, world.right_ring)
        world.trace["poison_saved"] = payload["saved"]
        world.trace["poison_roll"] = payload["roll"]
        if not payload["saved"]:
            if not world.sustain_strength:
                world.player.strength -= 1
                world.markers.append("chg_str:-1")
            elif not world.to_death:
                world.markers.append("sustain_strength")
    elif monster.monster_type in {"W", "V"}:
        drain_roll = world.rng.rnd(100)
        world.trace["drain_roll"] = drain_roll
        threshold = 15 if monster.monster_type == "W" else 30
        if drain_roll < threshold:
            if monster.monster_type == "W":
                if world.player.exp == 0:
                    world.markers.append("death:W")
                world.player.level -= 1
                if world.player.level == 0:
                    world.player.exp = 0
                    world.player.level = 1
                else:
                    world.player.exp = E_LEVELS[world.player.level - 1] + 1
                fewer = world.rng.roll(1, 10)
            else:
                fewer = world.rng.roll(1, 3)
            world.trace["drain_fewer"] = fewer
            world.player.hp -= fewer
            world.max_hp -= fewer
            if world.player.hp <= 0:
                world.player.hp = 1
            if world.max_hp <= 0:
                world.markers.append(f"death:{monster.monster_type}")
            world.markers.append("drain")
    elif monster.monster_type == "F":
        world.player_flags |= ISHELD
        world.vf_hit += 1
        monster.stats.damage = f"{world.vf_hit}x1"
        world.player.hp -= 1
        if world.player.hp <= 0:
            world.markers.append("death:F")
    elif monster.monster_type == "L":
        lastpurse = world.purse
        world.purse -= world.rng.gold_calc(world.level)
        payload = save(world.rng, VS_MAGIC, world.player, world.left_ring, world.right_ring)
        world.trace["gold_saved"] = payload["saved"]
        world.trace["gold_save_roll"] = payload["roll"]
        if not payload["saved"]:
            for _ in range(4):
                world.purse -= world.rng.gold_calc(world.level)
        if world.purse < 0:
            world.purse = 0
        world.markers.append("remove_mon")
        if world.purse != lastpurse:
            world.markers.append("purse_lighter")
        return True
    elif monster.monster_type == "N":
        stolen_index = _pick_nymph_steal(world)
        if stolen_index is not None:
            stolen = world.pack.pop(stolen_index)
            world.trace["stolen"] = stolen.name
            world.markers.extend(["remove_mon", "leave_pack", "discard"])
            return True
    return False


def _pick_nymph_steal(world: AttackWorld) -> int | None:
    steal_index: int | None = None
    nobj = 0
    for index, item in enumerate(world.pack):
        if item.equipped or not _is_magic(item):
            continue
        nobj += 1
        if world.rng.rnd(nobj) == 0:
            steal_index = index
    return steal_index


def _is_magic(item: AttackItem) -> bool:
    if item.obj_type in {POTION, SCROLL, STICK, RING, AMULET}:
        return True
    if item.obj_type in {ARMOR, WEAPON}:
        return item.magic
    return False


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    world = _world(case)
    monster = AttackMonster(
        monster_type=case["type"],
        stats=_stats(case.get("monster_stats", {})),
        flags=case.get("monster_flags", ISRUN),
        disguise=case.get("disguise", case["type"]),
    )
    returned = attack(world, monster)
    return {"name": case["name"], "seed": case["seed"], "returned": returned, "monster": monster.to_dict(), "world": world.to_dict()}


def _world(case: dict[str, Any]) -> AttackWorld:
    left_ring = _ring(case.get("left_ring"))
    right_ring = _ring(case.get("right_ring"))
    return AttackWorld(
        rng=RogueRng(case["seed"]),
        player=_stats(case.get("player_stats", {})),
        player_flags=case.get("player_flags", ISRUN),
        current_armor_arm=case.get("armor_arm", 6),
        left_ring=left_ring,
        right_ring=right_ring,
        sustain_strength=case.get("sustain_strength", False),
        running=case.get("running", True),
        count=case.get("count", 4),
        quiet=case.get("quiet", 7),
        to_death=case.get("to_death", False),
        kamikaze=case.get("kamikaze", False),
        has_hit=case.get("has_hit", False),
        max_hit=case.get("max_hit", 0),
        no_command=case.get("no_command", 0),
        purse=case.get("purse", 200),
        level=case.get("level", 1),
        max_hp=case.get("max_hp", case.get("player_stats", {}).get("max_hp", 30)),
        vf_hit=case.get("vf_hit", 0),
        fight_flush=case.get("fight_flush", True),
        pack=[AttackItem(**item) for item in case.get("pack", [])],
    )


def _stats(overrides: dict[str, Any]) -> SourceStats:
    base = {"strength": 16, "exp": 100, "level": 20, "arm": 6, "hp": 30, "damage": "1x1", "max_hp": 30, "flags": ISRUN}
    base.update(overrides)
    return SourceStats(**base)


def _ring(payload: dict[str, int] | None) -> SourceRing | None:
    if payload is None:
        return None
    return SourceRing(payload["which"], payload["arm"])


def _cases() -> list[dict[str, Any]]:
    hard_to_hit_player = {"level": 1, "arm": -10, "hp": 30, "max_hp": 30, "damage": "1x1", "flags": ISRUN}
    return [
        {"name": "basic_hit_updates_max_hit", "seed": 1, "type": "K", "monster_stats": {"level": 20, "damage": "1x4"}, "player_stats": {"hp": 20, "max_hp": 20}, "max_hit": 1},
        {"name": "basic_miss_message", "seed": 7, "type": "K", "monster_stats": {"level": 1, "damage": "1x1"}, "player_stats": hard_to_hit_player, "armor_arm": -10, "has_hit": True},
        {"name": "target_keeps_to_death", "seed": 1, "type": "K", "monster_flags": ISRUN | ISTARGET, "monster_stats": {"level": 20, "damage": "1x1"}, "to_death": True, "kamikaze": True},
        {"name": "xeroc_hallu_reveals", "seed": 7, "type": "X", "disguise": "A", "player_flags": ISRUN | ISHALU, "monster_stats": {"level": 1, "damage": "1x1"}, "player_stats": hard_to_hit_player, "armor_arm": -10},
        {"name": "aquator_rusts_armor", "seed": 1, "type": "A", "monster_stats": {"level": 20, "damage": "1x1"}},
        {"name": "ice_freezes_player", "seed": 1, "type": "I", "monster_stats": {"level": 20, "damage": "1x1"}, "no_command": 49},
        {"name": "rattlesnake_poison_strength", "seed": 2, "type": "R", "monster_stats": {"level": 20, "damage": "1x1"}, "player_stats": {"level": 1, "strength": 16, "hp": 30, "max_hp": 30}},
        {"name": "rattlesnake_sustain_strength", "seed": 2, "type": "R", "monster_stats": {"level": 20, "damage": "1x1"}, "player_stats": {"level": 1, "strength": 16, "hp": 30, "max_hp": 30}, "sustain_strength": True},
        {"name": "wraith_energy_drain", "seed": 3, "type": "W", "monster_stats": {"level": 20, "damage": "1x1"}, "player_stats": {"level": 5, "exp": 200, "hp": 30, "max_hp": 30}, "max_hp": 30},
        {"name": "venus_flytrap_hit_holds", "seed": 1, "type": "F", "monster_stats": {"level": 20, "damage": "1x1"}, "vf_hit": 1},
        {"name": "venus_flytrap_miss_crushes", "seed": 7, "type": "F", "monster_stats": {"level": 1, "damage": "1x1"}, "player_stats": hard_to_hit_player, "armor_arm": -10, "vf_hit": 3},
        {"name": "leprechaun_steals_gold", "seed": 1, "type": "L", "monster_stats": {"level": 20, "damage": "1x1"}, "purse": 200, "level": 4, "left_ring": {"which": R_PROTECT, "arm": 2}},
        {
            "name": "nymph_steals_magic_item",
            "seed": 1,
            "type": "N",
            "monster_stats": {"level": 20, "damage": "1x1"},
            "pack": [
                {"name": "plain-food", "obj_type": ":", "magic": False, "equipped": False},
                {"name": "worn-armor", "obj_type": "]", "magic": True, "equipped": True},
                {"name": "wand", "obj_type": "/", "magic": True, "equipped": False},
                {"name": "plus-mace", "obj_type": ")", "magic": True, "equipped": False},
            ],
        },
    ]
