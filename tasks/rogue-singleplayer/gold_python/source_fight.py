"""Source-faithful Rogue player fight, killed, and remove_mon slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_rogue import GOLD, RogueRng, WEAPON


CANHUH = 0o000001
ISBLIND = 0o000004
ISMISL = 0o000004
ISTARGET = 0o000200
ISHELD = 0o000400
ISHUH = 0o001000
ISHALU = 0o004000
ISRUN = 0o020000

NO_WEAPON = -1
BOW = 2
ARROW = 3
VS_MAGIC = 3

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

STR_PLUS = [-7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3]
ADD_DAM = [-7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6]


@dataclass
class FightStats:
    strength: int
    exp: int
    level: int
    arm: int
    hp: int
    damage: str
    max_hp: int
    flags: int = ISRUN

    def to_dict(self) -> dict[str, Any]:
        return {
            "strength": self.strength,
            "exp": self.exp,
            "level": self.level,
            "arm": self.arm,
            "hp": self.hp,
            "damage": self.damage,
            "max_hp": self.max_hp,
            "flags": self.flags,
        }


@dataclass
class FightWeapon:
    obj_type: str
    which: int
    hplus: int
    dplus: int
    damage: str
    hurl_damage: str
    launch: int
    flags: int
    name: str = "weapon"


@dataclass
class FightObject:
    obj_type: str
    name: str
    goldval: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.obj_type, "name": self.name, "goldval": self.goldval}


@dataclass
class FightMonster:
    monster_type: str
    stats: FightStats
    flags: int = ISRUN
    disguise: str | None = None
    pack: list[FightObject] = field(default_factory=list)
    oldch: str = "."

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.monster_type,
            "stats": self.stats.to_dict(),
            "flags": self.flags,
            "disguise": self.disguise,
            "pack": [obj.to_dict() for obj in self.pack],
            "oldch": self.oldch,
        }


@dataclass
class FightWorld:
    rng: RogueRng
    player: FightStats
    player_flags: int = ISRUN
    current_weapon: FightWeapon | None = None
    count: int = 4
    quiet: int = 7
    terse: bool = False
    to_death: bool = False
    has_hit: bool = False
    fight_flush: bool = True
    level: int = 1
    max_level: int = 1
    max_hp: int = 30
    vf_hit: int = 0
    fallpos_ok: bool = False
    monster_present: bool = True
    markers: list[str] = field(default_factory=list)
    dropped: list[FightObject] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rng_seed": self.rng.seed,
            "player": self.player.to_dict(),
            "player_flags": self.player_flags,
            "count": self.count,
            "quiet": self.quiet,
            "terse": self.terse,
            "to_death": self.to_death,
            "has_hit": self.has_hit,
            "level": self.level,
            "max_level": self.max_level,
            "max_hp": self.max_hp,
            "vf_hit": self.vf_hit,
            "monster_present": self.monster_present,
            "markers": self.markers,
            "dropped": [obj.to_dict() for obj in self.dropped],
            "trace": self.trace,
        }


def fight(world: FightWorld, monster: FightMonster, weapon: FightWeapon | None, thrown: bool) -> bool:
    world.count = 0
    world.quiet = 0
    world.markers.append("runto")
    if monster.monster_type == "X" and monster.disguise != "X" and not (world.player_flags & ISBLIND):
        monster.disguise = "X"
        world.markers.append("xeroc_reveal")
        if world.player_flags & ISHALU:
            world.trace["xeroc_hallu"] = chr(world.rng.rnd(26) + ord("A"))
        if not thrown:
            return False

    world.has_hit = world.terse and not world.to_death
    result = _roll_em(world.rng, world.player, monster.stats, weapon, thrown, world.current_weapon)
    world.trace["roll_hit"] = result["did_hit"]
    world.trace["roll_rng"] = world.rng.seed
    if result["did_hit"]:
        if thrown:
            world.markers.append("thunk")
        else:
            world.markers.append("hit")
        did_confuse = False
        if world.player_flags & CANHUH:
            did_confuse = True
            monster.flags |= ISHUH
            world.player_flags &= ~CANHUH
            world.markers.extend(["endmsg", "hands_stop_glowing"])
            world.has_hit = False
        if monster.stats.hp <= 0:
            killed(world, monster, True)
        elif did_confuse and not (world.player_flags & ISBLIND):
            world.markers.append("appears_confused")
        return True
    if thrown:
        world.markers.append("bounce")
    else:
        world.markers.append("miss")
    return False


def killed(world: FightWorld, monster: FightMonster, pr: bool) -> None:
    world.player.exp += monster.stats.exp
    if monster.monster_type == "F":
        world.player_flags &= ~ISHELD
        world.vf_hit = 0
        monster.stats.damage = "000x0"
    if monster.monster_type == "L" and world.fallpos_ok and world.level >= world.max_level:
        goldval = world.rng.gold_calc(world.level)
        saved = _save_magic(world)
        world.trace["leprechaun_gold_saved"] = saved
        if saved:
            for _ in range(4):
                goldval += world.rng.gold_calc(world.level)
        monster.pack.insert(0, FightObject(GOLD, "gold", goldval))
    remove_mon(world, monster, True)
    if pr:
        if world.has_hit:
            world.markers.append("defeated_join")
            world.has_hit = False
        else:
            world.markers.append("defeated")
    _check_level(world)
    if world.fight_flush:
        world.markers.append("flush_type")


def remove_mon(world: FightWorld, monster: FightMonster, waskill: bool) -> None:
    for obj in list(monster.pack):
        monster.pack.remove(obj)
        if waskill:
            world.dropped.append(obj)
            world.markers.append(f"fall:{obj.name}")
        else:
            world.markers.append(f"discard:{obj.name}")
    world.monster_present = False
    world.markers.append(f"mvaddch:{monster.oldch}")
    world.markers.append("detach_monster")
    if monster.flags & ISTARGET:
        world.trace["target_removed"] = True
        world.to_death = False
        if world.fight_flush:
            world.markers.append("flush_type")
    world.markers.append("discard_monster")


def source_fight_report() -> dict[str, Any]:
    return {"schema": "gamebench.rogue.source_fight.v1", "cases": [_run_case(case) for case in _cases()]}


def _roll_em(
    rng: RogueRng,
    attacker: FightStats,
    defender: FightStats,
    weapon: FightWeapon | None,
    hurl: bool,
    current_weapon: FightWeapon | None,
) -> dict[str, Any]:
    if weapon is None:
        damage_expression = attacker.damage
        hplus = 0
        dplus = 0
    else:
        hplus = weapon.hplus
        dplus = weapon.dplus
        damage_expression = weapon.damage
        if hurl:
            if weapon.flags & ISMISL and current_weapon is not None and current_weapon.which == weapon.launch:
                damage_expression = weapon.hurl_damage
                hplus += current_weapon.hplus
                dplus += current_weapon.dplus
            elif weapon.launch < 0:
                damage_expression = weapon.hurl_damage
    if not (defender.flags & ISRUN):
        hplus += 4
    did_hit = False
    attacks: list[dict[str, Any]] = []
    for ndice, nsides in _damage_terms(damage_expression):
        swing_roll = rng.rnd(20)
        need = (20 - attacker.level) - defender.arm
        hit = swing_roll + hplus + STR_PLUS[attacker.strength] >= need
        attack = {"ndice": ndice, "nsides": nsides, "swing_roll": swing_roll, "need": need, "hit": hit}
        if hit:
            damage_roll = rng.roll(ndice, nsides)
            damage = dplus + damage_roll + ADD_DAM[attacker.strength]
            applied = max(0, damage)
            defender.hp -= applied
            attack.update({"damage_roll": damage_roll, "damage": damage, "applied": applied})
            did_hit = True
        attacks.append(attack)
    return {"did_hit": did_hit, "damage_expression": damage_expression, "attacks": attacks}


def _check_level(world: FightWorld) -> None:
    next_level = 1
    for threshold in E_LEVELS:
        if threshold == 0 or threshold > world.player.exp:
            break
        next_level += 1
    old_level = world.player.level
    world.player.level = next_level
    if next_level > old_level:
        add = world.rng.roll(next_level - old_level, 10)
        world.max_hp += add
        world.player.hp += add
        world.markers.append(f"welcome:{next_level}")
        world.trace["level_add"] = add


def _save_magic(world: FightWorld) -> bool:
    need = 14 + VS_MAGIC - world.player.level // 2
    roll = world.rng.roll(1, 20)
    world.trace["magic_save_roll"] = roll
    return roll >= need


def _damage_terms(expression: str) -> list[tuple[int, int]]:
    terms = []
    for part in expression.split("/"):
        if "x" not in part:
            continue
        ndice, nsides = part.split("x", 1)
        terms.append((int(ndice), int(nsides)))
    return terms


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    world = _world(case)
    monster = FightMonster(
        monster_type=case.get("type", "K"),
        stats=_stats(case.get("monster_stats", {})),
        flags=case.get("monster_flags", ISRUN),
        disguise=case.get("disguise", case.get("type", "K")),
        pack=[FightObject(**obj) for obj in case.get("monster_pack", [])],
        oldch=case.get("oldch", "."),
    )
    weapon = _weapon(case.get("weapon"))
    returned = fight(world, monster, weapon, case.get("thrown", False))
    return {"name": case["name"], "seed": case["seed"], "returned": returned, "monster": monster.to_dict(), "world": world.to_dict()}


def _world(case: dict[str, Any]) -> FightWorld:
    return FightWorld(
        rng=RogueRng(case["seed"]),
        player=_stats(case.get("player_stats", {})),
        player_flags=case.get("player_flags", ISRUN),
        current_weapon=_weapon(case.get("current_weapon")),
        count=case.get("count", 4),
        quiet=case.get("quiet", 7),
        terse=case.get("terse", False),
        to_death=case.get("to_death", False),
        has_hit=case.get("has_hit", False),
        fight_flush=case.get("fight_flush", True),
        level=case.get("level", 1),
        max_level=case.get("max_level", 1),
        max_hp=case.get("max_hp", case.get("player_stats", {}).get("max_hp", 30)),
        vf_hit=case.get("vf_hit", 0),
        fallpos_ok=case.get("fallpos_ok", False),
    )


def _stats(overrides: dict[str, Any]) -> FightStats:
    base = {"strength": 16, "exp": 0, "level": 5, "arm": 6, "hp": 30, "damage": "1x1", "max_hp": 30, "flags": ISRUN}
    base.update(overrides)
    return FightStats(**base)


def _weapon(payload: dict[str, Any] | None) -> FightWeapon | None:
    if payload is None:
        return None
    return FightWeapon(
        obj_type=payload.get("obj_type", WEAPON),
        which=payload.get("which", NO_WEAPON),
        hplus=payload.get("hplus", 0),
        dplus=payload.get("dplus", 0),
        damage=payload.get("damage", "1x1"),
        hurl_damage=payload.get("hurl_damage", "1x1"),
        launch=payload.get("launch", NO_WEAPON),
        flags=payload.get("flags", 0),
        name=payload.get("name", "weapon"),
    )


def _cases() -> list[dict[str, Any]]:
    hard_to_hit = {"level": 1, "arm": -10, "hp": 30, "max_hp": 30, "damage": "1x1", "flags": ISRUN}
    return [
        {"name": "xeroc_melee_reveal_returns_false", "seed": 1, "type": "X", "disguise": "A", "player_flags": ISRUN | ISHALU, "monster_stats": hard_to_hit},
        {
            "name": "thrown_xeroc_continues_hits",
            "seed": 1,
            "type": "X",
            "disguise": "A",
            "thrown": True,
            "monster_stats": {"arm": 20, "hp": 30, "damage": "1x1"},
            "weapon": {"obj_type": WEAPON, "which": ARROW, "damage": "1x1", "hurl_damage": "2x3", "launch": BOW, "flags": ISMISL},
            "current_weapon": {"obj_type": WEAPON, "which": BOW, "hplus": 1, "dplus": 2, "damage": "1x1", "hurl_damage": "1x1", "launch": NO_WEAPON, "flags": 0},
        },
        {"name": "melee_miss", "seed": 7, "type": "K", "monster_stats": hard_to_hit},
        {"name": "canhuh_confuses_monster", "seed": 1, "type": "K", "player_flags": ISRUN | CANHUH, "monster_stats": {"arm": 20, "hp": 30, "damage": "1x1"}},
        {"name": "kill_regular_levels_up", "seed": 1, "type": "K", "player_stats": {"exp": 9, "level": 1, "hp": 12, "max_hp": 12}, "monster_stats": {"arm": 20, "hp": 1, "exp": 20, "damage": "1x1"}, "max_hp": 12},
        {"name": "kill_flytrap_unholds", "seed": 1, "type": "F", "player_flags": ISRUN | ISHELD, "monster_stats": {"arm": 20, "hp": 1, "exp": 5, "damage": "1x1"}, "vf_hit": 3},
        {
            "name": "kill_leprechaun_drops_gold",
            "seed": 1,
            "type": "L",
            "player_stats": {"level": 10, "hp": 30, "max_hp": 30},
            "monster_stats": {"arm": 20, "hp": 1, "exp": 10, "damage": "1x1"},
            "level": 8,
            "max_level": 8,
            "fallpos_ok": True,
        },
        {
            "name": "kill_target_clears_to_death",
            "seed": 1,
            "type": "K",
            "monster_flags": ISRUN | ISTARGET,
            "monster_stats": {"arm": 20, "hp": 1, "exp": 1, "damage": "1x1"},
            "to_death": True,
        },
        {
            "name": "remove_mon_drops_pack",
            "seed": 1,
            "type": "K",
            "monster_stats": {"arm": 20, "hp": 1, "exp": 1, "damage": "1x1"},
            "monster_pack": [{"obj_type": WEAPON, "name": "club"}, {"obj_type": GOLD, "name": "gold", "goldval": 12}],
        },
    ]
