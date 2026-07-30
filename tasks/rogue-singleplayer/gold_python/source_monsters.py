"""Source-faithful Rogue monster behavior slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_rogue import AMULET, ARMOR, FOOD, GOLD, RING, SCROLL, STAIRS, STICK, WEAPON, POTION, RogueRng


AMULETLEVEL = 26
LAMPDIST = 3
VS_MAGIC = 3
S_SCARE = 10

CANSEE = 0o000002
ISBLIND = 0o000004
ISCANC = 0o000010
ISLEVIT = 0o000010
ISFOUND = 0o000020
ISGREED = 0o000040
ISHASTE = 0o000100
ISHELD = 0o000400
ISHUH = 0o001000
ISINVIS = 0o002000
ISMEAN = 0o004000
ISHALU = 0o004000
ISREGEN = 0o010000
ISRUN = 0o020000
ISFLY = 0o040000

R_PROTECT = 0
R_STEALTH = 12
R_AGGR = 6

LVL_MONS = ["K", "E", "B", "S", "H", "I", "R", "O", "Z", "L", "C", "Q", "A", "N", "Y", "F", "T", "W", "P", "X", "U", "M", "V", "G", "J", "D"]
WAND_MONS = ["K", "E", "B", "S", "H", "\0", "R", "O", "Z", "\0", "C", "Q", "A", "\0", "Y", "\0", "T", "W", "P", "\0", "U", "M", "V", "G", "J", "\0"]
RND_THING_LIST = [POTION, SCROLL, RING, STICK, FOOD, WEAPON, ARMOR, STAIRS, GOLD, AMULET]

MONSTER_NAMES = [
    "aquator",
    "bat",
    "centaur",
    "dragon",
    "emu",
    "venus flytrap",
    "griffin",
    "hobgoblin",
    "ice monster",
    "jabberwock",
    "kestrel",
    "leprechaun",
    "medusa",
    "nymph",
    "orc",
    "phantom",
    "quagga",
    "rattlesnake",
    "snake",
    "troll",
    "black unicorn",
    "vampire",
    "wraith",
    "xeroc",
    "yeti",
    "zombie",
]
MONSTER_CARRY = [0, 0, 15, 100, 0, 0, 20, 0, 0, 70, 0, 0, 40, 100, 15, 0, 0, 0, 0, 50, 0, 20, 0, 30, 30, 0]
MONSTER_EXP = [20, 1, 17, 5000, 2, 80, 2000, 3, 5, 3000, 1, 10, 200, 37, 5, 120, 15, 9, 2, 120, 190, 350, 55, 100, 50, 6]
MONSTER_LEVELS = [5, 1, 4, 10, 1, 8, 13, 1, 1, 15, 1, 3, 8, 3, 1, 8, 3, 2, 1, 6, 7, 8, 5, 7, 4, 2]
MONSTER_ARMOR = [2, 3, 4, -1, 7, 3, 2, 5, 9, 6, 7, 8, 2, 9, 6, 3, 3, 3, 5, 4, -2, 1, 4, 7, 6, 8]
MONSTER_DAMAGE = [
    "0x0/0x0",
    "1x2",
    "1x2/1x5/1x5",
    "1x8/1x8/3x10",
    "1x2",
    "%%%x0",
    "4x3/3x5",
    "1x8",
    "0x0",
    "2x12/2x4",
    "1x4",
    "1x1",
    "3x4/3x4/2x5",
    "0x0",
    "1x8",
    "4x4",
    "1x5/1x5",
    "1x6",
    "1x3",
    "1x8/1x8/2x6",
    "1x9/1x9/2x9",
    "1x10",
    "1x6",
    "4x4",
    "1x6/1x6",
    "1x8",
]
MONSTER_FLAGS = [
    ISMEAN,
    ISFLY,
    0,
    ISMEAN,
    ISMEAN,
    ISMEAN,
    ISMEAN | ISFLY | ISREGEN,
    ISMEAN,
    0,
    0,
    ISMEAN | ISFLY,
    0,
    ISMEAN,
    0,
    ISGREED,
    ISINVIS,
    ISMEAN,
    ISMEAN,
    ISMEAN,
    ISREGEN | ISMEAN,
    ISMEAN,
    ISREGEN | ISMEAN,
    0,
    0,
    0,
    ISMEAN,
]


@dataclass
class Coord:
    y: int
    x: int

    def to_dict(self) -> dict[str, int]:
        return {"y": self.y, "x": self.x}


@dataclass
class SourceMonsterStats:
    strength: int
    exp: int
    level: int
    arm: int
    hp: int
    damage: str
    max_hp: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "strength": self.strength,
            "exp": self.exp,
            "level": self.level,
            "arm": self.arm,
            "hp": self.hp,
            "damage": self.damage,
            "max_hp": self.max_hp,
        }


@dataclass
class SourceMonster:
    monster_type: str
    disguise: str
    pos: Coord
    oldch: str
    room: int
    dest: str
    dest_pos: Coord | None
    flags: int
    turn: bool
    stats: SourceMonsterStats
    pack_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.monster_type,
            "disguise": self.disguise,
            "pos": self.pos.to_dict(),
            "oldch": self.oldch,
            "room": self.room,
            "dest": self.dest,
            "dest_pos": None if self.dest_pos is None else self.dest_pos.to_dict(),
            "flags": self.flags,
            "turn": self.turn,
            "stats": self.stats.to_dict(),
            "pack_count": self.pack_count,
        }


@dataclass
class SourceObject:
    obj_type: str
    which: int
    pos: Coord
    room: int


@dataclass
class SourceRing:
    which: int
    arm: int


@dataclass
class SourceMonsterWorld:
    rng: RogueRng
    level: int
    max_level: int
    hero: Coord
    proom: int
    proom_gold: Coord
    proom_goldval: int
    room_dark: dict[int, bool] = field(default_factory=dict)
    player_flags: int = 0
    left_ring: SourceRing | None = None
    right_ring: SourceRing | None = None
    objects: list[SourceObject] = field(default_factory=list)
    claimed_dests: list[Coord] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rng_seed": self.rng.seed,
            "level": self.level,
            "max_level": self.max_level,
            "hero": self.hero.to_dict(),
            "proom": self.proom,
            "proom_gold": self.proom_gold.to_dict(),
            "proom_goldval": self.proom_goldval,
            "player_flags": self.player_flags,
            "left_ring": None if self.left_ring is None else {"which": self.left_ring.which, "arm": self.left_ring.arm},
            "right_ring": None if self.right_ring is None else {"which": self.right_ring.which, "arm": self.right_ring.arm},
            "markers": self.markers,
            "trace": self.trace,
        }


def randmonster(rng: RogueRng, level: int, *, wander: bool) -> dict[str, Any]:
    monsters = WAND_MONS if wander else LVL_MONS
    attempts: list[dict[str, Any]] = []
    while True:
        raw = level + (rng.rnd(10) - 6)
        index = raw
        if index < 0:
            index = rng.rnd(5)
        if index > 25:
            index = rng.rnd(5) + 21
        monster = monsters[index]
        attempts.append({"raw": raw, "index": index, "monster": monster})
        if monster != "\0":
            return {"level": level, "wander": wander, "monster": monster, "attempts": attempts, "rng_seed": rng.seed}


def new_monster(world: SourceMonsterWorld, monster_type: str, pos: Coord, *, room: int, oldch: str = ".") -> SourceMonster:
    index = ord(monster_type) - ord("A")
    lev_add = max(0, world.level - AMULETLEVEL)
    monster_level = MONSTER_LEVELS[index] + lev_add
    hp = world.rng.roll(monster_level, 8)
    max_hp = hp
    arm = MONSTER_ARMOR[index] - lev_add
    exp = MONSTER_EXP[index] + lev_add * 10 + exp_add(monster_level, max_hp)
    disguise = rnd_thing(world.rng, world.level) if monster_type == "X" else monster_type
    flags = MONSTER_FLAGS[index]
    if world.level > 29:
        flags |= ISHASTE
    monster = SourceMonster(
        monster_type=monster_type,
        disguise=disguise,
        pos=Coord(pos.y, pos.x),
        oldch=oldch,
        room=room,
        dest="none",
        dest_pos=None,
        flags=flags,
        turn=True,
        stats=SourceMonsterStats(strength=10, exp=exp, level=monster_level, arm=arm, hp=hp, damage=MONSTER_DAMAGE[index], max_hp=max_hp),
    )
    if is_wearing(world, R_AGGR):
        runto(world, monster)
    return monster


def runto(world: SourceMonsterWorld, monster: SourceMonster) -> None:
    monster.flags |= ISRUN
    monster.flags &= ~ISHELD
    dest, dest_pos = find_dest(world, monster)
    monster.dest = dest
    monster.dest_pos = dest_pos


def wake_monster(world: SourceMonsterWorld, monster: SourceMonster) -> SourceMonster:
    if not (monster.flags & ISRUN):
        wake_roll = world.rng.rnd(3)
        world.trace["wake_roll"] = wake_roll
        if (
            wake_roll != 0
            and monster.flags & ISMEAN
            and not (monster.flags & ISHELD)
            and not is_wearing(world, R_STEALTH)
            and not (world.player_flags & ISLEVIT)
        ):
            monster.dest = "hero"
            monster.dest_pos = Coord(world.hero.y, world.hero.x)
            monster.flags |= ISRUN
            world.markers.append("monster_runs")

    if (
        monster.monster_type == "M"
        and not (world.player_flags & ISBLIND)
        and not (world.player_flags & ISHALU)
        and not (monster.flags & ISFOUND)
        and not (monster.flags & ISCANC)
        and monster.flags & ISRUN
    ):
        visible = (monster.room == world.proom and not world.room_dark.get(world.proom, False)) or dist(monster.pos, world.hero) < LAMPDIST
        world.trace["medusa_visible"] = visible
        if visible:
            monster.flags |= ISFOUND
            save_payload = save(world, VS_MAGIC, player_level=1)
            world.trace["medusa_save"] = save_payload
            if not save_payload["saved"]:
                world.player_flags |= ISHUH
                world.markers.append("confuse_player")
                world.markers.append("fuse_unconfuse")

    if monster.flags & ISGREED and not (monster.flags & ISRUN):
        monster.flags |= ISRUN
        if world.proom_goldval:
            monster.dest = "gold"
            monster.dest_pos = Coord(world.proom_gold.y, world.proom_gold.x)
        else:
            monster.dest = "hero"
            monster.dest_pos = Coord(world.hero.y, world.hero.x)
        world.markers.append("greed_runs")
    return monster


def find_dest(world: SourceMonsterWorld, monster: SourceMonster) -> tuple[str, Coord | None]:
    carry_prob = MONSTER_CARRY[ord(monster.monster_type) - ord("A")]
    if carry_prob <= 0 or monster.room == world.proom or see_monst(world, monster):
        return "hero", Coord(world.hero.y, world.hero.x)
    for obj in world.objects:
        if obj.obj_type == SCROLL and obj.which == S_SCARE:
            continue
        if obj.room == monster.room:
            roll = world.rng.rnd(100)
            world.trace.setdefault("find_dest_rolls", []).append({"pos": obj.pos.to_dict(), "roll": roll, "prob": carry_prob})
            if roll < carry_prob and not any(coord_eq(obj.pos, claimed) for claimed in world.claimed_dests):
                return "object", Coord(obj.pos.y, obj.pos.x)
    return "hero", Coord(world.hero.y, world.hero.x)


def source_monsters_report() -> dict[str, Any]:
    return {
        "schema": "gamebench.rogue.source_monsters.v1",
        "randmonster": _randmonster_cases(),
        "new_monster": _new_monster_cases(),
        "runto_find_dest": _runto_cases(),
        "wake_monster": _wake_cases(),
    }


def _randmonster_cases() -> list[dict[str, Any]]:
    return [
        {"seed": 1, **randmonster(RogueRng(1), 1, wander=False)},
        {"seed": 7, **randmonster(RogueRng(7), 12, wander=False)},
        {"seed": -17, **randmonster(RogueRng(-17), 30, wander=False)},
        {"seed": 5, **randmonster(RogueRng(5), 6, wander=True)},
        {"seed": 10, **randmonster(RogueRng(10), 18, wander=True)},
    ]


def _new_monster_cases() -> list[dict[str, Any]]:
    return [
        _new_monster_case("kestrel_level_1", 1, 1, "K", Coord(4, 5), room=0),
        _new_monster_case("dragon_level_30", 7, 30, "D", Coord(7, 8), room=1),
        _new_monster_case("xeroc_disguise", -17, 26, "X", Coord(10, 20), room=2),
        _new_monster_case("aggravate_ring_sets_dest", 3, 12, "C", Coord(3, 4), room=1, left_ring=SourceRing(R_AGGR, 0)),
    ]


def _new_monster_case(
    name: str,
    seed: int,
    level: int,
    monster_type: str,
    pos: Coord,
    *,
    room: int,
    left_ring: SourceRing | None = None,
) -> dict[str, Any]:
    world = SourceMonsterWorld(rng=RogueRng(seed), level=level, max_level=level, hero=Coord(1, 1), proom=0, proom_gold=Coord(2, 2), proom_goldval=0, left_ring=left_ring)
    monster = new_monster(world, monster_type, pos, room=room)
    return {"name": name, "seed": seed, "world": world.to_dict(), "monster": monster.to_dict()}


def _runto_cases() -> list[dict[str, Any]]:
    return [
        _runto_case("same_room_goes_hero", 1, "C", room=0, proom=0, objects=[]),
        _runto_case("carry_object_dest", 7, "C", room=1, proom=0, objects=[SourceObject(FOOD, 0, Coord(6, 7), 1)]),
        _runto_case("scare_scroll_skipped", 7, "C", room=1, proom=0, objects=[SourceObject(SCROLL, S_SCARE, Coord(6, 7), 1), SourceObject(FOOD, 0, Coord(6, 8), 1)]),
        _runto_case("claimed_object_goes_hero", 7, "C", room=1, proom=0, objects=[SourceObject(FOOD, 0, Coord(6, 7), 1)], claimed=[Coord(6, 7)]),
        _runto_case("visible_goes_hero", 7, "C", room=1, proom=0, objects=[SourceObject(FOOD, 0, Coord(6, 7), 1)], hero=Coord(5, 6)),
    ]


def _runto_case(
    name: str,
    seed: int,
    monster_type: str,
    *,
    room: int,
    proom: int,
    objects: list[SourceObject],
    claimed: list[Coord] | None = None,
    hero: Coord | None = None,
) -> dict[str, Any]:
    world = SourceMonsterWorld(
        rng=RogueRng(seed),
        level=12,
        max_level=12,
        hero=hero or Coord(1, 1),
        proom=proom,
        proom_gold=Coord(2, 2),
        proom_goldval=0,
        room_dark={proom: False, room: False},
        objects=objects,
        claimed_dests=claimed or [],
    )
    monster = SourceMonster(monster_type, monster_type, Coord(5, 5), ".", room, "none", None, MONSTER_FLAGS[ord(monster_type) - ord("A")], True, _base_stats(monster_type))
    runto(world, monster)
    return {"name": name, "seed": seed, "world": world.to_dict(), "monster": monster.to_dict()}


def _wake_cases() -> list[dict[str, Any]]:
    return [
        _wake_case("mean_starts_running", 5, "K", MONSTER_FLAGS[ord("K") - ord("A")]),
        _wake_case("mean_roll_zero_stays", 1, "K", MONSTER_FLAGS[ord("K") - ord("A")]),
        _wake_case("stealth_prevents_running", 5, "K", MONSTER_FLAGS[ord("K") - ord("A")], left_ring=SourceRing(R_STEALTH, 0)),
        _wake_case("levitation_prevents_running", 5, "K", MONSTER_FLAGS[ord("K") - ord("A")], player_flags=ISLEVIT),
        _wake_case("medusa_confuses", 5, "M", MONSTER_FLAGS[ord("M") - ord("A")]),
        _wake_case("medusa_save", 10, "M", MONSTER_FLAGS[ord("M") - ord("A")]),
        _wake_case("medusa_dark_room_no_gaze", 5, "M", MONSTER_FLAGS[ord("M") - ord("A")], room_dark=True, pos=Coord(8, 8)),
        _wake_case("greed_guards_gold", 1, "O", MONSTER_FLAGS[ord("O") - ord("A")], proom_goldval=25),
        _wake_case("greed_runs_hero_without_gold", 1, "O", MONSTER_FLAGS[ord("O") - ord("A")], proom_goldval=0),
    ]


def _wake_case(
    name: str,
    seed: int,
    monster_type: str,
    flags: int,
    *,
    left_ring: SourceRing | None = None,
    player_flags: int = 0,
    room_dark: bool = False,
    pos: Coord | None = None,
    proom_goldval: int = 0,
) -> dict[str, Any]:
    world = SourceMonsterWorld(
        rng=RogueRng(seed),
        level=12,
        max_level=12,
        hero=Coord(5, 5),
        proom=0,
        proom_gold=Coord(2, 2),
        proom_goldval=proom_goldval,
        room_dark={0: room_dark},
        player_flags=player_flags,
        left_ring=left_ring,
    )
    monster = SourceMonster(monster_type, monster_type, pos or Coord(5, 6), ".", 0, "none", None, flags, True, _base_stats(monster_type))
    wake_monster(world, monster)
    return {"name": name, "seed": seed, "world": world.to_dict(), "monster": monster.to_dict()}


def _base_stats(monster_type: str) -> SourceMonsterStats:
    index = ord(monster_type) - ord("A")
    return SourceMonsterStats(10, MONSTER_EXP[index], MONSTER_LEVELS[index], MONSTER_ARMOR[index], 1, MONSTER_DAMAGE[index], 1)


def exp_add(level: int, max_hp: int) -> int:
    modifier = max_hp // 8 if level == 1 else max_hp // 6
    if level > 9:
        modifier *= 20
    elif level > 6:
        modifier *= 4
    return modifier


def rnd_thing(rng: RogueRng, level: int) -> str:
    if level >= AMULETLEVEL:
        return RND_THING_LIST[rng.rnd(len(RND_THING_LIST))]
    return RND_THING_LIST[rng.rnd(len(RND_THING_LIST) - 1)]


def save(world: SourceMonsterWorld, which: int, *, player_level: int) -> dict[str, Any]:
    adjusted = which
    if which == VS_MAGIC:
        if world.left_ring is not None and world.left_ring.which == R_PROTECT:
            adjusted -= world.left_ring.arm
        if world.right_ring is not None and world.right_ring.which == R_PROTECT:
            adjusted -= world.right_ring.arm
    need = 14 + adjusted - player_level // 2
    roll = world.rng.roll(1, 20)
    return {"which": adjusted, "original_which": which, "level": player_level, "need": need, "roll": roll, "saved": roll >= need, "rng_seed": world.rng.seed}


def see_monst(world: SourceMonsterWorld, monster: SourceMonster) -> bool:
    if world.player_flags & ISBLIND:
        return False
    if monster.flags & ISINVIS and not (world.player_flags & CANSEE):
        return False
    if dist(monster.pos, world.hero) < LAMPDIST:
        return True
    if monster.room != world.proom:
        return False
    return not world.room_dark.get(monster.room, False)


def is_wearing(world: SourceMonsterWorld, ring_kind: int) -> bool:
    return (world.left_ring is not None and world.left_ring.which == ring_kind) or (world.right_ring is not None and world.right_ring.which == ring_kind)


def dist(first: Coord, second: Coord) -> int:
    return (second.x - first.x) * (second.x - first.x) + (second.y - first.y) * (second.y - first.y)


def coord_eq(first: Coord, second: Coord) -> bool:
    return first.x == second.x and first.y == second.y
