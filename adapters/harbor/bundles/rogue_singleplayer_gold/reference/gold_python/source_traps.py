"""Source-faithful Rogue trap consequence slices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from source_rogue import ARMOR, DOOR, PASSAGE, TRAP, WEAPON, RogueRng


F_SEEN = 0x40
F_REAL = 0x10
F_TMASK = 0x07

T_DOOR = 0
T_ARROW = 1
T_SLEEP = 2
T_BEAR = 3
T_TELEP = 4
T_DART = 5
T_RUST = 6
T_MYST = 7

VS_POISON = 0

ISBLIND = 0o000004
ISLEVIT = 0o000010
ISRUN = 0o020000
ISHALU = 0o004000
ISMISL = 0o000004
ISMANY = 0o000010
ISPROT = 0o000040

LEATHER = 0

R_PROTECT = 0
R_ADDSTR = 1
R_SUSTSTR = 2
R_SUSTARM = 13

BOW = 2
ARROW = 3
DAGGER = 4

INIT_WEAPON_FLAGS = [0, 0, 0, ISMANY | ISMISL, ISMISL | ISMISL, 0, ISMANY | ISMISL, ISMANY | ISMISL, ISMISL]
RAINBOW = [
    "amber",
    "aquamarine",
    "black",
    "blue",
    "brown",
    "clear",
    "crimson",
    "cyan",
    "ecru",
    "gold",
    "green",
    "grey",
    "magenta",
    "orange",
    "pink",
    "plaid",
    "purple",
    "red",
    "silver",
    "tan",
    "tangerine",
    "topaz",
    "turquoise",
    "vermilion",
    "violet",
    "white",
    "yellow",
]


@dataclass
class SourceTrapCell:
    ch: str
    flags: int

    def to_dict(self) -> dict[str, Any]:
        return {"ch": self.ch, "flags": self.flags}


@dataclass
class SourceTrapStats:
    strength: int
    max_strength: int
    level: int
    arm: int
    hp: int
    max_hp: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "strength": self.strength,
            "max_strength": self.max_strength,
            "level": self.level,
            "arm": self.arm,
            "hp": self.hp,
            "max_hp": self.max_hp,
        }


@dataclass
class SourceTrapRing:
    which: int
    arm: int

    def to_dict(self) -> dict[str, Any]:
        return {"which": self.which, "arm": self.arm}


@dataclass
class SourceTrapArmor:
    obj_type: str
    which: int
    arm: int
    flags: int

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.obj_type, "which": self.which, "arm": self.arm, "flags": self.flags}


@dataclass
class SourceTrapObject:
    obj_type: str
    which: int
    count: int
    group: int
    flags: int
    y: int
    x: int
    init_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.obj_type,
            "which": self.which,
            "count": self.count,
            "group": self.group,
            "flags": self.flags,
            "y": self.y,
            "x": self.x,
            "init_count": self.init_count,
        }


@dataclass
class SourceTrapState:
    rng: RogueRng
    level: int
    no_move: int
    no_command: int
    player_flags: int
    stats: SourceTrapStats
    cell: SourceTrapCell
    running: bool
    count: bool
    weapon_group: int
    hero_y: int
    hero_x: int
    left_ring: SourceTrapRing | None = None
    right_ring: SourceTrapRing | None = None
    armor: SourceTrapArmor | None = None
    markers: list[str] | None = None
    trace: dict[str, Any] | None = None
    arrow: SourceTrapObject | None = None
    terminal: bool = False

    def __post_init__(self) -> None:
        if self.markers is None:
            self.markers = []
        if self.trace is None:
            self.trace = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "rng_seed": self.rng.seed,
            "level": self.level,
            "no_move": self.no_move,
            "no_command": self.no_command,
            "player_flags": self.player_flags,
            "stats": self.stats.to_dict(),
            "cell": self.cell.to_dict(),
            "running": self.running,
            "count": self.count,
            "weapon_group": self.weapon_group,
            "hero": {"y": self.hero_y, "x": self.hero_x},
            "left_ring": None if self.left_ring is None else self.left_ring.to_dict(),
            "right_ring": None if self.right_ring is None else self.right_ring.to_dict(),
            "armor": None if self.armor is None else self.armor.to_dict(),
            "arrow": None if self.arrow is None else self.arrow.to_dict(),
            "markers": self.markers,
            "trace": self.trace,
            "terminal": self.terminal,
        }


def be_trapped(state: SourceTrapState) -> int | None:
    if state.player_flags & ISLEVIT:
        return T_RUST

    state.running = False
    state.count = False
    state.cell.ch = TRAP
    trap_kind = state.cell.flags & F_TMASK
    state.cell.flags |= F_SEEN

    if trap_kind == T_DOOR:
        state.level += 1
        state.markers.append("new_level")
    elif trap_kind == T_BEAR:
        state.no_move += state.rng.spread(3)
    elif trap_kind == T_MYST:
        mystery_roll = state.rng.rnd(11)
        state.trace["mystery_roll"] = mystery_roll
        if mystery_roll in {1, 4, 6, 10}:
            color_index = state.rng.rnd(len(RAINBOW))
            state.trace["color_index"] = color_index
            state.trace["color"] = RAINBOW[color_index]
    elif trap_kind == T_SLEEP:
        state.no_command += state.rng.spread(5)
        state.player_flags &= ~ISRUN
    elif trap_kind == T_ARROW:
        swing_payload = _swing(state.rng, state.stats.level - 1, state.stats.arm, 1)
        state.trace["arrow_swing"] = swing_payload
        if swing_payload["hit"]:
            damage = state.rng.roll(1, 6)
            state.stats.hp -= damage
            state.trace["arrow_damage"] = damage
            if state.stats.hp <= 0:
                state.markers.append("death_a")
                state.terminal = True
                return None
        else:
            arrow = _init_weapon(state, ARROW)
            arrow.count = 1
            arrow.y = state.hero_y
            arrow.x = state.hero_x
            state.arrow = arrow
            state.markers.append("fall_arrow")
    elif trap_kind == T_TELEP:
        state.markers.append("teleport")
    elif trap_kind == T_DART:
        swing_payload = _swing(state.rng, state.stats.level + 1, state.stats.arm, 1)
        state.trace["dart_swing"] = swing_payload
        if swing_payload["hit"]:
            damage = state.rng.roll(1, 4)
            state.stats.hp -= damage
            state.trace["dart_damage"] = damage
            if state.stats.hp <= 0:
                state.markers.append("death_d")
                state.terminal = True
                return None
            if not _is_wearing(state, R_SUSTSTR):
                save_payload = _save_throw(state.rng, VS_POISON, state.stats.level)
                state.trace["poison_save"] = save_payload
                if not save_payload["saved"]:
                    _chg_str(state, -1)
                    state.markers.append("poison_strength")
    elif trap_kind == T_RUST:
        state.markers.append("rust_armor")
        _rust_armor(state)

    state.markers.append("flush_type")
    return trap_kind


def search_hidden_traps(
    rng: RogueRng,
    traps: list[dict[str, Any]],
    hero_y: int,
    hero_x: int,
    player_flags: int,
    map_cells: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    probinc = 0
    if player_flags & ISHALU:
        probinc += 3
    if player_flags & ISBLIND:
        probinc += 2
    cells = [] if map_cells is None else map_cells
    markers: list[str] = []
    found = False
    for row in range(hero_y - 1, hero_y + 2):
        for col in range(hero_x - 1, hero_x + 2):
            if row == hero_y and col == hero_x:
                continue
            cell = _map_cell_at(cells, row, col)
            if cell is not None and not (int(cell.get("flags", 0)) & F_REAL):
                ch = str(cell.get("ch", " "))[:1] or " "
                if ch in {"|", "-"}:
                    roll = rng.rnd(5 + probinc)
                    markers.append(f"search_cell_roll:{cell['id']}:{roll}")
                    if roll != 0:
                        continue
                    cell["flags"] = int(cell.get("flags", 0)) | F_REAL
                    cell["ch"] = DOOR
                    markers.append(f"search_found_door:{cell['id']}")
                    found = True
                    continue
                if ch == " ":
                    roll = rng.rnd(3 + probinc)
                    markers.append(f"search_cell_roll:{cell['id']}:{roll}")
                    if roll != 0:
                        continue
                    cell["flags"] = int(cell.get("flags", 0)) | F_REAL
                    cell["ch"] = PASSAGE
                    markers.append(f"search_found_passage:{cell['id']}")
                    found = True
                    continue
            trap = _trap_at(traps, row, col)
            if trap is None or int(trap.get("flags", 0)) & F_REAL:
                continue
            roll = rng.rnd(2 + probinc)
            markers.append(f"search_trap_roll:{trap['id']}:{roll}")
            if roll != 0:
                continue
            trap["flags"] = int(trap.get("flags", 0)) | F_REAL | F_SEEN
            trap["ch"] = TRAP
            markers.append(f"search_found_trap:{trap['id']}")
            found = True
    return {
        "rng_seed": rng.seed,
        "found": found,
        "traps": [dict(trap) for trap in traps],
        "map_cells": [dict(cell) for cell in cells],
        "markers": markers,
    }


def source_traps_report() -> dict[str, Any]:
    return {
        "schema": "gamebench.rogue.source_traps.v1",
        "trap_cases": [_run_case(case) for case in _trap_cases()],
        "search_cases": [_run_search_case(case) for case in _search_cases()],
    }


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    state = SourceTrapState(
        rng=RogueRng(case["seed"]),
        level=case.get("level", 1),
        no_move=case.get("no_move", 0),
        no_command=case.get("no_command", 0),
        player_flags=case.get("player_flags", ISRUN),
        stats=SourceTrapStats(**case.get("stats", _stats()).to_dict()),
        cell=SourceTrapCell(TRAP, case.get("flags", F_REAL | case["trap_kind"])),
        running=case.get("running", True),
        count=case.get("count", True),
        weapon_group=case.get("weapon_group", 1),
        hero_y=case.get("hero_y", 10),
        hero_x=case.get("hero_x", 20),
        left_ring=case.get("left_ring"),
        right_ring=case.get("right_ring"),
        armor=case.get("armor"),
    )
    returned = be_trapped(state)
    return {"name": case["name"], "seed": case["seed"], "trap_kind": case["trap_kind"], "returned": returned, "state": state.to_dict()}


def _trap_cases() -> list[dict[str, Any]]:
    return [
        {"name": "levitating_arrow_returns_rust", "seed": 1, "trap_kind": T_ARROW, "player_flags": ISRUN | ISLEVIT},
        {"name": "trapdoor_new_level", "seed": 1, "trap_kind": T_DOOR, "level": 4},
        {"name": "bear_trap_holds", "seed": -17, "trap_kind": T_BEAR, "no_move": 1},
        {"name": "mystery_plain", "seed": -184, "trap_kind": T_MYST},
        {"name": "mystery_color_1", "seed": -178, "trap_kind": T_MYST},
        {"name": "mystery_color_4", "seed": -160, "trap_kind": T_MYST},
        {"name": "mystery_color_6", "seed": -148, "trap_kind": T_MYST},
        {"name": "mystery_color_10", "seed": -190, "trap_kind": T_MYST},
        {"name": "sleep_trap_stops_run", "seed": 7, "trap_kind": T_SLEEP, "no_command": 2},
        {"name": "arrow_hit", "seed": 76, "trap_kind": T_ARROW, "stats": _stats(level=1, arm=6, hp=12)},
        {"name": "arrow_miss_falls", "seed": 1, "trap_kind": T_ARROW, "stats": _stats(level=1, arm=6, hp=12), "weapon_group": 9},
        {"name": "arrow_death", "seed": 76, "trap_kind": T_ARROW, "stats": _stats(level=1, arm=6, hp=1)},
        {"name": "teleport_marker", "seed": 7, "trap_kind": T_TELEP},
        {"name": "dart_miss", "seed": 1, "trap_kind": T_DART, "stats": _stats(level=1, arm=6, hp=12)},
        {"name": "dart_poison_strength", "seed": 64, "trap_kind": T_DART, "stats": _stats(strength=10, max_strength=10, level=1, arm=6, hp=12)},
        {"name": "dart_poison_saved", "seed": 68, "trap_kind": T_DART, "stats": _stats(strength=10, max_strength=10, level=1, arm=6, hp=12)},
        {
            "name": "dart_sustain_strength",
            "seed": 64,
            "trap_kind": T_DART,
            "stats": _stats(strength=10, max_strength=10, level=1, arm=6, hp=12),
            "left_ring": SourceTrapRing(R_SUSTSTR, 0),
        },
        {"name": "rust_armor", "seed": 5, "trap_kind": T_RUST, "armor": SourceTrapArmor(ARMOR, 1, 4, 0)},
        {"name": "rust_protected_armor", "seed": 5, "trap_kind": T_RUST, "armor": SourceTrapArmor(ARMOR, 1, 4, ISPROT)},
        {"name": "rust_sustain_armor", "seed": 5, "trap_kind": T_RUST, "armor": SourceTrapArmor(ARMOR, 1, 4, 0), "right_ring": SourceTrapRing(R_SUSTARM, 0)},
    ]


def _run_search_case(case: dict[str, Any]) -> dict[str, Any]:
    traps = [dict(trap) for trap in case["traps"]]
    cells = [dict(cell) for cell in case.get("map_cells", [])]
    result = search_hidden_traps(RogueRng(case["seed"]), traps, case.get("hero_y", 2), case.get("hero_x", 3), case.get("player_flags", 0), cells)
    return {"name": case["name"], "seed": case["seed"], "result": result}


def _search_cases() -> list[dict[str, Any]]:
    return [
        {"name": "search_hidden_trap_found", "seed": 1, "traps": [_search_trap("hidden_arrow", T_ARROW, 2, 4, T_ARROW)]},
        {"name": "search_hidden_trap_missed", "seed": 5, "traps": [_search_trap("hidden_bear", T_BEAR, 2, 4, T_BEAR)]},
        {"name": "search_ignores_real_trap", "seed": 1, "traps": [_search_trap("real_arrow", T_ARROW, 2, 4, F_REAL | T_ARROW)]},
        {"name": "search_secret_door_found", "seed": 1, "traps": [], "map_cells": [_search_cell("secret_door", "|", 2, 4, 0)]},
        {"name": "search_hidden_passage_found", "seed": 1, "traps": [], "map_cells": [_search_cell("hidden_passage", " ", 2, 4, 0)]},
        {"name": "search_secret_door_missed", "seed": 5, "traps": [], "map_cells": [_search_cell("missed_door", "-", 2, 4, 0)]},
    ]


def _search_trap(trap_id: str, kind: int, row: int, col: int, flags: int) -> dict[str, Any]:
    return {"id": trap_id, "row": row, "col": col, "kind": kind, "flags": flags, "ch": "^", "weapon_group": 1}


def _search_cell(cell_id: str, ch: str, row: int, col: int, flags: int) -> dict[str, Any]:
    return {"id": cell_id, "row": row, "col": col, "ch": ch, "flags": flags}


def _trap_at(traps: list[dict[str, Any]], row: int, col: int) -> dict[str, Any] | None:
    for trap in traps:
        if int(trap.get("row", -1)) == row and int(trap.get("col", -1)) == col:
            return trap
    return None


def _map_cell_at(cells: list[dict[str, Any]], row: int, col: int) -> dict[str, Any] | None:
    for cell in cells:
        if int(cell.get("row", -1)) == row and int(cell.get("col", -1)) == col:
            return cell
    return None


def _stats(strength: int = 16, max_strength: int = 16, level: int = 1, arm: int = 6, hp: int = 12, max_hp: int = 12) -> SourceTrapStats:
    return SourceTrapStats(strength=strength, max_strength=max_strength, level=level, arm=arm, hp=hp, max_hp=max_hp)


def _swing(rng: RogueRng, at_lvl: int, op_arm: int, wplus: int) -> dict[str, Any]:
    result = rng.rnd(20)
    need = (20 - at_lvl) - op_arm
    return {"roll": result, "need": need, "hit": result + wplus >= need, "rng_seed": rng.seed}


def _save_throw(rng: RogueRng, which: int, level: int) -> dict[str, Any]:
    need = 14 + which - level // 2
    roll = rng.roll(1, 20)
    return {"which": which, "level": level, "need": need, "roll": roll, "saved": roll >= need, "rng_seed": rng.seed}


def _init_weapon(state: SourceTrapState, which: int) -> SourceTrapObject:
    flags = INIT_WEAPON_FLAGS[which]
    init_count = 1
    group = 0
    if which == DAGGER:
        init_count = state.rng.rnd(4) + 2
        group = state.weapon_group
        state.weapon_group += 1
    elif flags & ISMANY:
        init_count = state.rng.rnd(8) + 8
        group = state.weapon_group
        state.weapon_group += 1
    return SourceTrapObject(WEAPON, which, init_count, group, flags, 0, 0, init_count)


def _is_wearing(state: SourceTrapState, ring_kind: int) -> bool:
    return (state.left_ring is not None and state.left_ring.which == ring_kind) or (state.right_ring is not None and state.right_ring.which == ring_kind)


def _chg_str(state: SourceTrapState, amount: int) -> None:
    state.stats.strength = max(3, min(31, state.stats.strength + amount))
    comparable = state.stats.strength
    if state.left_ring is not None and state.left_ring.which == R_ADDSTR:
        comparable = max(3, min(31, comparable - state.left_ring.arm))
    if state.right_ring is not None and state.right_ring.which == R_ADDSTR:
        comparable = max(3, min(31, comparable - state.right_ring.arm))
    if comparable > state.stats.max_strength:
        state.stats.max_strength = comparable


def _rust_armor(state: SourceTrapState) -> None:
    armor = state.armor
    if armor is None or armor.obj_type != ARMOR or armor.which == LEATHER or armor.arm >= 9:
        return
    if armor.flags & ISPROT or _is_wearing(state, R_SUSTARM):
        state.markers.append("rust_vanishes")
        return
    armor.arm += 1
    state.markers.append("armor_weakened")
