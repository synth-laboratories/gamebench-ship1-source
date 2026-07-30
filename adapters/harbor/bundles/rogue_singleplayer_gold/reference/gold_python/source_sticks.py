"""Source-faithful Rogue stick and wand behavior slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_rogue import STICK, RogueRng


ISGONE = 0o000002

CANHUH = 0o000001
ISCANC = 0o000010
ISHASTE = 0o000100
ISHELD = 0o000400
ISINVIS = 0o002000
ISRUN = 0o020000
ISSLOW = 0o100000

ISMISL = 0o000004
ISKNOW = 0o000002

WS_LIGHT = 0
WS_INVIS = 1
WS_ELECT = 2
WS_FIRE = 3
WS_COLD = 4
WS_POLYMORPH = 5
WS_MISSILE = 6
WS_HASTE_M = 7
WS_SLOW_M = 8
WS_DRAIN = 9
WS_NOP = 10
WS_TELAWAY = 11
WS_TELTO = 12
WS_CANCEL = 13
MAXSTICKS = 14


@dataclass
class StickObject:
    obj_type: str
    which: int
    charges: int = 0
    flags: int = 0
    damage: str = ""
    hurldmg: str = ""
    hplus: int = 0
    dplus: int = 0
    launch: int = -1
    is_staff: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.obj_type,
            "which": self.which,
            "charges": self.charges,
            "flags": self.flags,
            "damage": self.damage,
            "hurldmg": self.hurldmg,
            "hplus": self.hplus,
            "dplus": self.dplus,
            "launch": self.launch,
            "is_staff": self.is_staff,
        }


@dataclass
class StickMonster:
    monster_type: str
    hp: int
    flags: int = 0
    disguise: str | None = None
    oldch: str = "."
    pack_count: int = 0
    turn: bool = False
    dest_hero: bool = False
    visible: bool = True
    cansee: bool = True
    same_room: bool = True
    at_door_to_room: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.monster_type,
            "hp": self.hp,
            "flags": self.flags,
            "disguise": self.disguise,
            "oldch": self.oldch,
            "pack_count": self.pack_count,
            "turn": self.turn,
            "dest_hero": self.dest_hero,
            "visible": self.visible,
            "cansee": self.cansee,
        }


@dataclass
class StickWorld:
    rng: RogueRng
    after: bool = True
    player_flags: int = 0
    hero_hp: int = 12
    proom_flags: int = 0
    current_weapon_which: int | None = None
    target: StickMonster | None = None
    drain_monsters: list[StickMonster] = field(default_factory=list)
    save_throw_success: bool = False
    ws_known: list[bool] = field(default_factory=lambda: [False] * MAXSTICKS)
    markers: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, obj: StickObject | None = None) -> dict[str, Any]:
        return {
            "rng_seed": self.rng.seed,
            "after": self.after,
            "player_flags": self.player_flags,
            "hero_hp": self.hero_hp,
            "proom_flags": self.proom_flags,
            "current_weapon_which": self.current_weapon_which,
            "object": obj.to_dict() if obj is not None else None,
            "target": self.target.to_dict() if self.target is not None else None,
            "drain_monsters": [monster.to_dict() for monster in self.drain_monsters],
            "ws_known": self.ws_known,
            "markers": self.markers,
            "trace": self.trace,
        }


def fix_stick(world: StickWorld, obj: StickObject) -> None:
    obj.damage = "2x3" if obj.is_staff else "1x1"
    obj.hurldmg = "1x1"
    if obj.which == WS_LIGHT:
        obj.charges = world.rng.rnd(10) + 10
    else:
        obj.charges = world.rng.rnd(5) + 3
    world.trace["charges"] = obj.charges


def do_zap(world: StickWorld, obj: StickObject | None) -> None:
    if obj is None:
        return
    if obj.obj_type != STICK:
        world.after = False
        world.markers.append("cant_zap")
        return
    if obj.charges == 0:
        world.markers.append("nothing_happens")
        return
    which = obj.which
    if which == WS_LIGHT:
        world.ws_known[WS_LIGHT] = True
        if world.proom_flags & ISGONE:
            world.markers.append("corridor_glows")
        else:
            world.proom_flags &= ~ISGONE
            world.markers.append("enter_room")
            world.markers.append("room_lit")
    elif which == WS_DRAIN:
        if world.hero_hp < 2:
            world.markers.append("too_weak")
            return
        drain(world)
    elif which in {WS_INVIS, WS_POLYMORPH, WS_TELAWAY, WS_TELTO, WS_CANCEL}:
        zap_target_effect(world, obj)
    elif which == WS_MISSILE:
        world.ws_known[WS_MISSILE] = True
        world.trace["missile_launch"] = world.current_weapon_which
        if world.target is not None and not world.save_throw_success:
            world.markers.append("hit_monster:missile")
        elif world.target is not None:
            world.markers.append("missile_misses")
        else:
            world.markers.append("missile_vanishes")
    elif which in {WS_HASTE_M, WS_SLOW_M}:
        if world.target is not None:
            if which == WS_HASTE_M:
                if world.target.flags & ISSLOW:
                    world.target.flags &= ~ISSLOW
                else:
                    world.target.flags |= ISHASTE
            else:
                if world.target.flags & ISHASTE:
                    world.target.flags &= ~ISHASTE
                else:
                    world.target.flags |= ISSLOW
                world.target.turn = True
            world.markers.append("runto")
    elif which in {WS_ELECT, WS_FIRE, WS_COLD}:
        name = "bolt" if which == WS_ELECT else "flame" if which == WS_FIRE else "ice"
        fire_bolt(world, name)
        world.ws_known[which] = True
    elif which == WS_NOP:
        pass
    else:
        world.markers.append("bizarre_schtick")
    obj.charges -= 1


def zap_target_effect(world: StickWorld, obj: StickObject) -> None:
    monster = world.target
    if monster is None:
        return
    if monster.monster_type == "F":
        world.player_flags &= ~ISHELD
    if obj.which == WS_INVIS:
        monster.flags |= ISINVIS
        if monster.cansee:
            world.markers.append("draw_oldch")
    elif obj.which == WS_POLYMORPH:
        oldch = monster.oldch
        pack_count = monster.pack_count
        if monster.visible:
            world.markers.append("erase_monster")
        monster.monster_type = chr(world.rng.rnd(26) + ord("A"))
        monster.oldch = oldch
        monster.pack_count = pack_count
        world.trace["polymorph_type"] = monster.monster_type
        if monster.visible:
            world.markers.append("draw_new_monster")
            world.ws_known[WS_POLYMORPH] = True
    elif obj.which == WS_CANCEL:
        monster.flags |= ISCANC
        monster.flags &= ~(ISINVIS | CANHUH)
        monster.disguise = monster.monster_type
        if monster.visible:
            world.markers.append("draw_disguise")
    elif obj.which in {WS_TELAWAY, WS_TELTO}:
        monster.dest_hero = True
        monster.flags |= ISRUN
        if obj.which == WS_TELAWAY:
            world.markers.append("relocate:random_floor")
        else:
            world.markers.append("relocate:adjacent")


def drain(world: StickWorld) -> None:
    monsters = world.drain_monsters
    if not monsters:
        world.markers.append("tingling")
        return
    world.hero_hp //= 2
    amount = world.hero_hp // len(monsters)
    world.trace["drain_amount"] = amount
    for monster in monsters:
        monster.hp -= amount
        if monster.hp <= 0:
            world.markers.append(f"killed:{monster.monster_type}")
        else:
            world.markers.append(f"runto:{monster.monster_type}")


def fire_bolt(world: StickWorld, name: str) -> None:
    world.markers.append(f"fire_bolt:{name}")


def charge_str(obj: StickObject, terse: bool) -> str:
    if not (obj.flags & ISKNOW):
        return ""
    if terse:
        return f" [{obj.charges}]"
    return f" [{obj.charges} charges]"


def source_sticks_report() -> dict[str, Any]:
    return {"schema": "gamebench.rogue.source_sticks.v1", "cases": [_run_case(case) for case in _cases()]}


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    world = StickWorld(
        rng=RogueRng(case["seed"]),
        after=case.get("after", True),
        player_flags=case.get("player_flags", 0),
        hero_hp=case.get("hero_hp", 12),
        proom_flags=case.get("proom_flags", 0),
        current_weapon_which=case.get("current_weapon_which"),
        target=_monster(case.get("target")),
        drain_monsters=[_monster(monster) for monster in case.get("drain_monsters", []) if _monster(monster) is not None],
        save_throw_success=case.get("save_throw_success", False),
    )
    obj = _stick(case.get("obj"))
    result: Any = None
    if case["op"] == "fix_stick":
        if obj is not None:
            fix_stick(world, obj)
    elif case["op"] == "do_zap":
        do_zap(world, obj)
    elif case["op"] == "charge_str":
        result = charge_str(obj or StickObject(STICK, WS_NOP), case.get("terse", False))
    else:
        raise ValueError(case["op"])
    return {"name": case["name"], "seed": case["seed"], "result": result, "world": world.to_dict(obj)}


def _stick(payload: dict[str, Any] | None) -> StickObject | None:
    if payload is None:
        return None
    return StickObject(
        obj_type=payload.get("type", STICK),
        which=payload.get("which", WS_NOP),
        charges=payload.get("charges", 0),
        flags=payload.get("flags", 0),
        damage=payload.get("damage", ""),
        hurldmg=payload.get("hurldmg", ""),
        hplus=payload.get("hplus", 0),
        dplus=payload.get("dplus", 0),
        launch=payload.get("launch", -1),
        is_staff=payload.get("is_staff", False),
    )


def _monster(payload: dict[str, Any] | None) -> StickMonster | None:
    if payload is None:
        return None
    return StickMonster(
        monster_type=payload.get("type", "K"),
        hp=payload.get("hp", 8),
        flags=payload.get("flags", 0),
        disguise=payload.get("disguise"),
        oldch=payload.get("oldch", "."),
        pack_count=payload.get("pack_count", 0),
        turn=payload.get("turn", False),
        dest_hero=payload.get("dest_hero", False),
        visible=payload.get("visible", True),
        cansee=payload.get("cansee", True),
        same_room=payload.get("same_room", True),
        at_door_to_room=payload.get("at_door_to_room", False),
    )


def _stick_payload(which: int, charges: int = 1, **extra: Any) -> dict[str, Any]:
    payload = {"type": STICK, "which": which, "charges": charges}
    payload.update(extra)
    return payload


def _cases() -> list[dict[str, Any]]:
    return [
        {"name": "fix_light_wand", "seed": 1, "op": "fix_stick", "obj": _stick_payload(WS_LIGHT, is_staff=False)},
        {"name": "fix_staff_nonlight", "seed": 1, "op": "fix_stick", "obj": _stick_payload(WS_FIRE, is_staff=True)},
        {"name": "zap_non_stick", "seed": 1, "op": "do_zap", "obj": {"type": "!", "which": WS_LIGHT, "charges": 1}},
        {"name": "zap_empty", "seed": 1, "op": "do_zap", "obj": _stick_payload(WS_LIGHT, charges=0)},
        {"name": "light_room", "seed": 1, "op": "do_zap", "proom_flags": 0, "obj": _stick_payload(WS_LIGHT, charges=2)},
        {"name": "light_corridor", "seed": 1, "op": "do_zap", "proom_flags": ISGONE, "obj": _stick_payload(WS_LIGHT, charges=2)},
        {"name": "drain_too_weak", "seed": 1, "op": "do_zap", "hero_hp": 1, "obj": _stick_payload(WS_DRAIN, charges=2)},
        {"name": "drain_no_monsters", "seed": 1, "op": "do_zap", "hero_hp": 12, "obj": _stick_payload(WS_DRAIN, charges=2)},
        {"name": "drain_hits_monsters", "seed": 1, "op": "do_zap", "hero_hp": 20, "drain_monsters": [{"type": "K", "hp": 4}, {"type": "O", "hp": 10}], "obj": _stick_payload(WS_DRAIN, charges=2)},
        {"name": "invis_flytrap_unholds", "seed": 1, "op": "do_zap", "player_flags": ISHELD, "target": {"type": "F", "hp": 8}, "obj": _stick_payload(WS_INVIS, charges=2)},
        {"name": "polymorph_visible", "seed": 1, "op": "do_zap", "target": {"type": "K", "hp": 8, "oldch": ".", "pack_count": 2, "visible": True}, "obj": _stick_payload(WS_POLYMORPH, charges=2)},
        {"name": "cancel_invisible_confuser", "seed": 1, "op": "do_zap", "target": {"type": "M", "hp": 8, "flags": ISINVIS | CANHUH}, "obj": _stick_payload(WS_CANCEL, charges=2)},
        {"name": "telaway_sets_run", "seed": 1, "op": "do_zap", "target": {"type": "K", "hp": 8}, "obj": _stick_payload(WS_TELAWAY, charges=2)},
        {"name": "telto_sets_run", "seed": 1, "op": "do_zap", "target": {"type": "K", "hp": 8}, "obj": _stick_payload(WS_TELTO, charges=2)},
        {"name": "missile_hits", "seed": 1, "op": "do_zap", "current_weapon_which": 3, "target": {"type": "K", "hp": 8}, "save_throw_success": False, "obj": _stick_payload(WS_MISSILE, charges=2)},
        {"name": "missile_misses", "seed": 1, "op": "do_zap", "target": {"type": "K", "hp": 8}, "save_throw_success": True, "obj": _stick_payload(WS_MISSILE, charges=2)},
        {"name": "haste_clears_slow", "seed": 1, "op": "do_zap", "target": {"type": "K", "hp": 8, "flags": ISSLOW}, "obj": _stick_payload(WS_HASTE_M, charges=2)},
        {"name": "haste_sets_haste", "seed": 1, "op": "do_zap", "target": {"type": "K", "hp": 8}, "obj": _stick_payload(WS_HASTE_M, charges=2)},
        {"name": "slow_clears_haste", "seed": 1, "op": "do_zap", "target": {"type": "K", "hp": 8, "flags": ISHASTE}, "obj": _stick_payload(WS_SLOW_M, charges=2)},
        {"name": "slow_sets_slow_turn", "seed": 1, "op": "do_zap", "target": {"type": "K", "hp": 8}, "obj": _stick_payload(WS_SLOW_M, charges=2)},
        {"name": "fire_bolt", "seed": 1, "op": "do_zap", "obj": _stick_payload(WS_FIRE, charges=2)},
        {"name": "cold_bolt", "seed": 1, "op": "do_zap", "obj": _stick_payload(WS_COLD, charges=2)},
        {"name": "nop_consumes_charge", "seed": 1, "op": "do_zap", "obj": _stick_payload(WS_NOP, charges=2)},
        {"name": "charge_unknown", "seed": 1, "op": "charge_str", "obj": _stick_payload(WS_LIGHT, charges=7, flags=0)},
        {"name": "charge_known_verbose", "seed": 1, "op": "charge_str", "obj": _stick_payload(WS_LIGHT, charges=7, flags=ISKNOW), "terse": False},
        {"name": "charge_known_terse", "seed": 1, "op": "charge_str", "obj": _stick_payload(WS_LIGHT, charges=7, flags=ISKNOW), "terse": True},
    ]
