"""Source-faithful Rogue do_chase branch slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_rogue import DOOR, FLOOR, PASSAGE, RogueRng


ISGONE = 0o000002
ISCANC = 0o000010
ISGREED = 0o000040
ISTARGET = 0o000200
ISRUN = 0o020000

BOLT_LENGTH = 6
DRAGONSHOT = 5


@dataclass
class Coord:
    y: int
    x: int

    def to_dict(self) -> dict[str, int]:
        return {"y": self.y, "x": self.x}


@dataclass
class ChaseRoom:
    index: int
    goldval: int = 0
    flags: int = 0
    exits: list[Coord] = field(default_factory=list)


@dataclass
class ChaseObject:
    obj_type: str
    pos: Coord

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.obj_type, "pos": self.pos.to_dict()}


@dataclass
class ChaseMonster:
    monster_type: str
    pos: Coord
    room: int
    flags: int
    dest_kind: str
    dest_pos: Coord
    pack: list[ChaseObject] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.monster_type,
            "pos": self.pos.to_dict(),
            "room": self.room,
            "flags": self.flags,
            "dest": self.dest_kind,
            "dest_pos": self.dest_pos.to_dict(),
            "pack": [obj.to_dict() for obj in self.pack],
        }


@dataclass
class DoChaseWorld:
    rng: RogueRng
    hero: Coord
    proom: int
    rooms: dict[int, ChaseRoom]
    passages: dict[int, ChaseRoom]
    objects: list[ChaseObject] = field(default_factory=list)
    terrain: dict[tuple[int, int], str] = field(default_factory=dict)
    dest_room: int = 0
    passage_index: int = 0
    chase_keep: bool = True
    chase_pos: Coord = field(default_factory=lambda: Coord(0, 0))
    chase_room: int = 0
    attack_return: int = 0
    find_dest_kind: str = "hero"
    find_dest_pos: Coord = field(default_factory=lambda: Coord(0, 0))
    running: bool = True
    count: int = 1
    quiet: int = 3
    has_hit: bool = False
    to_death: bool = False
    kamikaze: bool = False
    markers: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rng_seed": self.rng.seed,
            "hero": self.hero.to_dict(),
            "proom": self.proom,
            "objects": [obj.to_dict() for obj in self.objects],
            "terrain": [{"y": y, "x": x, "ch": ch} for (y, x), ch in sorted(self.terrain.items())],
            "running": self.running,
            "count": self.count,
            "quiet": self.quiet,
            "has_hit": self.has_hit,
            "to_death": self.to_death,
            "kamikaze": self.kamikaze,
            "markers": self.markers,
            "trace": self.trace,
        }


def do_chase(world: DoChaseWorld, monster: ChaseMonster) -> int:
    rer = world.rooms[monster.room]
    if monster.flags & ISGREED and rer.goldval == 0:
        monster.dest_kind = "hero"
        monster.dest_pos = Coord(world.hero.y, world.hero.x)
        world.trace["greed_dest_reset"] = True
    ree_index = world.proom if monster.dest_kind == "hero" else world.dest_room
    door = world.terrain.get((monster.pos.y, monster.pos.x), FLOOR) == DOOR
    target = Coord(monster.dest_pos.y, monster.dest_pos.x)
    mindist = 32767
    route_checks: list[dict[str, Any]] = []

    while rer.index != ree_index:
        for exit_coord in rer.exits:
            curdist = dist(monster.dest_pos, exit_coord)
            check = {"room": rer.index, "exit": exit_coord.to_dict(), "dist": curdist}
            if curdist < mindist:
                target = Coord(exit_coord.y, exit_coord.x)
                mindist = curdist
                check["chosen"] = True
            route_checks.append(check)
        if door:
            rer = world.passages[world.passage_index]
            door = False
            continue
        break
    else:
        target = Coord(monster.dest_pos.y, monster.dest_pos.x)
        world.trace["target"] = target.to_dict()
        if _dragon_flame(world, monster):
            return 0

    world.trace["route_checks"] = route_checks
    world.trace["target"] = target.to_dict()

    if not world.chase_keep:
        if coord_eq(target, world.hero):
            world.markers.append("attack")
            return world.attack_return
        if coord_eq(target, monster.dest_pos):
            for index, obj in enumerate(list(world.objects)):
                if coord_eq(obj.pos, monster.dest_pos):
                    world.objects.pop(index)
                    monster.pack.insert(0, obj)
                    world.terrain[(obj.pos.y, obj.pos.x)] = PASSAGE if world.rooms[monster.room].flags & ISGONE else FLOOR
                    monster.dest_kind = world.find_dest_kind
                    monster.dest_pos = Coord(world.find_dest_pos.y, world.find_dest_pos.x)
                    world.markers.append("pickup_object")
                    break
            stoprun = monster.monster_type != "F"
        else:
            stoprun = False
    elif monster.monster_type == "F":
        return 0
    else:
        stoprun = False

    if not coord_eq(world.chase_pos, monster.pos):
        monster.pos = Coord(world.chase_pos.y, world.chase_pos.x)
        monster.room = world.chase_room
        world.markers.append("relocate")
    if stoprun and coord_eq(monster.pos, monster.dest_pos):
        monster.flags &= ~ISRUN
    return 0


def source_do_chase_report() -> dict[str, Any]:
    return {
        "schema": "gamebench.rogue.source_do_chase.v1",
        "cases": [_run_case(case) for case in _cases()],
    }


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    world = _world(case)
    monster = ChaseMonster(
        monster_type=case.get("type", "K"),
        pos=Coord(*case.get("pos", [5, 5])),
        room=case.get("room", 0),
        flags=case.get("flags", ISRUN),
        dest_kind=case.get("dest", "hero"),
        dest_pos=Coord(*case.get("dest_pos", [10, 10])),
    )
    returned = do_chase(world, monster)
    return {"name": case["name"], "seed": case["seed"], "returned": returned, "monster": monster.to_dict(), "world": world.to_dict()}


def _world(case: dict[str, Any]) -> DoChaseWorld:
    rooms = {
        0: ChaseRoom(0, case.get("room_goldval", 1), case.get("room_flags", 0), [Coord(2, 2), Coord(6, 6)]),
        1: ChaseRoom(1, 0, 0, [Coord(10, 10)]),
        2: ChaseRoom(2, 0, 0, [Coord(4, 4)]),
    }
    passages = {9: ChaseRoom(9, 0, ISGONE, [Coord(3, 8), Coord(8, 3)])}
    world = DoChaseWorld(
        rng=RogueRng(case["seed"]),
        hero=Coord(*case.get("hero", [10, 10])),
        proom=case.get("proom", 1),
        rooms=rooms,
        passages=passages,
        dest_room=case.get("dest_room", 1),
        passage_index=case.get("passage_index", 9),
        chase_keep=case.get("chase_keep", True),
        chase_pos=Coord(*case.get("chase_pos", [6, 6])),
        chase_room=case.get("chase_room", case.get("room", 0)),
        attack_return=case.get("attack_return", 0),
        find_dest_kind=case.get("find_dest", "hero"),
        find_dest_pos=Coord(*case.get("find_dest_pos", [10, 10])),
        running=case.get("running", True),
        count=case.get("count", 1),
        quiet=case.get("quiet", 3),
        has_hit=case.get("has_hit", False),
        to_death=case.get("to_death", False),
        kamikaze=case.get("kamikaze", False),
    )
    if case.get("tile") is not None:
        world.terrain[(case.get("pos", [5, 5])[0], case.get("pos", [5, 5])[1])] = case["tile"]
    for obj in case.get("objects", []):
        world.objects.append(ChaseObject(obj.get("type", "*"), Coord(obj["pos"][0], obj["pos"][1])))
    return world


def _cases() -> list[dict[str, Any]]:
    return [
        {"name": "different_room_routes_exit", "seed": 1, "dest": "hero", "dest_pos": [10, 10], "chase_keep": True, "chase_pos": [6, 6], "chase_room": 0},
        {"name": "door_reroutes_passage", "seed": 1, "tile": DOOR, "dest": "object", "dest_pos": [12, 12], "dest_room": 2, "chase_keep": True, "chase_pos": [8, 3], "chase_room": 9},
        {"name": "dragon_flame", "seed": 1, "type": "D", "room": 1, "pos": [5, 5], "dest": "hero", "dest_pos": [5, 10], "hero": [5, 10], "chase_keep": True, "has_hit": True, "to_death": True, "kamikaze": True},
        {"name": "dragon_cancelled_chases", "seed": 1, "type": "D", "flags": ISRUN | ISCANC, "room": 1, "pos": [5, 5], "dest": "hero", "dest_pos": [5, 10], "hero": [5, 10], "chase_keep": True, "chase_pos": [5, 6], "chase_room": 1},
        {"name": "attack_hero_return", "seed": 7, "room": 1, "pos": [5, 5], "dest": "hero", "dest_pos": [10, 10], "hero": [10, 10], "chase_keep": False, "chase_pos": [5, 5], "attack_return": -1},
        {"name": "pickup_object_keeps_running_after_find_dest", "seed": 7, "room": 1, "pos": [5, 5], "dest": "object", "dest_pos": [6, 6], "dest_room": 1, "chase_keep": False, "chase_pos": [6, 6], "chase_room": 1, "objects": [{"type": "*", "pos": [6, 6]}], "find_dest": "hero", "find_dest_pos": [10, 10]},
        {"name": "stoprun_at_destination", "seed": 7, "room": 1, "pos": [5, 5], "dest": "custom", "dest_pos": [6, 6], "dest_room": 1, "chase_keep": False, "chase_pos": [6, 6], "chase_room": 1},
        {"name": "venus_flytrap_no_relocate", "seed": 7, "type": "F", "room": 1, "pos": [5, 5], "dest": "hero", "dest_pos": [10, 10], "hero": [10, 10], "chase_keep": True, "chase_pos": [6, 6], "chase_room": 1},
        {"name": "greed_gold_taken_resets_dest", "seed": 7, "type": "O", "flags": ISRUN | ISGREED, "room_goldval": 0, "dest": "object", "dest_pos": [6, 6], "dest_room": 1, "chase_keep": True, "chase_pos": [5, 6], "chase_room": 0},
    ]


def _dragon_flame(world: DoChaseWorld, monster: ChaseMonster) -> bool:
    aligned = (
        monster.pos.y == world.hero.y
        or monster.pos.x == world.hero.x
        or abs(monster.pos.y - world.hero.y) == abs(monster.pos.x - world.hero.x)
    )
    if monster.monster_type != "D" or not aligned or dist(monster.pos, world.hero) > BOLT_LENGTH * BOLT_LENGTH or monster.flags & ISCANC:
        return False
    shot_roll = world.rng.rnd(DRAGONSHOT)
    world.trace["dragon_roll"] = shot_roll
    if shot_roll != 0:
        return False
    world.trace["delta"] = {"y": sign(world.hero.y - monster.pos.y), "x": sign(world.hero.x - monster.pos.x)}
    if world.has_hit:
        world.markers.append("endmsg")
    world.markers.append("fire_bolt_flame")
    world.running = False
    world.count = 0
    world.quiet = 0
    if world.to_death and not (monster.flags & ISTARGET):
        world.to_death = False
        world.kamikaze = False
    return True


def dist(first: Coord, second: Coord) -> int:
    return (second.x - first.x) * (second.x - first.x) + (second.y - first.y) * (second.y - first.y)


def coord_eq(first: Coord, second: Coord) -> bool:
    return first.x == second.x and first.y == second.y


def sign(value: int) -> int:
    return (value > 0) - (value < 0)
