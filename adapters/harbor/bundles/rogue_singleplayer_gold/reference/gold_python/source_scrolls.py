"""Source-faithful Rogue scroll behavior slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_rogue import ARMOR, DOOR, FLOOR, FOOD, PASSAGE, POTION, SCROLL, STAIRS, TRAP, WEAPON, RogueRng


R_OR_S = -2

F_PASS = 0x80
F_SEEN = 0x40
F_REAL = 0x10

ISCURSED = 0o000001
ISPROT = 0o000040

CANHUH = 0o000001
ISHELD = 0o000400
ISRUN = 0o020000
SEEMONST = 0o040000

S_CONFUSE = 0
S_MAP = 1
S_HOLD = 2
S_SLEEP = 3
S_ARMOR = 4
S_ID_POTION = 5
S_ID_SCROLL = 6
S_ID_WEAPON = 7
S_ID_ARMOR = 8
S_ID_R_OR_S = 9
S_SCARE = 10
S_FDET = 11
S_TELEP = 12
S_ENCH = 13
S_CREATE = 14
S_REMOVE = 15
S_AGGR = 16
S_PROTECT = 17
MAXSCROLLS = 18


@dataclass
class ScrollObject:
    obj_type: str
    which: int
    count: int = 1


@dataclass
class ScrollItem:
    obj_type: str
    which: int = 0
    flags: int = 0
    arm: int = 0
    hplus: int = 0
    dplus: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.obj_type, "which": self.which, "flags": self.flags, "arm": self.arm, "hplus": self.hplus, "dplus": self.dplus}


@dataclass
class ScrollMonster:
    monster_type: str = "K"
    flags: int = 0
    oldch: str = " "

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.monster_type, "flags": self.flags, "oldch": self.oldch}


@dataclass
class MapCell:
    ch: str
    flags: int = 0
    monster: ScrollMonster | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"ch": self.ch, "flags": self.flags, "monster": self.monster.to_dict() if self.monster is not None else None}


@dataclass
class ScrollWorld:
    rng: RogueRng
    player_flags: int = 0
    no_command: int = 0
    current_weapon_is_obj: bool = False
    current_weapon: ScrollItem | None = None
    current_armor: ScrollItem | None = None
    left_ring: ScrollItem | None = None
    right_ring: ScrollItem | None = None
    nearby_monsters: list[ScrollMonster] = field(default_factory=list)
    create_candidates: int = 0
    food_count: int = 0
    teleport_room_changed: bool = False
    map_cells: list[MapCell] = field(default_factory=list)
    scr_known: list[bool] = field(default_factory=lambda: [False] * MAXSCROLLS)
    markers: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rng_seed": self.rng.seed,
            "player_flags": self.player_flags,
            "no_command": self.no_command,
            "current_weapon_is_obj": self.current_weapon_is_obj,
            "current_weapon": self.current_weapon.to_dict() if self.current_weapon is not None else None,
            "current_armor": self.current_armor.to_dict() if self.current_armor is not None else None,
            "left_ring": self.left_ring.to_dict() if self.left_ring is not None else None,
            "right_ring": self.right_ring.to_dict() if self.right_ring is not None else None,
            "nearby_monsters": [monster.to_dict() for monster in self.nearby_monsters],
            "map_cells": [cell.to_dict() for cell in self.map_cells],
            "scr_known": self.scr_known,
            "markers": self.markers,
            "trace": self.trace,
        }


def read_scroll(world: ScrollWorld, obj: ScrollObject | None) -> None:
    if obj is None:
        return
    if obj.obj_type != SCROLL:
        world.markers.append("nothing_to_read")
        return
    if world.current_weapon_is_obj:
        world.current_weapon_is_obj = False
        world.markers.append("unwield_scroll")
    discardit = obj.count == 1
    world.markers.append("leave_pack")
    which = obj.which
    if which == S_CONFUSE:
        world.player_flags |= CANHUH
        world.markers.append("hands_glow")
    elif which == S_ARMOR:
        if world.current_armor is not None:
            world.current_armor.arm -= 1
            world.current_armor.flags &= ~ISCURSED
            world.markers.append("armor_glows")
    elif which == S_HOLD:
        held = 0
        for monster in world.nearby_monsters:
            if monster.flags & ISRUN:
                monster.flags &= ~ISRUN
                monster.flags |= ISHELD
                held += 1
        if held:
            world.scr_known[S_HOLD] = True
            world.markers.append(f"monsters_freeze:{held}")
        else:
            world.markers.append("loss")
    elif which == S_SLEEP:
        world.scr_known[S_SLEEP] = True
        sleep_time = world.rng.spread(5)
        sleep_roll = world.rng.rnd(sleep_time)
        world.trace["sleep_time"] = sleep_time
        world.trace["sleep_roll"] = sleep_roll
        world.no_command += sleep_roll + 4
        world.player_flags &= ~ISRUN
        world.markers.append("fall_asleep")
    elif which == S_CREATE:
        create_monster(world)
    elif which in {S_ID_POTION, S_ID_SCROLL, S_ID_WEAPON, S_ID_ARMOR, S_ID_R_OR_S}:
        world.scr_known[which] = True
        id_type = {S_ID_POTION: POTION, S_ID_SCROLL: SCROLL, S_ID_WEAPON: WEAPON, S_ID_ARMOR: ARMOR, S_ID_R_OR_S: R_OR_S}[which]
        world.markers.append(f"id_scroll:{which}")
        world.markers.append(f"whatis:{id_type}")
    elif which == S_MAP:
        world.scr_known[S_MAP] = True
        world.markers.append("map_msg")
        magic_map(world)
    elif which == S_FDET:
        if world.food_count > 0:
            world.scr_known[S_FDET] = True
            world.markers.append(f"show_food:{world.food_count}")
        else:
            world.markers.append("nose_tingles")
    elif which == S_TELEP:
        world.markers.append("teleport")
        if world.teleport_room_changed:
            world.scr_known[S_TELEP] = True
    elif which == S_ENCH:
        if world.current_weapon is None or world.current_weapon.obj_type != WEAPON:
            world.markers.append("loss")
        else:
            world.current_weapon.flags &= ~ISCURSED
            if world.rng.rnd(2) == 0:
                world.current_weapon.hplus += 1
                world.trace["enchanted"] = "hplus"
            else:
                world.current_weapon.dplus += 1
                world.trace["enchanted"] = "dplus"
            world.markers.append("weapon_glows")
    elif which == S_SCARE:
        world.markers.append("laughter")
    elif which == S_REMOVE:
        uncurse(world.current_armor)
        uncurse(world.current_weapon)
        uncurse(world.left_ring)
        uncurse(world.right_ring)
        world.markers.append("remove_curse")
    elif which == S_AGGR:
        world.markers.append("aggravate")
        world.markers.append("hum")
    elif which == S_PROTECT:
        if world.current_armor is not None:
            world.current_armor.flags |= ISPROT
            world.markers.append("protect_armor")
        else:
            world.markers.append("loss")
    else:
        world.markers.append("puzzling")
        return
    world.markers.append("look:true")
    world.markers.append("status")
    world.markers.append(f"call_it:{which}")
    if discardit:
        world.markers.append("discard")


def create_monster(world: ScrollWorld) -> None:
    selected = -1
    for index in range(world.create_candidates):
        if world.rng.rnd(index + 1) == 0:
            selected = index
    if selected < 0:
        world.markers.append("faint_cry")
    else:
        world.trace["create_selected"] = selected
        world.markers.append("new_monster")


def magic_map(world: ScrollWorld) -> None:
    draw_count = 0
    oldch_count = 0
    for cell in world.map_cells:
        display = map_cell(cell)
        if display != " ":
            if cell.monster is not None:
                cell.monster.oldch = display
                oldch_count += 1
            if cell.monster is None or not (world.player_flags & SEEMONST):
                draw_count += 1
    world.trace["map_draw"] = draw_count
    world.trace["map_oldch"] = oldch_count


def map_cell(cell: MapCell) -> str:
    ch = cell.ch
    if ch in {DOOR, STAIRS}:
        return ch
    if ch in {"-", "|"}:
        if not (cell.flags & F_REAL):
            cell.ch = DOOR
            cell.flags |= F_REAL
            return DOOR
        return ch
    if ch == " ":
        if cell.flags & F_REAL:
            return map_default(cell)
        cell.flags |= F_REAL
        cell.ch = PASSAGE
        ch = PASSAGE
    if ch == PASSAGE:
        if not (cell.flags & F_REAL):
            cell.ch = PASSAGE
        cell.flags |= F_SEEN | F_REAL
        return PASSAGE
    if ch == FLOOR:
        if cell.flags & F_REAL:
            return " "
        cell.ch = TRAP
        cell.flags |= F_SEEN | F_REAL
        return TRAP
    return map_default(cell)


def map_default(cell: MapCell) -> str:
    if cell.flags & F_PASS:
        if not (cell.flags & F_REAL):
            cell.ch = PASSAGE
        cell.flags |= F_SEEN | F_REAL
        return PASSAGE
    return " "


def uncurse(item: ScrollItem | None) -> None:
    if item is not None:
        item.flags &= ~ISCURSED


def source_scrolls_report() -> dict[str, Any]:
    return {"schema": "gamebench.rogue.source_scrolls.v1", "cases": [_run_case(case) for case in _cases()]}


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    world = ScrollWorld(
        rng=RogueRng(case["seed"]),
        player_flags=case.get("player_flags", 0),
        no_command=case.get("no_command", 0),
        current_weapon_is_obj=case.get("current_weapon_is_obj", False),
        current_weapon=_item(case.get("current_weapon")),
        current_armor=_item(case.get("current_armor")),
        left_ring=_item(case.get("left_ring")),
        right_ring=_item(case.get("right_ring")),
        nearby_monsters=[_monster(monster) for monster in case.get("nearby_monsters", [])],
        create_candidates=case.get("create_candidates", 0),
        food_count=case.get("food_count", 0),
        teleport_room_changed=case.get("teleport_room_changed", False),
        map_cells=[_map_cell(cell) for cell in case.get("map_cells", [])],
        scr_known=case.get("scr_known", [False] * MAXSCROLLS).copy(),
    )
    read_scroll(world, _scroll(case.get("obj")))
    return {"name": case["name"], "seed": case["seed"], "world": world.to_dict()}


def _scroll(payload: dict[str, Any] | None) -> ScrollObject | None:
    if payload is None:
        return None
    return ScrollObject(obj_type=payload.get("type", SCROLL), which=payload.get("which", 0), count=payload.get("count", 1))


def _item(payload: dict[str, Any] | None) -> ScrollItem | None:
    if payload is None:
        return None
    return ScrollItem(
        obj_type=payload.get("type", ARMOR),
        which=payload.get("which", 0),
        flags=payload.get("flags", 0),
        arm=payload.get("arm", 0),
        hplus=payload.get("hplus", 0),
        dplus=payload.get("dplus", 0),
    )


def _monster(payload: dict[str, Any]) -> ScrollMonster:
    return ScrollMonster(monster_type=payload.get("type", "K"), flags=payload.get("flags", 0), oldch=payload.get("oldch", " "))


def _map_cell(payload: dict[str, Any]) -> MapCell:
    return MapCell(ch=payload.get("ch", " "), flags=payload.get("flags", 0), monster=_monster(payload["monster"]) if payload.get("monster") is not None else None)


def _scroll_payload(which: int, count: int = 1) -> dict[str, Any]:
    return {"type": SCROLL, "which": which, "count": count}


def _cases() -> list[dict[str, Any]]:
    return [
        {"name": "non_scroll_rejected", "seed": 1, "obj": {"type": "!", "which": 0}},
        {"name": "confuse_sets_canhuh", "seed": 1, "obj": _scroll_payload(S_CONFUSE)},
        {"name": "armor_enchants_uncurses", "seed": 1, "current_armor": {"type": ARMOR, "arm": 5, "flags": ISCURSED}, "obj": _scroll_payload(S_ARMOR)},
        {"name": "hold_two_monsters", "seed": 1, "nearby_monsters": [{"type": "K", "flags": ISRUN}, {"type": "O", "flags": ISRUN}, {"type": "B", "flags": 0}], "obj": _scroll_payload(S_HOLD)},
        {"name": "hold_none", "seed": 1, "nearby_monsters": [{"type": "K", "flags": 0}], "obj": _scroll_payload(S_HOLD)},
        {"name": "sleep_stops_running", "seed": 1, "player_flags": ISRUN, "no_command": 2, "obj": _scroll_payload(S_SLEEP)},
        {"name": "create_no_space", "seed": 1, "create_candidates": 0, "obj": _scroll_payload(S_CREATE)},
        {"name": "create_selects_space", "seed": 1, "create_candidates": 4, "obj": _scroll_payload(S_CREATE)},
        {"name": "id_potion", "seed": 1, "obj": _scroll_payload(S_ID_POTION)},
        {"name": "id_ring_or_stick", "seed": 1, "obj": _scroll_payload(S_ID_R_OR_S)},
        {
            "name": "magic_map_cells",
            "seed": 1,
            "map_cells": [
                {"ch": DOOR, "flags": 0},
                {"ch": "-", "flags": 0},
                {"ch": " ", "flags": 0},
                {"ch": PASSAGE, "flags": 0},
                {"ch": FLOOR, "flags": 0, "monster": {"type": "K", "flags": 0}},
                {"ch": FLOOR, "flags": F_REAL},
                {"ch": "x", "flags": F_PASS},
            ],
            "obj": _scroll_payload(S_MAP),
        },
        {"name": "food_detect_found", "seed": 1, "food_count": 2, "obj": _scroll_payload(S_FDET)},
        {"name": "food_detect_none", "seed": 1, "food_count": 0, "obj": _scroll_payload(S_FDET)},
        {"name": "teleport_changes_room", "seed": 1, "teleport_room_changed": True, "obj": _scroll_payload(S_TELEP)},
        {"name": "teleport_same_room", "seed": 1, "teleport_room_changed": False, "obj": _scroll_payload(S_TELEP)},
        {"name": "enchant_weapon_hplus", "seed": 1, "current_weapon": {"type": WEAPON, "which": 0, "flags": ISCURSED, "hplus": 0, "dplus": 0}, "obj": _scroll_payload(S_ENCH)},
        {"name": "enchant_no_weapon", "seed": 1, "obj": _scroll_payload(S_ENCH)},
        {"name": "scare_laughter", "seed": 1, "obj": _scroll_payload(S_SCARE)},
        {
            "name": "remove_curse_all",
            "seed": 1,
            "current_armor": {"type": ARMOR, "flags": ISCURSED, "arm": 5},
            "current_weapon": {"type": WEAPON, "flags": ISCURSED, "hplus": 0, "dplus": 0},
            "left_ring": {"type": "=", "flags": ISCURSED},
            "right_ring": {"type": "=", "flags": ISCURSED},
            "obj": _scroll_payload(S_REMOVE),
        },
        {"name": "aggravate", "seed": 1, "obj": _scroll_payload(S_AGGR)},
        {"name": "protect_armor", "seed": 1, "current_armor": {"type": ARMOR, "flags": 0, "arm": 5}, "obj": _scroll_payload(S_PROTECT)},
        {"name": "protect_no_armor", "seed": 1, "obj": _scroll_payload(S_PROTECT)},
        {"name": "unwield_scroll_multi_count", "seed": 1, "current_weapon_is_obj": True, "obj": _scroll_payload(S_CONFUSE, count=2)},
    ]
