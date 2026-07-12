"""Source-faithful Rogue combat math slices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from source_rogue import RogueRng, WEAPON


VS_POISON = 0
VS_MAGIC = 3

ISRUN = 0o020000
ISMISL = 0o000004

R_PROTECT = 0
R_ADDHIT = 7
R_ADDDAM = 8

BOW = 2
ARROW = 3
NO_WEAPON = -1

STR_PLUS = [-7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3]
ADD_DAM = [-7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6]


@dataclass
class SourceStats:
    strength: int
    exp: int
    level: int
    arm: int
    hp: int
    damage: str
    max_hp: int
    flags: int = 0

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
class SourceWeapon:
    which: int
    hplus: int
    dplus: int
    damage: str
    hurl_damage: str
    launch: int
    flags: int
    obj_type: str = WEAPON

    def to_dict(self) -> dict[str, Any]:
        return {
            "which": self.which,
            "hplus": self.hplus,
            "dplus": self.dplus,
            "damage": self.damage,
            "hurl_damage": self.hurl_damage,
            "launch": self.launch,
            "flags": self.flags,
            "type": self.obj_type,
        }


@dataclass
class SourceRing:
    which: int
    arm: int


@dataclass
class RollEmResult:
    did_hit: bool
    attacker: SourceStats
    defender: SourceStats
    rng_seed: int
    attacks: list[dict[str, Any]]
    damage_expression: str
    hplus: int
    dplus: int
    defender_arm: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "did_hit": self.did_hit,
            "attacker": self.attacker.to_dict(),
            "defender": self.defender.to_dict(),
            "rng_seed": self.rng_seed,
            "attacks": self.attacks,
            "damage_expression": self.damage_expression,
            "hplus": self.hplus,
            "dplus": self.dplus,
            "defender_arm": self.defender_arm,
        }


def swing(rng: RogueRng, at_lvl: int, op_arm: int, wplus: int) -> dict[str, Any]:
    result = rng.rnd(20)
    need = (20 - at_lvl) - op_arm
    return {"roll": result, "need": need, "hit": result + wplus >= need, "rng_seed": rng.seed}


def save_throw(rng: RogueRng, which: int, level: int) -> dict[str, Any]:
    need = 14 + which - level // 2
    roll = rng.roll(1, 20)
    return {"which": which, "level": level, "need": need, "roll": roll, "saved": roll >= need, "rng_seed": rng.seed}


def save(rng: RogueRng, which: int, player: SourceStats, left_ring: SourceRing | None = None, right_ring: SourceRing | None = None) -> dict[str, Any]:
    adjusted = which
    if which == VS_MAGIC:
        if left_ring is not None and left_ring.which == R_PROTECT:
            adjusted -= left_ring.arm
        if right_ring is not None and right_ring.which == R_PROTECT:
            adjusted -= right_ring.arm
    payload = save_throw(rng, adjusted, player.level)
    payload["original_which"] = which
    return payload


def roll_em(
    seed: int,
    attacker: SourceStats,
    defender: SourceStats,
    *,
    weapon: SourceWeapon | None = None,
    hurl: bool = False,
    weapon_is_current: bool = False,
    current_weapon: SourceWeapon | None = None,
    current_armor_arm: int | None = None,
    left_ring: SourceRing | None = None,
    right_ring: SourceRing | None = None,
    defender_is_player: bool = False,
) -> RollEmResult:
    rng = RogueRng(seed)
    attacker = SourceStats(**attacker.to_dict())
    defender = SourceStats(**defender.to_dict())
    if weapon is None:
        damage_expression = attacker.damage
        hplus = 0
        dplus = 0
    else:
        hplus = weapon.hplus
        dplus = weapon.dplus
        if weapon_is_current:
            if left_ring is not None and left_ring.which == R_ADDDAM:
                dplus += left_ring.arm
            elif left_ring is not None and left_ring.which == R_ADDHIT:
                hplus += left_ring.arm
            if right_ring is not None and right_ring.which == R_ADDDAM:
                dplus += right_ring.arm
            elif right_ring is not None and right_ring.which == R_ADDHIT:
                hplus += right_ring.arm
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
    defender_arm = defender.arm
    if defender_is_player:
        if current_armor_arm is not None:
            defender_arm = current_armor_arm
        if left_ring is not None and left_ring.which == R_PROTECT:
            defender_arm -= left_ring.arm
        if right_ring is not None and right_ring.which == R_PROTECT:
            defender_arm -= right_ring.arm
    did_hit = False
    attacks: list[dict[str, Any]] = []
    for ndice, nsides in _damage_terms(damage_expression):
        swing_payload = swing(rng, attacker.level, defender_arm, hplus + STR_PLUS[attacker.strength])
        attack_payload: dict[str, Any] = {"ndice": ndice, "nsides": nsides, "swing": swing_payload, "damage_roll": 0, "damage": 0}
        if swing_payload["hit"]:
            damage_roll = rng.roll(ndice, nsides)
            damage = dplus + damage_roll + ADD_DAM[attacker.strength]
            applied = max(0, damage)
            defender.hp -= applied
            did_hit = True
            attack_payload["damage_roll"] = damage_roll
            attack_payload["damage"] = damage
            attack_payload["applied"] = applied
        attacks.append(attack_payload)
    return RollEmResult(
        did_hit=did_hit,
        attacker=attacker,
        defender=defender,
        rng_seed=rng.seed,
        attacks=attacks,
        damage_expression=damage_expression,
        hplus=hplus,
        dplus=dplus,
        defender_arm=defender_arm,
    )


def exp_add(level: int, max_hp: int) -> int:
    if level == 1:
        modifier = max_hp // 8
    else:
        modifier = max_hp // 6
    if level > 9:
        modifier *= 20
    elif level > 6:
        modifier *= 4
    return modifier


def source_combat_report() -> dict[str, Any]:
    return {
        "swing": [
            {"seed": 1, **swing(RogueRng(1), 1, 6, 0)},
            {"seed": 7, **swing(RogueRng(7), 5, 2, 3)},
            {"seed": -17, **swing(RogueRng(-17), 12, -1, 5)},
        ],
        "save": [
            {"seed": 1, **save_throw(RogueRng(1), VS_POISON, 1)},
            {"seed": 7, **save(RogueRng(7), VS_MAGIC, SourceStats(16, 0, 5, 6, 12, "1x4", 12), SourceRing(R_PROTECT, 2), None)},
            {"seed": -17, **save(RogueRng(-17), VS_MAGIC, SourceStats(16, 0, 10, 6, 20, "1x4", 20), SourceRing(R_PROTECT, 1), SourceRing(R_PROTECT, 3))},
        ],
        "roll_em": [
            {"name": "monster_claw", "result": roll_em(1, SourceStats(10, 0, 3, 5, 12, "1x3/1x3", 12), SourceStats(10, 0, 1, 7, 10, "1x4", 10)).to_dict()},
            {
                "name": "current_mace_with_rings",
                "result": roll_em(
                    7,
                    SourceStats(18, 0, 4, 5, 20, "1x4", 20),
                    SourceStats(10, 0, 5, 4, 30, "1x6", 30),
                    weapon=SourceWeapon(0, 1, 1, "2x4", "1x3", NO_WEAPON, 0),
                    weapon_is_current=True,
                    left_ring=SourceRing(R_ADDHIT, 2),
                    right_ring=SourceRing(R_ADDDAM, 3),
                ).to_dict(),
            },
            {
                "name": "hurled_arrow_with_bow",
                "result": roll_em(
                    12345,
                    SourceStats(16, 0, 6, 5, 22, "1x4", 22),
                    SourceStats(10, 0, 8, 2, 45, "2x6", 45),
                    weapon=SourceWeapon(ARROW, 0, 0, "1x1", "2x3", BOW, ISMISL),
                    hurl=True,
                    current_weapon=SourceWeapon(BOW, 1, 2, "1x1", "1x1", NO_WEAPON, 0),
                ).to_dict(),
            },
            {
                "name": "defender_player_protection",
                "result": roll_em(
                    -17,
                    SourceStats(20, 0, 9, 2, 50, "3x4/2x5", 50),
                    SourceStats(16, 0, 7, 8, 35, "1x4", 35),
                    defender_is_player=True,
                    current_armor_arm=4,
                    left_ring=SourceRing(R_PROTECT, 1),
                    right_ring=SourceRing(R_PROTECT, 2),
                ).to_dict(),
            },
        ],
        "exp_add": [
            {"level": 1, "max_hp": 7, "value": exp_add(1, 7)},
            {"level": 5, "max_hp": 30, "value": exp_add(5, 30)},
            {"level": 8, "max_hp": 48, "value": exp_add(8, 48)},
            {"level": 12, "max_hp": 90, "value": exp_add(12, 90)},
        ],
    }


def _damage_terms(expression: str) -> list[tuple[int, int]]:
    terms = []
    for part in expression.split("/"):
        if "x" not in part:
            continue
        ndice, nsides = part.split("x", 1)
        terms.append((int(ndice), int(nsides)))
    return terms
