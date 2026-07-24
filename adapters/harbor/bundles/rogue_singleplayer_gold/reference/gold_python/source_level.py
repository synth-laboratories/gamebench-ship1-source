"""Source-faithful Rogue level-generation slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_rogue import (
    AMULET,
    AMULETLEVEL,
    ARMOR,
    DOOR,
    FOOD,
    FLOOR,
    GOLD,
    MAXOBJ,
    MAXPASS,
    MAXROOMS,
    MAXTRAPS,
    NUMCOLS,
    NUMLINES,
    PASSAGE,
    POTION,
    RING,
    SCROLL,
    STAIRS,
    STICK,
    WEAPON,
    RogueRng,
    step_ok,
)


ISDARK = 0o000001
ISGONE = 0o000002
ISMAZE = 0o000004

ISCURSED = 0o000001
ISMISL = 0o000004
ISMANY = 0o000010

F_PASS = 0x80
F_SEEN = 0x40
F_REAL = 0x10
F_PNUM = 0x0F

GOLDGRP = 1
TREAS_ROOM = 20
MAXTREAS = 10
MINTREAS = 2
MAXTRIES = 10
NTRAPS = 8

MAXPOTIONS = 14
MAXSCROLLS = 18
MAXWEAPONS = 9
MAXARMORS = 8
MAXRINGS = 14
MAXSTICKS = 14

ISGREED = 0o000040
ISHASTE = 0o000100
ISINVIS = 0o002000
ISMEAN = 0o004000
ISREGEN = 0o010000
ISFLY = 0o040000

R_PROTECT = 0
R_ADDSTR = 1
R_AGGR = 6
R_ADDHIT = 7
R_ADDDAM = 8
R_TELEPORT = 11
WS_LIGHT = 0
DAGGER = 4

LVL_MONS = list("KEBSHIROZLCQANYFTWPXUMVGJD")
MONSTER_CARRY = [0, 0, 15, 100, 0, 0, 20, 0, 0, 70, 0, 0, 40, 100, 15, 0, 0, 0, 0, 50, 0, 20, 0, 30, 30, 0]
MONSTER_LEVELS = [5, 1, 4, 10, 1, 8, 13, 1, 1, 15, 1, 3, 8, 3, 1, 8, 3, 2, 1, 6, 7, 8, 5, 7, 4, 2]
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
THING_PROBS = [26, 36, 16, 7, 7, 4, 4]
ARMOR_PROBS = [20, 15, 15, 13, 12, 10, 10, 5]
POTION_PROBS = [7, 8, 8, 13, 3, 13, 6, 6, 2, 5, 5, 13, 5, 6]
RING_PROBS = [9, 9, 5, 10, 10, 1, 10, 8, 8, 4, 9, 5, 7, 5]
SCROLL_PROBS = [7, 4, 2, 3, 7, 10, 10, 6, 7, 10, 3, 2, 5, 8, 4, 7, 3, 2]
WEAPON_PROBS = [11, 11, 12, 12, 8, 10, 12, 12, 12]
STICK_PROBS = [12, 6, 3, 3, 3, 15, 10, 10, 11, 9, 1, 6, 6, 5]
A_CLASS = [8, 7, 7, 6, 5, 4, 4, 3]
INIT_WEAPON_FLAGS = [0, 0, 0, ISMANY | ISMISL, ISMISL | ISMISL, 0, ISMANY | ISMISL, ISMANY | ISMISL, ISMISL]
RND_THING_LIST = [POTION, SCROLL, RING, STICK, FOOD, WEAPON, ARMOR, STAIRS, GOLD, AMULET]


@dataclass
class Coord:
    y: int = 0
    x: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"y": self.y, "x": self.x}


@dataclass
class Room:
    pos: Coord = field(default_factory=Coord)
    max: Coord = field(default_factory=Coord)
    gold: Coord = field(default_factory=Coord)
    goldval: int = 0
    flags: int = 0
    exits: list[Coord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pos": self.pos.to_dict(),
            "max": self.max.to_dict(),
            "gold": self.gold.to_dict(),
            "goldval": self.goldval,
            "flags": self.flags,
            "nexits": len(self.exits),
            "exits": [coord.to_dict() for coord in self.exits],
        }


@dataclass
class Place:
    ch: str = " "
    flags: int = F_REAL
    monst: bool = False


@dataclass
class SourceObject:
    obj_type: str
    which: int = 0
    pos: Coord = field(default_factory=Coord)
    count: int = 1
    hplus: int = 0
    dplus: int = 0
    arm: int = 11
    flags: int = 0
    group: int = 0
    goldval: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.obj_type,
            "which": self.which,
            "pos": self.pos.to_dict(),
            "count": self.count,
            "hplus": self.hplus,
            "dplus": self.dplus,
            "arm": self.arm,
            "flags": self.flags,
            "group": self.group,
            "goldval": self.goldval,
        }


@dataclass
class SourceMonster:
    monster_type: str
    pos: Coord
    level: int
    hp: int
    disguise: str
    flags: int
    pack: list[SourceObject] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.monster_type,
            "pos": self.pos.to_dict(),
            "level": self.level,
            "hp": self.hp,
            "disguise": self.disguise,
            "flags": self.flags,
            "pack": [item.to_dict() for item in self.pack],
        }


@dataclass
class SourceTrap:
    pos: Coord
    kind: int

    def to_dict(self) -> dict[str, Any]:
        return {"pos": self.pos.to_dict(), "kind": self.kind}


@dataclass
class SourceLevelDraft:
    level: int
    max_level: int
    amulet: bool
    rooms: list[Room]
    places: list[list[Place]]
    gold_positions: dict[str, int]
    monster_slots: list[Coord]
    monsters: list[SourceMonster]
    level_objects: list[SourceObject]
    traps: list[SourceTrap]
    stairs: Coord
    hero: Coord
    ntraps: int
    no_food: int
    rng_seed: int
    passages: list[Room] = field(default_factory=list)
    hidden_passages: list[Coord] = field(default_factory=list)
    passage_numbers: dict[str, int] = field(default_factory=dict)
    source_map_cells: list[dict[str, Any]] = field(default_factory=list)

    def rows(self) -> list[str]:
        return ["".join(place.ch for place in row) for row in self.places[:NUMLINES]]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "level": self.level,
            "max_level": self.max_level,
            "amulet": self.amulet,
            "rooms": [room.to_dict() for room in self.rooms],
            "rows": self.rows(),
            "gold_positions": dict(sorted(self.gold_positions.items())),
            "monster_slots": [coord.to_dict() for coord in self.monster_slots],
            "monsters": [monster.to_dict() for monster in self.monsters],
            "level_objects": [obj.to_dict() for obj in self.level_objects],
            "traps": [trap.to_dict() for trap in self.traps],
            "stairs": self.stairs.to_dict(),
            "hero": self.hero.to_dict(),
            "ntraps": self.ntraps,
            "no_food": self.no_food,
            "rng_seed": self.rng_seed,
        }
        if self.passages:
            payload["passages"] = [passage.to_dict() for passage in self.passages]
            payload["hidden_passages"] = [coord.to_dict() for coord in self.hidden_passages]
            payload["passage_numbers"] = dict(sorted(self.passage_numbers.items()))
        return payload


def generate_room_slice(seed: int, *, level: int = 1, max_level: int = 1, amulet: bool = False) -> SourceLevelDraft:
    builder = _RoomBuilder(seed=seed, level=level, max_level=max_level, amulet=amulet)
    return builder.do_rooms()


def generate_passage_slice(seed: int, *, level: int = 1, max_level: int = 1, amulet: bool = False) -> SourceLevelDraft:
    builder = _RoomBuilder(seed=seed, level=level, max_level=max_level, amulet=amulet)
    builder.do_rooms()
    builder.do_passages()
    return builder.to_draft(include_passages=True)


def generate_new_level_slice(seed: int, *, level: int = 1, max_level: int = 1, amulet: bool = False) -> SourceLevelDraft:
    builder = _RoomBuilder(seed=seed, level=level, max_level=max_level, amulet=amulet)
    builder.do_rooms()
    builder.do_passages()
    builder.no_food += 1
    builder.put_things()
    builder.place_traps()
    builder.place_stairs()
    builder.assign_monster_rooms()
    builder.place_hero()
    return builder.to_draft(include_passages=True)


class _RoomBuilder:
    def __init__(self, *, seed: int, level: int, max_level: int, amulet: bool) -> None:
        self.rng = RogueRng(seed)
        self.level = level
        self.max_level = max_level
        self.amulet = amulet
        self.rooms = [Room() for _ in range(MAXROOMS)]
        self.places = [[Place() for _ in range(NUMCOLS)] for _ in range(NUMLINES)]
        self.gold_positions: dict[str, int] = {}
        self.monster_slots: list[Coord] = []
        self.monsters: list[SourceMonster] = []
        self.level_objects: list[SourceObject] = []
        self.traps: list[SourceTrap] = []
        self.stairs = Coord()
        self.hero = Coord()
        self.ntraps = 0
        self.passages = [Room() for _ in range(MAXPASS)]
        self.no_food = 0
        self.weapon_group = 2
        self._maze_maxy = 0
        self._maze_maxx = 0
        self._maze_starty = 0
        self._maze_startx = 0
        self._pnum = 0
        self._newpnum = False

    def do_rooms(self) -> SourceLevelDraft:
        bsze = Coord(y=NUMLINES // 3, x=NUMCOLS // 3)
        for room in self.rooms:
            room.goldval = 0
            room.exits = []
            room.flags = 0
        left_out = self.rng.rnd(4)
        for _ in range(left_out):
            self.rooms[self.rnd_room()].flags |= ISGONE
        for index, room in enumerate(self.rooms):
            top = Coord(y=(index // 3) * bsze.y, x=(index % 3) * bsze.x + 1)
            if room.flags & ISGONE:
                while True:
                    room.pos.x = top.x + self.rng.rnd(bsze.x - 2) + 1
                    room.pos.y = top.y + self.rng.rnd(bsze.y - 2) + 1
                    room.max.x = -NUMCOLS
                    room.max.y = -NUMLINES
                    if room.pos.y > 0 and room.pos.y < NUMLINES - 1:
                        break
                continue
            if self.rng.rnd(10) < self.level - 1:
                room.flags |= ISDARK
                if self.rng.rnd(15) == 0:
                    room.flags = ISMAZE
            if room.flags & ISMAZE:
                room.max.x = bsze.x - 1
                room.max.y = bsze.y - 1
                room.pos.x = top.x
                if room.pos.x == 1:
                    room.pos.x = 0
                room.pos.y = top.y
                if room.pos.y == 0:
                    room.pos.y += 1
                    room.max.y -= 1
            else:
                while True:
                    room.max.x = self.rng.rnd(bsze.x - 4) + 4
                    room.max.y = self.rng.rnd(bsze.y - 4) + 4
                    room.pos.x = top.x + self.rng.rnd(bsze.x - room.max.x)
                    room.pos.y = top.y + self.rng.rnd(bsze.y - room.max.y)
                    if room.pos.y != 0:
                        break
            self.draw_room(index)
            if self.rng.rnd(2) == 0 and (not self.amulet or self.level >= self.max_level):
                room.goldval = self.rng.gold_calc(self.level)
                gold = self.find_floor(index, limit=0, monst=False)
                room.gold = gold
                self.set_ch(gold.y, gold.x, GOLD)
                self.gold_positions[f"{gold.y},{gold.x}"] = room.goldval
                gold_object = self.new_item()
                gold_object.goldval = room.goldval
                gold_object.pos = Coord(y=gold.y, x=gold.x)
                gold_object.flags = ISMANY
                gold_object.group = GOLDGRP
                gold_object.obj_type = GOLD
                self.attach_object(gold_object)
            if self.rng.rnd(100) < (80 if room.goldval > 0 else 25):
                monster_slot = self.find_floor(index, limit=0, monst=True)
                self.place(monster_slot.y, monster_slot.x).monst = True
                self.monster_slots.append(monster_slot)
                monster = self.new_monster(self.randmonster(wander=False), monster_slot)
                self.give_pack(monster)
                self.monsters.insert(0, monster)
        return self.to_draft(include_passages=False)

    def to_draft(self, *, include_passages: bool) -> SourceLevelDraft:
        hidden_passages = []
        passage_numbers = {}
        source_map_cells = []
        if include_passages:
            for y, row in enumerate(self.places):
                for x, place in enumerate(row):
                    if not (place.flags & F_REAL) and place.ch in {"|", "-", " "}:
                        source_map_cells.append({"id": f"cell{len(source_map_cells)}", "row": y, "col": x, "ch": place.ch, "flags": place.flags})
                    if place.flags & F_PASS and place.ch != PASSAGE:
                        hidden_passages.append(Coord(y=y, x=x))
                    pnum = place.flags & F_PNUM
                    if pnum:
                        passage_numbers[f"{y},{x}"] = pnum
        return SourceLevelDraft(
            level=self.level,
            max_level=self.max_level,
            amulet=self.amulet,
            rooms=self.rooms,
            places=self.places,
            gold_positions=self.gold_positions,
            monster_slots=self.monster_slots,
            monsters=self.monsters,
            level_objects=self.level_objects,
            traps=self.traps,
            stairs=self.stairs,
            hero=self.hero,
            ntraps=self.ntraps,
            no_food=self.no_food,
            rng_seed=self.rng.seed,
            passages=self.passages if include_passages else [],
            hidden_passages=hidden_passages,
            passage_numbers=passage_numbers,
            source_map_cells=source_map_cells,
        )

    def put_things(self) -> None:
        if self.amulet and self.level < self.max_level:
            return
        if self.rng.rnd(TREAS_ROOM) == 0:
            self.treas_room()
        for _ in range(MAXOBJ):
            if self.rng.rnd(100) < 36:
                obj = self.new_thing()
                self.attach_object(obj)
                obj.pos = self.find_floor(None, limit=0, monst=False)
                self.set_ch(obj.pos.y, obj.pos.x, obj.obj_type)
        if self.level >= AMULETLEVEL and not self.amulet:
            obj = self.new_item()
            self.attach_object(obj)
            obj.hplus = 0
            obj.dplus = 0
            obj.arm = 11
            obj.obj_type = AMULET
            obj.pos = self.find_floor(None, limit=0, monst=False)
            self.set_ch(obj.pos.y, obj.pos.x, AMULET)

    def treas_room(self) -> None:
        room_index = self.rnd_room()
        room = self.rooms[room_index]
        spots = (room.max.y - 2) * (room.max.x - 2) - MINTREAS
        if spots > MAXTREAS - MINTREAS:
            spots = MAXTREAS - MINTREAS
        num_monst = self.rng.rnd(spots) + MINTREAS
        for _ in range(num_monst):
            coord = self.find_floor(room_index, limit=2 * MAXTRIES, monst=False)
            obj = self.new_thing()
            obj.pos = coord
            self.attach_object(obj)
            self.set_ch(coord.y, coord.x, obj.obj_type)
        monster_count = self.rng.rnd(spots) + MINTREAS
        if monster_count < num_monst + 2:
            monster_count = num_monst + 2
        spots = (room.max.y - 2) * (room.max.x - 2)
        if monster_count > spots:
            monster_count = spots
        self.level += 1
        try:
            for _ in range(monster_count):
                coord = self.try_find_floor(room_index, limit=MAXTRIES, monst=True)
                if coord is None:
                    continue
                self.place(coord.y, coord.x).monst = True
                self.monster_slots.append(coord)
                monster = self.new_monster(self.randmonster(wander=False), coord)
                monster.flags |= ISMEAN
                self.give_pack(monster)
                self.monsters.insert(0, monster)
        finally:
            self.level -= 1

    def place_traps(self) -> None:
        if self.rng.rnd(10) >= self.level:
            return
        self.ntraps = self.rng.rnd(self.level // 4) + 1
        if self.ntraps > MAXTRAPS:
            self.ntraps = MAXTRAPS
        for _ in range(self.ntraps):
            while True:
                coord = self.find_floor(None, limit=0, monst=False)
                if self.place(coord.y, coord.x).ch == FLOOR:
                    break
            place = self.place(coord.y, coord.x)
            place.flags &= ~F_REAL
            trap_kind = self.rng.rnd(NTRAPS)
            place.flags |= trap_kind
            self.traps.append(SourceTrap(pos=coord, kind=trap_kind))

    def place_stairs(self) -> None:
        self.stairs = self.find_floor(None, limit=0, monst=False)
        self.set_ch(self.stairs.y, self.stairs.x, STAIRS)

    def assign_monster_rooms(self) -> None:
        pass

    def place_hero(self) -> None:
        self.hero = self.find_floor(None, limit=0, monst=True)

    def do_passages(self) -> None:
        connections = [
            [False, True, False, True, False, False, False, False, False],
            [True, False, True, False, True, False, False, False, False],
            [False, True, False, False, False, True, False, False, False],
            [True, False, False, False, True, False, True, False, False],
            [False, True, False, True, False, True, False, True, False],
            [False, False, True, False, True, False, False, False, True],
            [False, False, False, True, False, False, False, True, False],
            [False, False, False, False, True, False, True, False, True],
            [False, False, False, False, False, True, False, True, False],
        ]
        isconn = [[False for _ in range(MAXROOMS)] for _ in range(MAXROOMS)]
        ingraph = [False for _ in range(MAXROOMS)]
        roomcount = 1
        r1 = self.rng.rnd(MAXROOMS)
        ingraph[r1] = True
        while roomcount < MAXROOMS:
            count = 0
            r2 = 0
            for index in range(MAXROOMS):
                if connections[r1][index] and not ingraph[index]:
                    count += 1
                    if self.rng.rnd(count) == 0:
                        r2 = index
            if count == 0:
                while True:
                    r1 = self.rng.rnd(MAXROOMS)
                    if ingraph[r1]:
                        break
            else:
                ingraph[r2] = True
                self.conn(r1, r2)
                isconn[r1][r2] = True
                isconn[r2][r1] = True
                roomcount += 1
        for _ in range(self.rng.rnd(5), 0, -1):
            r1 = self.rng.rnd(MAXROOMS)
            count = 0
            r2 = 0
            for index in range(MAXROOMS):
                if connections[r1][index] and not isconn[r1][index]:
                    count += 1
                    if self.rng.rnd(count) == 0:
                        r2 = index
            if count != 0:
                self.conn(r1, r2)
                isconn[r1][r2] = True
                isconn[r2][r1] = True
        self.passnum()

    def conn(self, r1: int, r2: int) -> None:
        if r1 < r2:
            room_index = r1
            direc = "r" if r1 + 1 == r2 else "d"
        else:
            room_index = r2
            direc = "r" if r2 + 1 == r1 else "d"
        source = self.rooms[room_index]
        if direc == "d":
            target_index = room_index + 3
            target = self.rooms[target_index]
            delta = Coord(y=1, x=0)
            start = Coord(y=source.pos.y, x=source.pos.x)
            end = Coord(y=target.pos.y, x=target.pos.x)
            if not (source.flags & ISGONE):
                while True:
                    start.x = source.pos.x + self.rng.rnd(source.max.x - 2) + 1
                    start.y = source.pos.y + source.max.y - 1
                    if not (source.flags & ISMAZE) or self.flags(start.y, start.x) & F_PASS:
                        break
            if not (target.flags & ISGONE):
                while True:
                    end.x = target.pos.x + self.rng.rnd(target.max.x - 2) + 1
                    if not (target.flags & ISMAZE) or self.flags(end.y, end.x) & F_PASS:
                        break
            distance = abs(start.y - end.y) - 1
            turn_delta = Coord(y=0, x=1 if start.x < end.x else -1)
            turn_distance = abs(start.x - end.x)
        else:
            target_index = room_index + 1
            target = self.rooms[target_index]
            delta = Coord(y=0, x=1)
            start = Coord(y=source.pos.y, x=source.pos.x)
            end = Coord(y=target.pos.y, x=target.pos.x)
            if not (source.flags & ISGONE):
                while True:
                    start.x = source.pos.x + source.max.x - 1
                    start.y = source.pos.y + self.rng.rnd(source.max.y - 2) + 1
                    if not (source.flags & ISMAZE) or self.flags(start.y, start.x) & F_PASS:
                        break
            if not (target.flags & ISGONE):
                while True:
                    end.y = target.pos.y + self.rng.rnd(target.max.y - 2) + 1
                    if not (target.flags & ISMAZE) or self.flags(end.y, end.x) & F_PASS:
                        break
            distance = abs(start.x - end.x) - 1
            turn_delta = Coord(y=1 if start.y < end.y else -1, x=0)
            turn_distance = abs(start.y - end.y)
        turn_spot = self.rng.rnd(distance - 1) + 1
        if not (source.flags & ISGONE):
            self.door(room_index, start)
        else:
            self.putpass(start)
        if not (target.flags & ISGONE):
            self.door(target_index, end)
        else:
            self.putpass(end)
        curr = Coord(y=start.y, x=start.x)
        while distance > 0:
            curr.x += delta.x
            curr.y += delta.y
            if distance == turn_spot:
                while turn_distance > 0:
                    self.putpass(curr)
                    curr.x += turn_delta.x
                    curr.y += turn_delta.y
                    turn_distance -= 1
            self.putpass(curr)
            distance -= 1

    def door(self, room_index: int, coord: Coord) -> None:
        room = self.rooms[room_index]
        room.exits.append(Coord(y=coord.y, x=coord.x))
        if room.flags & ISMAZE:
            return
        place = self.place(coord.y, coord.x)
        if self.rng.rnd(10) + 1 < self.level and self.rng.rnd(5) == 0:
            if coord.y == room.pos.y or coord.y == room.pos.y + room.max.y - 1:
                place.ch = "-"
            else:
                place.ch = "|"
            place.flags &= ~F_REAL
        else:
            place.ch = DOOR

    def passnum(self) -> None:
        self._pnum = 0
        self._newpnum = False
        for passage in self.passages:
            passage.exits = []
        for room in self.rooms:
            for exit_coord in room.exits:
                self._newpnum = True
                self.numpass(exit_coord.y, exit_coord.x)

    def numpass(self, y: int, x: int) -> None:
        if x >= NUMCOLS or x < 0 or y >= NUMLINES or y <= 0:
            return
        place = self.place(y, x)
        if place.flags & F_PNUM:
            return
        if self._newpnum:
            self._pnum += 1
            self._newpnum = False
        if place.ch == DOOR or (not (place.flags & F_REAL) and place.ch in {"|", "-"}):
            self.passages[self._pnum].exits.append(Coord(y=y, x=x))
        elif not (place.flags & F_PASS):
            return
        place.flags |= self._pnum
        self.numpass(y + 1, x)
        self.numpass(y - 1, x)
        self.numpass(y, x + 1)
        self.numpass(y, x - 1)

    def randmonster(self, *, wander: bool) -> str:
        if wander:
            raise NotImplementedError("wandering monster table is not needed for this source slice")
        while True:
            monster_index = self.level + (self.rng.rnd(10) - 6)
            if monster_index < 0:
                monster_index = self.rng.rnd(5)
            if monster_index > 25:
                monster_index = self.rng.rnd(5) + 21
            monster = LVL_MONS[monster_index]
            if monster != "\0":
                return monster

    def new_monster(self, monster_type: str, pos: Coord) -> SourceMonster:
        lev_add = max(self.level - 26, 0)
        monster_index = ord(monster_type) - ord("A")
        monster_level = MONSTER_LEVELS[monster_index] + lev_add
        hp = self.rng.roll(monster_level, 8)
        disguise = self.rnd_thing() if monster_type == "X" else monster_type
        flags = MONSTER_FLAGS[monster_index]
        if self.level > 29:
            flags |= ISHASTE
        return SourceMonster(monster_type=monster_type, pos=Coord(y=pos.y, x=pos.x), level=monster_level, hp=hp, disguise=disguise, flags=flags)

    def give_pack(self, monster: SourceMonster) -> None:
        monster_index = ord(monster.monster_type) - ord("A")
        if self.level >= self.max_level and self.rng.rnd(100) < MONSTER_CARRY[monster_index]:
            monster.pack.insert(0, self.new_thing())

    def rnd_thing(self) -> str:
        if self.level >= 26:
            return RND_THING_LIST[self.rng.rnd(len(RND_THING_LIST))]
        return RND_THING_LIST[self.rng.rnd(len(RND_THING_LIST) - 1)]

    def new_thing(self) -> SourceObject:
        obj = self.new_item()
        obj.hplus = 0
        obj.dplus = 0
        obj.arm = 11
        obj.count = 1
        obj.group = 0
        obj.flags = 0
        object_kind = 2 if self.no_food > 3 else self.pick_one(THING_PROBS)
        if object_kind == 0:
            obj.obj_type = POTION
            obj.which = self.pick_one(POTION_PROBS)
        elif object_kind == 1:
            obj.obj_type = SCROLL
            obj.which = self.pick_one(SCROLL_PROBS)
        elif object_kind == 2:
            obj.obj_type = FOOD
            self.no_food = 0
            obj.which = 0 if self.rng.rnd(10) != 0 else 1
        elif object_kind == 3:
            self.init_weapon(obj, self.pick_one(WEAPON_PROBS))
            roll = self.rng.rnd(100)
            if roll < 10:
                obj.flags |= ISCURSED
                obj.hplus -= self.rng.rnd(3) + 1
            elif roll < 15:
                obj.hplus += self.rng.rnd(3) + 1
        elif object_kind == 4:
            obj.obj_type = ARMOR
            obj.which = self.pick_one(ARMOR_PROBS)
            obj.arm = A_CLASS[obj.which]
            roll = self.rng.rnd(100)
            if roll < 20:
                obj.flags |= ISCURSED
                obj.arm += self.rng.rnd(3) + 1
            elif roll < 28:
                obj.arm -= self.rng.rnd(3) + 1
        elif object_kind == 5:
            obj.obj_type = RING
            obj.which = self.pick_one(RING_PROBS)
            if obj.which in {R_ADDSTR, R_PROTECT, R_ADDHIT, R_ADDDAM}:
                obj.arm = self.rng.rnd(3)
                if obj.arm == 0:
                    obj.arm = -1
                    obj.flags |= ISCURSED
            elif obj.which in {R_AGGR, R_TELEPORT}:
                obj.flags |= ISCURSED
        elif object_kind == 6:
            obj.obj_type = STICK
            obj.which = self.pick_one(STICK_PROBS)
            obj.arm = self.rng.rnd(10) + 10 if obj.which == WS_LIGHT else self.rng.rnd(5) + 3
        else:
            raise RuntimeError(f"unknown Rogue object kind {object_kind}")
        return obj

    def new_item(self) -> SourceObject:
        return SourceObject(obj_type="", count=0, arm=0)

    def attach_object(self, obj: SourceObject) -> None:
        self.level_objects.insert(0, obj)

    def pick_one(self, probabilities: list[int]) -> int:
        value = self.rng.rnd(100)
        for index, probability in enumerate(probabilities):
            if value < probability:
                return index
        return 0

    def init_weapon(self, obj: SourceObject, which: int) -> None:
        obj.obj_type = WEAPON
        obj.which = which
        obj.flags = INIT_WEAPON_FLAGS[which]
        obj.hplus = 0
        obj.dplus = 0
        if which == DAGGER:
            obj.count = self.rng.rnd(4) + 2
            obj.group = self.weapon_group
            self.weapon_group += 1
        elif obj.flags & ISMANY:
            obj.count = self.rng.rnd(8) + 8
            obj.group = self.weapon_group
            self.weapon_group += 1
        else:
            obj.count = 1
            obj.group = 0

    def rnd_room(self) -> int:
        while True:
            room_index = self.rng.rnd(MAXROOMS)
            if not (self.rooms[room_index].flags & ISGONE):
                return room_index

    def draw_room(self, room_index: int) -> None:
        room = self.rooms[room_index]
        if room.flags & ISMAZE:
            self.do_maze(room_index)
            return
        self.vert(room_index, room.pos.x)
        self.vert(room_index, room.pos.x + room.max.x - 1)
        self.horiz(room_index, room.pos.y)
        self.horiz(room_index, room.pos.y + room.max.y - 1)
        for y in range(room.pos.y + 1, room.pos.y + room.max.y - 1):
            for x in range(room.pos.x + 1, room.pos.x + room.max.x - 1):
                self.set_ch(y, x, FLOOR)

    def vert(self, room_index: int, startx: int) -> None:
        room = self.rooms[room_index]
        for y in range(room.pos.y + 1, room.max.y + room.pos.y):
            self.set_ch(y, startx, "|")

    def horiz(self, room_index: int, starty: int) -> None:
        room = self.rooms[room_index]
        for x in range(room.pos.x, room.pos.x + room.max.x):
            self.set_ch(starty, x, "-")

    def do_maze(self, room_index: int) -> None:
        room = self.rooms[room_index]
        self._maze_maxy = room.max.y
        self._maze_maxx = room.max.x
        self._maze_starty = room.pos.y
        self._maze_startx = room.pos.x
        starty = (self.rng.rnd(room.max.y) // 2) * 2
        startx = (self.rng.rnd(room.max.x) // 2) * 2
        self.putpass(Coord(y=starty + self._maze_starty, x=startx + self._maze_startx))
        self.dig(starty, startx)

    def dig(self, y: int, x: int) -> None:
        deltas = [Coord(y=2, x=0), Coord(y=-2, x=0), Coord(y=0, x=2), Coord(y=0, x=-2)]
        while True:
            count = 0
            nexty = 0
            nextx = 0
            for delta in deltas:
                newy = y + delta.y
                newx = x + delta.x
                if newy < 0 or newy > self._maze_maxy or newx < 0 or newx > self._maze_maxx:
                    continue
                if self.flags(newy + self._maze_starty, newx + self._maze_startx) & F_PASS:
                    continue
                count += 1
                if self.rng.rnd(count) == 0:
                    nexty = newy
                    nextx = newx
            if count == 0:
                return
            if nexty == y:
                mid = Coord(y=y + self._maze_starty, x=nextx + self._maze_startx + (1 if nextx - x < 0 else -1))
            else:
                mid = Coord(y=nexty + self._maze_starty + (1 if nexty - y < 0 else -1), x=x + self._maze_startx)
            self.putpass(mid)
            self.putpass(Coord(y=nexty + self._maze_starty, x=nextx + self._maze_startx))
            self.dig(nexty, nextx)

    def putpass(self, coord: Coord) -> None:
        place = self.place(coord.y, coord.x)
        place.flags |= F_PASS
        if self.rng.rnd(10) + 1 < self.level and self.rng.rnd(40) == 0:
            place.flags &= ~F_REAL
        else:
            place.ch = PASSAGE

    def rnd_pos(self, room_index: int) -> Coord:
        room = self.rooms[room_index]
        x = room.pos.x + self.rng.rnd(room.max.x - 2) + 1
        y = room.pos.y + self.rng.rnd(room.max.y - 2) + 1
        return Coord(y=y, x=x)

    def find_floor(self, room_index: int | None, *, limit: int, monst: bool) -> Coord:
        coord = self.try_find_floor(room_index, limit=limit, monst=monst)
        if coord is None:
            raise RuntimeError("Rogue find_floor limit exhausted")
        return coord

    def try_find_floor(self, room_index: int | None, *, limit: int, monst: bool) -> Coord | None:
        pickroom = room_index is None
        count = limit
        compchar = ""
        if room_index is not None:
            compchar = PASSAGE if self.rooms[room_index].flags & ISMAZE else FLOOR
        while True:
            if limit and count == 0:
                return None
            if limit:
                count -= 1
            if pickroom:
                room_index = self.rnd_room()
                compchar = PASSAGE if self.rooms[room_index].flags & ISMAZE else FLOOR
            assert room_index is not None
            coord = self.rnd_pos(room_index)
            place = self.place(coord.y, coord.x)
            if monst:
                if not place.monst and step_ok(place.ch):
                    return coord
            elif place.ch == compchar:
                return coord

    def place(self, y: int, x: int) -> Place:
        return self.places[y][x]

    def flags(self, y: int, x: int) -> int:
        return self.place(y, x).flags

    def set_ch(self, y: int, x: int, ch: str) -> None:
        self.place(y, x).ch = ch
