"""Source-faithful Rogue chase movement decision slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_rogue import NUMCOLS, NUMLINES, SCROLL, RogueRng, step_ok


ISHUH = 0o001000
ISHASTE = 0o000100
ISSLOW = 0o100000
S_SCARE = 10


@dataclass
class Coord:
    y: int
    x: int

    def to_dict(self) -> dict[str, int]:
        return {"y": self.y, "x": self.x}


@dataclass
class ChaseThing:
    monster_type: str
    pos: Coord
    flags: int
    turn: bool = True
    disguise: str | None = None

    def __post_init__(self) -> None:
        if self.disguise is None:
            self.disguise = self.monster_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.monster_type,
            "pos": self.pos.to_dict(),
            "flags": self.flags,
            "turn": self.turn,
            "disguise": self.disguise,
        }


@dataclass
class ChaseObject:
    obj_type: str
    which: int
    pos: Coord


@dataclass
class ChaseMap:
    terrain: dict[tuple[int, int], str] = field(default_factory=dict)
    objects: list[ChaseObject] = field(default_factory=list)
    monsters: list[ChaseThing] = field(default_factory=list)

    def chat(self, coord: Coord) -> str:
        return self.terrain.get((coord.y, coord.x), ".")

    def moat(self, coord: Coord) -> ChaseThing | None:
        for monster in self.monsters:
            if coord_eq(monster.pos, coord):
                return monster
        return None

    def winat(self, coord: Coord) -> str:
        monster = self.moat(coord)
        if monster is not None:
            return monster.disguise or monster.monster_type
        return self.chat(coord)

    def object_at(self, coord: Coord) -> ChaseObject | None:
        for obj in self.objects:
            if coord_eq(obj.pos, coord):
                return obj
        return None


def chase(rng: RogueRng, game_map: ChaseMap, thing: ChaseThing, target: Coord, hero: Coord) -> dict[str, Any]:
    trace: dict[str, Any] = {"branch": "direct", "candidates": []}
    random_branch = False
    if thing.flags & ISHUH:
        confused_roll = rng.rnd(5)
        trace["confused_roll"] = confused_roll
        random_branch = confused_roll != 0
    if not random_branch and thing.monster_type == "P":
        phantom_roll = rng.rnd(5)
        trace["phantom_roll"] = phantom_roll
        random_branch = phantom_roll == 0
    if not random_branch and thing.monster_type == "B":
        bat_roll = rng.rnd(2)
        trace["bat_roll"] = bat_roll
        random_branch = bat_roll == 0

    if random_branch:
        trace["branch"] = "random"
        chosen = rndmove(rng, thing)
        curdist = dist(chosen, target)
        clear_roll = rng.rnd(20)
        trace["clear_roll"] = clear_roll
        if clear_roll == 0:
            thing.flags &= ~ISHUH
    else:
        curdist = dist(thing.pos, target)
        chosen = Coord(thing.pos.y, thing.pos.x)
        plcnt = 1
        ey = thing.pos.y + 1
        if ey >= NUMLINES - 1:
            ey = NUMLINES - 2
        ex = thing.pos.x + 1
        if ex >= NUMCOLS:
            ex = NUMCOLS - 1
        for x in range(thing.pos.x - 1, ex + 1):
            if x < 0:
                continue
            for y in range(thing.pos.y - 1, ey + 1):
                tryp = Coord(y, x)
                candidate: dict[str, Any] = {"pos": tryp.to_dict()}
                if not diag_ok(game_map, thing.pos, tryp):
                    candidate["skip"] = "diag"
                    trace["candidates"].append(candidate)
                    continue
                ch = game_map.winat(tryp)
                candidate["ch"] = ch
                if not step_ok(ch):
                    candidate["skip"] = "blocked"
                    trace["candidates"].append(candidate)
                    continue
                obj = game_map.object_at(tryp)
                if ch == SCROLL and obj is not None and obj.which == S_SCARE:
                    candidate["skip"] = "scare_scroll"
                    trace["candidates"].append(candidate)
                    continue
                blocker = game_map.moat(tryp)
                if blocker is not None and blocker.monster_type == "X":
                    candidate["skip"] = "xeroc"
                    trace["candidates"].append(candidate)
                    continue
                thisdist = dist(tryp, target)
                candidate["dist"] = thisdist
                if thisdist < curdist:
                    plcnt = 1
                    chosen = Coord(tryp.y, tryp.x)
                    curdist = thisdist
                    candidate["chosen"] = True
                elif thisdist == curdist:
                    plcnt += 1
                    tie_roll = rng.rnd(plcnt)
                    candidate["tie_roll"] = tie_roll
                    candidate["plcnt"] = plcnt
                    if tie_roll == 0:
                        chosen = Coord(tryp.y, tryp.x)
                        curdist = thisdist
                        candidate["chosen"] = True
                trace["candidates"].append(candidate)

    keep_chasing = curdist != 0 and not coord_eq(chosen, hero)
    return {
        "chosen": chosen.to_dict(),
        "curdist": curdist,
        "keep_chasing": keep_chasing,
        "thing": thing.to_dict(),
        "rng_seed": rng.seed,
        "trace": trace,
    }


def move_monst_schedule(thing: ChaseThing, do_chase_results: list[int]) -> dict[str, Any]:
    calls = 0
    returned = 0
    if not (thing.flags & ISSLOW) or thing.turn:
        calls += 1
        if do_chase_results and do_chase_results[0] == -1:
            returned = -1
            return _move_schedule_payload(thing, calls, returned)
    if thing.flags & ISHASTE:
        calls += 1
        if len(do_chase_results) > 1 and do_chase_results[1] == -1:
            returned = -1
            return _move_schedule_payload(thing, calls, returned)
    thing.turn = not thing.turn
    return _move_schedule_payload(thing, calls, returned)


def source_chase_report() -> dict[str, Any]:
    return {
        "schema": "gamebench.rogue.source_chase.v1",
        "chase_cases": [_run_chase_case(case) for case in _chase_cases()],
        "move_monst": [_run_move_case(case) for case in _move_cases()],
    }


def _run_chase_case(case: dict[str, Any]) -> dict[str, Any]:
    game_map = ChaseMap()
    for tile in case.get("tiles", []):
        game_map.terrain[(tile["y"], tile["x"])] = tile["ch"]
    for obj in case.get("objects", []):
        game_map.objects.append(ChaseObject(obj["type"], obj["which"], Coord(obj["y"], obj["x"])))
    for monster in case.get("monsters", []):
        game_map.monsters.append(ChaseThing(monster["type"], Coord(monster["y"], monster["x"]), monster.get("flags", 0), True, monster.get("disguise")))
    thing = ChaseThing(case["type"], Coord(case["pos"][0], case["pos"][1]), case.get("flags", 0), case.get("turn", True), case.get("disguise"))
    target = Coord(case["target"][0], case["target"][1])
    hero = Coord(case["hero"][0], case["hero"][1])
    outcome = chase(RogueRng(case["seed"]), game_map, thing, target, hero)
    return {"name": case["name"], "seed": case["seed"], "outcome": outcome}


def _run_move_case(case: dict[str, Any]) -> dict[str, Any]:
    thing = ChaseThing(case["type"], Coord(5, 5), case["flags"], case["turn"])
    return {"name": case["name"], "outcome": move_monst_schedule(thing, case.get("results", []))}


def _chase_cases() -> list[dict[str, Any]]:
    return [
        {"name": "direct_east", "seed": 1, "type": "K", "pos": [5, 5], "target": [5, 7], "hero": [5, 7]},
        {"name": "tie_break", "seed": 7, "type": "K", "pos": [5, 5], "target": [7, 7], "hero": [9, 9]},
        {"name": "wall_blocks_diagonal", "seed": 7, "type": "K", "pos": [5, 5], "target": [4, 4], "hero": [4, 4], "tiles": [{"y": 4, "x": 5, "ch": "|"}, {"y": 5, "x": 4, "ch": "-"}]},
        {"name": "scare_scroll_skip", "seed": 7, "type": "K", "pos": [5, 5], "target": [5, 4], "hero": [5, 4], "tiles": [{"y": 5, "x": 4, "ch": SCROLL}], "objects": [{"type": SCROLL, "which": S_SCARE, "y": 5, "x": 4}]},
        {"name": "ordinary_scroll_allowed", "seed": 7, "type": "K", "pos": [5, 5], "target": [5, 4], "hero": [5, 4], "tiles": [{"y": 5, "x": 4, "ch": SCROLL}], "objects": [{"type": SCROLL, "which": 1, "y": 5, "x": 4}]},
        {"name": "xeroc_skip", "seed": 7, "type": "K", "pos": [5, 5], "target": [5, 4], "hero": [5, 4], "monsters": [{"type": "X", "y": 5, "x": 4, "disguise": ":"}]},
        {"name": "confused_random", "seed": 5, "type": "K", "flags": ISHUH, "pos": [5, 5], "target": [7, 7], "hero": [7, 7]},
        {"name": "phantom_random", "seed": 1, "type": "P", "pos": [5, 5], "target": [7, 7], "hero": [7, 7]},
        {"name": "bat_random", "seed": 1, "type": "B", "pos": [5, 5], "target": [7, 7], "hero": [7, 7]},
    ]


def _move_cases() -> list[dict[str, Any]]:
    return [
        {"name": "normal_one_chase", "type": "K", "flags": 0, "turn": True, "results": [0]},
        {"name": "slow_turn_skips", "type": "K", "flags": ISSLOW, "turn": False, "results": []},
        {"name": "slow_turn_moves", "type": "K", "flags": ISSLOW, "turn": True, "results": [0]},
        {"name": "haste_two_chases", "type": "K", "flags": ISHASTE, "turn": True, "results": [0, 0]},
        {"name": "first_chase_stops", "type": "K", "flags": ISHASTE, "turn": True, "results": [-1, 0]},
        {"name": "second_chase_stops", "type": "K", "flags": ISHASTE, "turn": True, "results": [0, -1]},
    ]


def rndmove(rng: RogueRng, thing: ChaseThing) -> Coord:
    y = thing.pos.y + rng.rnd(3) - 1
    x = thing.pos.x + rng.rnd(3) - 1
    return Coord(y, x)


def diag_ok(game_map: ChaseMap, start: Coord, end: Coord) -> bool:
    if end.x < 0 or end.x >= NUMCOLS or end.y <= 0 or end.y >= NUMLINES - 1:
        return False
    if end.x == start.x or end.y == start.y:
        return True
    return step_ok(game_map.chat(Coord(end.y, start.x))) and step_ok(game_map.chat(Coord(start.y, end.x)))


def dist(first: Coord, second: Coord) -> int:
    return (second.x - first.x) * (second.x - first.x) + (second.y - first.y) * (second.y - first.y)


def coord_eq(first: Coord, second: Coord) -> bool:
    return first.x == second.x and first.y == second.y


def _move_schedule_payload(thing: ChaseThing, calls: int, returned: int) -> dict[str, Any]:
    return {"calls": calls, "returned": returned, "thing": thing.to_dict()}
