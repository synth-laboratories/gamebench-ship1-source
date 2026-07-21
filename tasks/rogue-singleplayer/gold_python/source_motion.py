"""Source-faithful Rogue motion and visibility decision slices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from source_level import F_PASS, F_PNUM, F_REAL, F_SEEN, ISDARK, ISGONE, Coord, Room
from source_rogue import DOOR, FLOOR, NUMCOLS, NUMLINES, PASSAGE, STAIRS, TRAP, step_ok


F_TMASK = 0x07
LAMPDIST = 3

T_DOOR = 0
T_BEAR = 3
T_TELEP = 4
T_RUST = 6


@dataclass
class RoomRef:
    kind: str
    index: int

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "index": self.index}


@dataclass
class SourceMotionMap:
    rows: list[list[str]]
    flags: list[list[int]]
    monsters: list[list[bool]]
    rooms: list[Room]
    passages: list[Room]

    @classmethod
    def base(cls) -> "SourceMotionMap":
        rows = [[" " for _ in range(NUMCOLS)] for _ in range(NUMLINES)]
        flags = [[F_REAL for _ in range(NUMCOLS)] for _ in range(NUMLINES)]
        monsters = [[False for _ in range(NUMCOLS)] for _ in range(NUMLINES)]
        rooms = [Room() for _ in range(9)]
        passages = [Room() for _ in range(13)]
        rooms[0].pos = Coord(y=1, x=1)
        rooms[0].max = Coord(y=5, x=10)
        rooms[1].pos = Coord(y=1, x=20)
        rooms[1].max = Coord(y=5, x=10)
        rooms[1].flags = ISDARK
        for y in range(1, 6):
            for x in range(1, 11):
                rows[y][x] = FLOOR
        for x in range(1, 11):
            rows[1][x] = "-"
            rows[5][x] = "-"
        for y in range(1, 6):
            rows[y][1] = "|"
            rows[y][10] = "|"
        for y in range(1, 6):
            for x in range(20, 30):
                rows[y][x] = FLOOR
        return cls(rows=rows, flags=flags, monsters=monsters, rooms=rooms, passages=passages)

    def copy(self) -> "SourceMotionMap":
        copied = SourceMotionMap(
            rows=[row[:] for row in self.rows],
            flags=[row[:] for row in self.flags],
            monsters=[row[:] for row in self.monsters],
            rooms=[_copy_room(room) for room in self.rooms],
            passages=[_copy_room(passage) for passage in self.passages],
        )
        return copied

    def set_tile(self, coord: Coord, ch: str, flags: int = F_REAL, monst: bool = False) -> None:
        self.rows[coord.y][coord.x] = ch
        self.flags[coord.y][coord.x] = flags
        self.monsters[coord.y][coord.x] = monst

    def ch(self, coord: Coord) -> str:
        return self.rows[coord.y][coord.x]

    def flag(self, coord: Coord) -> int:
        return self.flags[coord.y][coord.x]


def _copy_room(room: Room) -> Room:
    return Room(
        pos=Coord(y=room.pos.y, x=room.pos.x),
        max=Coord(y=room.max.y, x=room.max.x),
        gold=Coord(y=room.gold.y, x=room.gold.x),
        goldval=room.goldval,
        flags=room.flags,
        exits=[Coord(y=coord.y, x=coord.x) for coord in room.exits],
    )


def diag_ok(game_map: SourceMotionMap, start: Coord, end: Coord) -> bool:
    if end.x < 0 or end.x >= NUMCOLS or end.y <= 0 or end.y >= NUMLINES - 1:
        return False
    if end.x == start.x or end.y == start.y:
        return True
    return step_ok(game_map.rows[end.y][start.x]) and step_ok(game_map.rows[start.y][end.x])


def turn_ok(game_map: SourceMotionMap, coord: Coord) -> bool:
    flags = game_map.flag(coord)
    return game_map.ch(coord) == DOOR or (flags & (F_REAL | F_PASS)) == (F_REAL | F_PASS)


def roomin(game_map: SourceMotionMap, coord: Coord) -> RoomRef | None:
    flags = game_map.flag(coord)
    if flags & F_PASS:
        return RoomRef(kind="passage", index=flags & F_PNUM)
    for index, room in enumerate(game_map.rooms):
        if (
            coord.x <= room.pos.x + room.max.x
            and room.pos.x <= coord.x
            and coord.y <= room.pos.y + room.max.y
            and room.pos.y <= coord.y
        ):
            return RoomRef(kind="room", index=index)
    return None


def cansee(game_map: SourceMotionMap, hero: Coord, target: Coord, *, is_blind: bool = False) -> bool:
    if is_blind:
        return False
    if _dist(target.y, target.x, hero.y, hero.x) < LAMPDIST:
        if game_map.flag(target) & F_PASS:
            if (
                target.y != hero.y
                and target.x != hero.x
                and not step_ok(game_map.rows[target.y][hero.x])
                and not step_ok(game_map.rows[hero.y][target.x])
            ):
                return False
        return True
    target_room = roomin(game_map, target)
    hero_room = roomin(game_map, hero)
    if target_room is None or hero_room is None:
        return False
    if target_room.kind != hero_room.kind or target_room.index != hero_room.index:
        return False
    if target_room.kind != "room":
        return True
    return not (game_map.rooms[target_room.index].flags & ISDARK)


def classify_move(game_map: SourceMotionMap, hero: Coord, dy: int, dx: int, *, is_levit: bool = False) -> dict[str, Any]:
    target = Coord(y=hero.y + dy, x=hero.x + dx)
    if target.x < 0 or target.x >= NUMCOLS or target.y <= 0 or target.y >= NUMLINES - 1:
        return _move_payload("blocked", hero, target, moved=False, reason="boundary")
    if not diag_ok(game_map, hero, target):
        return _move_payload("blocked", hero, target, moved=False, reason="diagonal")
    flags = game_map.flag(target)
    ch = game_map.ch(target)
    revealed_hidden_trap = False
    if not (flags & F_REAL) and ch == FLOOR and not is_levit:
        ch = TRAP
        game_map.rows[target.y][target.x] = TRAP
        flags |= F_REAL
        game_map.flags[target.y][target.x] = flags
        revealed_hidden_trap = True
    if ch in {" ", "|", "-"}:
        return _move_payload("blocked", hero, target, moved=False, reason="wall", tile=ch)
    if ch == DOOR:
        return _move_payload("door", hero, target, moved=True, tile=ch)
    if ch == TRAP:
        trap_kind = _be_trapped(game_map, target)
        moved = trap_kind not in {T_DOOR, T_TELEP}
        return _move_payload(
            "trap_move" if moved else "trap_no_move",
            hero,
            target,
            moved=moved,
            tile=ch,
            trap_kind=trap_kind,
            revealed_hidden_trap=revealed_hidden_trap,
            cell_after=_cell_after(game_map, target),
        )
    if ch == PASSAGE:
        return _move_payload("passage", hero, target, moved=True, tile=ch)
    if ch == FLOOR:
        if not (flags & F_REAL):
            _be_trapped(game_map, hero)
        return _move_payload("floor", hero, target, moved=True, tile=ch)
    if ch == STAIRS:
        return _move_payload("stairs", hero, target, moved=True, tile=ch, seenstairs=True)
    if ch.isupper() or game_map.monsters[target.y][target.x]:
        return _move_payload("fight", hero, target, moved=False, tile=ch, fight=True)
    return _move_payload("item", hero, target, moved=True, tile=ch, take=ch)


def source_motion_report() -> dict[str, Any]:
    return {
        "move_cases": [_run_move_case(case) for case in _move_cases()],
        "spatial_cases": _spatial_cases(),
    }


def _be_trapped(game_map: SourceMotionMap, coord: Coord) -> int:
    game_map.rows[coord.y][coord.x] = TRAP
    trap_kind = game_map.flags[coord.y][coord.x] & F_TMASK
    game_map.flags[coord.y][coord.x] |= F_SEEN
    return trap_kind


def _move_payload(
    transition: str,
    hero: Coord,
    target: Coord,
    *,
    moved: bool,
    reason: str = "",
    tile: str = "",
    trap_kind: int | None = None,
    revealed_hidden_trap: bool = False,
    seenstairs: bool = False,
    fight: bool = False,
    take: str = "",
    cell_after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "transition": transition,
        "from": hero.to_dict(),
        "to": target.to_dict(),
        "hero_after": (target if moved else hero).to_dict(),
        "moved": moved,
        "reason": reason,
        "tile": tile,
        "trap_kind": trap_kind,
        "revealed_hidden_trap": revealed_hidden_trap,
        "seenstairs": seenstairs,
        "fight": fight,
        "take": take,
        "cell_after": cell_after,
    }


def _cell_after(game_map: SourceMotionMap, coord: Coord) -> dict[str, Any]:
    return {"ch": game_map.ch(coord), "flags": game_map.flag(coord)}


def _run_move_case(case: dict[str, Any]) -> dict[str, Any]:
    game_map = SourceMotionMap.base()
    for tile in case["tiles"]:
        game_map.set_tile(Coord(y=tile["y"], x=tile["x"]), tile["ch"], tile.get("flags", F_REAL), tile.get("monst", False))
    hero = Coord(y=case["hero"][0], x=case["hero"][1])
    outcome = classify_move(game_map, hero, case["delta"][0], case["delta"][1])
    target = Coord(y=hero.y + case["delta"][0], x=hero.x + case["delta"][1])
    payload = {
        "name": case["name"],
        "diag_ok": diag_ok(game_map, hero, target),
        "room_before": _room_ref_dict(roomin(game_map, hero)),
        "room_target": _room_ref_dict(roomin(game_map, target)) if 0 <= target.y < NUMLINES and 0 <= target.x < NUMCOLS else None,
        "outcome": outcome,
    }
    return payload


def _spatial_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    lit = SourceMotionMap.base()
    cases.append(_spatial_payload("lit_same_room_far", lit, Coord(y=3, x=3), Coord(y=4, x=8)))
    dark = SourceMotionMap.base()
    cases.append(_spatial_payload("dark_same_room_far", dark, Coord(y=3, x=22), Coord(y=4, x=28)))
    blocked = SourceMotionMap.base()
    blocked.set_tile(Coord(y=4, x=4), PASSAGE, F_REAL | F_PASS | 1)
    blocked.set_tile(Coord(y=4, x=3), "|")
    blocked.set_tile(Coord(y=3, x=4), "|")
    cases.append(_spatial_payload("near_passage_blocked_diagonal", blocked, Coord(y=3, x=3), Coord(y=4, x=4)))
    clear = SourceMotionMap.base()
    clear.set_tile(Coord(y=4, x=4), PASSAGE, F_REAL | F_PASS | 1)
    clear.set_tile(Coord(y=4, x=3), FLOOR)
    clear.set_tile(Coord(y=3, x=4), "|")
    cases.append(_spatial_payload("near_passage_clear_diagonal", clear, Coord(y=3, x=3), Coord(y=4, x=4)))
    turn = SourceMotionMap.base()
    turn.set_tile(Coord(y=3, x=4), DOOR)
    turn.set_tile(Coord(y=3, x=5), PASSAGE, F_REAL | F_PASS | 2)
    turn.set_tile(Coord(y=3, x=6), PASSAGE, F_PASS | 2)
    cases.append(
        {
            "name": "turn_ok",
            "door": turn_ok(turn, Coord(y=3, x=4)),
            "real_passage": turn_ok(turn, Coord(y=3, x=5)),
            "hidden_passage": turn_ok(turn, Coord(y=3, x=6)),
        }
    )
    return cases


def _spatial_payload(name: str, game_map: SourceMotionMap, hero: Coord, target: Coord) -> dict[str, Any]:
    return {
        "name": name,
        "hero_room": _room_ref_dict(roomin(game_map, hero)),
        "target_room": _room_ref_dict(roomin(game_map, target)),
        "diag_ok": diag_ok(game_map, hero, target),
        "cansee": cansee(game_map, hero, target),
    }


def _room_ref_dict(ref: RoomRef | None) -> dict[str, Any] | None:
    return None if ref is None else ref.to_dict()


def _move_cases() -> list[dict[str, Any]]:
    return [
        {"name": "floor_east", "hero": [3, 3], "delta": [0, 1], "tiles": [{"y": 3, "x": 4, "ch": FLOOR}]},
        {"name": "wall_west", "hero": [3, 2], "delta": [0, -1], "tiles": [{"y": 3, "x": 1, "ch": "|"}]},
        {"name": "boundary_top", "hero": [1, 4], "delta": [-1, 0], "tiles": []},
        {
            "name": "diagonal_blocked",
            "hero": [3, 3],
            "delta": [-1, 1],
            "tiles": [{"y": 2, "x": 4, "ch": FLOOR}, {"y": 2, "x": 3, "ch": "|"}, {"y": 3, "x": 4, "ch": FLOOR}],
        },
        {
            "name": "diagonal_open",
            "hero": [3, 3],
            "delta": [-1, 1],
            "tiles": [{"y": 2, "x": 4, "ch": FLOOR}, {"y": 2, "x": 3, "ch": FLOOR}, {"y": 3, "x": 4, "ch": FLOOR}],
        },
        {"name": "door_east", "hero": [3, 3], "delta": [0, 1], "tiles": [{"y": 3, "x": 4, "ch": DOOR}]},
        {"name": "passage_east", "hero": [3, 3], "delta": [0, 1], "tiles": [{"y": 3, "x": 4, "ch": PASSAGE, "flags": F_REAL | F_PASS | 1}]},
        {"name": "stairs_east", "hero": [3, 3], "delta": [0, 1], "tiles": [{"y": 3, "x": 4, "ch": STAIRS}]},
        {"name": "item_food_east", "hero": [3, 3], "delta": [0, 1], "tiles": [{"y": 3, "x": 4, "ch": ":"}]},
        {"name": "monster_fight_east", "hero": [3, 3], "delta": [0, 1], "tiles": [{"y": 3, "x": 4, "ch": "A"}]},
        {"name": "hidden_bear_trap", "hero": [3, 3], "delta": [0, 1], "tiles": [{"y": 3, "x": 4, "ch": FLOOR, "flags": T_BEAR}]},
        {"name": "visible_trapdoor", "hero": [3, 3], "delta": [0, 1], "tiles": [{"y": 3, "x": 4, "ch": TRAP, "flags": F_REAL | T_DOOR}]},
        {"name": "visible_rust_trap", "hero": [3, 3], "delta": [0, 1], "tiles": [{"y": 3, "x": 4, "ch": TRAP, "flags": F_REAL | T_RUST}]},
    ]


def _dist(y1: int, x1: int, y2: int, x2: int) -> int:
    return (x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1)
