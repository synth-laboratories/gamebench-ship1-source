"""Source-faithful Rogue potion behavior slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_rogue import ARMOR, AMULET, POTION, RING, SCROLL, STICK, WEAPON, RogueRng


BEFORE = 1
AFTER = 2
DAEMON = -1

HEALTIME = 30
HUHDURATION = 20
SEEDURATION = 850

ISCURSED = 0o000001
ISKNOW = 0o000002
ISPROT = 0o000040

CANSEE = 0o000002
ISBLIND = 0o000004
ISLEVIT = 0o000010
ISHASTE = 0o000100
ISHUH = 0o001000
ISHALU = 0o004000
ISRUN = 0o020000
SEEMONST = 0o040000

P_CONFUSE = 0
P_LSD = 1
P_POISON = 2
P_STRENGTH = 3
P_SEEINVIS = 4
P_HEALING = 5
P_MFIND = 6
P_TFIND = 7
P_RAISE = 8
P_XHEAL = 9
P_HASTE = 10
P_RESTORE = 11
P_BLIND = 12
P_LEVIT = 13
MAXPOTIONS = 14

R_ADDSTR = 1
R_SUSTSTR = 2

E_LEVELS = [10, 20, 40, 80, 160, 320, 640, 1300, 2600, 5200, 13000, 26000, 50000, 100000, 200000, 400000, 800000, 2000000, 4000000, 8000000, 0]
A_CLASS = [8, 7, 7, 6, 5, 4, 4, 3]


@dataclass
class PotionObject:
    obj_id: str
    obj_type: str
    which: int
    count: int = 1
    flags: int = 0
    arm: int = 0
    hplus: int = 0
    dplus: int = 0


@dataclass
class SourceRing:
    which: int
    arm: int = 0


@dataclass
class DelayedAction:
    action: str
    action_type: int
    arg: int
    time: int

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "type": self.action_type, "arg": self.arg, "time": self.time}


@dataclass
class PotionWorld:
    rng: RogueRng
    player_flags: int = 0
    strength: int = 16
    max_strength: int = 16
    level: int = 5
    exp: int = 100
    hp: int = 12
    max_hp: int = 20
    no_command: int = 0
    after: bool = True
    current_weapon_is_obj: bool = False
    left_ring: SourceRing | None = None
    right_ring: SourceRing | None = None
    pot_known: list[bool] = field(default_factory=lambda: [False] * MAXPOTIONS)
    actions: list[DelayedAction] = field(default_factory=list)
    magic_count: int = 0
    new_monsters: int = 0
    invisible_visible: int = 0
    stairs_visible: bool = False
    seenstairs: bool = False
    proom_gone: bool = False
    markers: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rng_seed": self.rng.seed,
            "player_flags": self.player_flags,
            "strength": self.strength,
            "max_strength": self.max_strength,
            "level": self.level,
            "exp": self.exp,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "no_command": self.no_command,
            "after": self.after,
            "current_weapon_is_obj": self.current_weapon_is_obj,
            "pot_known": self.pot_known,
            "actions": [action.to_dict() for action in self.actions],
            "seenstairs": self.seenstairs,
            "markers": self.markers,
            "trace": self.trace,
        }


def quaff(world: PotionWorld, obj: PotionObject | None) -> None:
    if obj is None:
        return
    if obj.obj_type != POTION:
        world.markers.append("undrinkable")
        return
    if world.current_weapon_is_obj:
        world.current_weapon_is_obj = False
        world.markers.append("unwield_potion")
    trip = bool(world.player_flags & ISHALU)
    discardit = obj.count == 1
    world.markers.append("leave_pack")
    which = obj.which
    if which == P_CONFUSE:
        do_pot(world, P_CONFUSE, not trip)
    elif which == P_POISON:
        world.pot_known[P_POISON] = True
        if is_wearing(world, R_SUSTSTR):
            world.markers.append("msg_momentarily_sick")
        else:
            loss = world.rng.rnd(3) + 1
            world.trace["poison_loss"] = loss
            chg_str(world, -loss)
            world.markers.append("msg_very_sick")
            come_down(world)
    elif which == P_HEALING:
        world.pot_known[P_HEALING] = True
        heal = world.rng.roll(world.level, 4)
        world.trace["heal_roll"] = heal
        world.hp += heal
        if world.hp > world.max_hp:
            world.max_hp += 1
            world.hp = world.max_hp
        sight(world)
        world.markers.append("msg_better")
    elif which == P_STRENGTH:
        world.pot_known[P_STRENGTH] = True
        chg_str(world, 1)
        world.markers.append("msg_stronger")
    elif which == P_MFIND:
        world.player_flags |= SEEMONST
        fuse(world, "turn_see", 1, HUHDURATION, AFTER)
        if not turn_see(world, False):
            world.markers.append("msg_monster_fleeting")
    elif which == P_TFIND:
        if world.magic_count > 0:
            world.pot_known[P_TFIND] = True
            world.markers.append(f"show_magic:{world.magic_count}")
            world.markers.append("show_win_magic")
        else:
            world.markers.append("msg_magic_fleeting")
    elif which == P_LSD:
        if not trip:
            if world.player_flags & SEEMONST:
                turn_see(world, False)
            start_daemon(world, "visuals", 0, BEFORE)
            world.seenstairs = world.stairs_visible
        do_pot(world, P_LSD, True)
    elif which == P_SEEINVIS:
        show = bool(world.player_flags & CANSEE)
        do_pot(world, P_SEEINVIS, False)
        if not show:
            invis_on(world)
        sight(world)
    elif which == P_RAISE:
        world.pot_known[P_RAISE] = True
        world.markers.append("msg_raise")
        raise_level(world)
    elif which == P_XHEAL:
        world.pot_known[P_XHEAL] = True
        heal = world.rng.roll(world.level, 8)
        world.trace["xheal_roll"] = heal
        world.hp += heal
        if world.hp > world.max_hp:
            if world.hp > world.max_hp + world.level + 1:
                world.max_hp += 1
            world.max_hp += 1
            world.hp = world.max_hp
        sight(world)
        come_down(world)
        world.markers.append("msg_much_better")
    elif which == P_HASTE:
        world.pot_known[P_HASTE] = True
        world.after = False
        if add_haste(world, True):
            world.markers.append("msg_much_faster")
    elif which == P_RESTORE:
        restore_strength(world)
        world.markers.append("msg_restore")
    elif which == P_BLIND:
        do_pot(world, P_BLIND, True)
    elif which == P_LEVIT:
        do_pot(world, P_LEVIT, True)
    else:
        world.markers.append("odd_tasting")
        return
    world.markers.append("status")
    world.markers.append(f"call_it:{which}")
    if discardit:
        world.markers.append("discard")


def is_magic(obj: PotionObject) -> bool:
    if obj.obj_type == ARMOR:
        base = A_CLASS[obj.which] if 0 <= obj.which < len(A_CLASS) else obj.arm
        return bool(obj.flags & ISPROT) or obj.arm != base
    if obj.obj_type == WEAPON:
        return obj.hplus != 0 or obj.dplus != 0
    return obj.obj_type in {POTION, SCROLL, STICK, RING, AMULET}


def do_pot(world: PotionWorld, potion_type: int, knowit: bool) -> None:
    action = potion_action(potion_type)
    if not world.pot_known[potion_type]:
        world.pot_known[potion_type] = knowit
    duration = world.rng.spread(action["time"])
    if not (world.player_flags & action["flag"]):
        world.player_flags |= action["flag"]
        fuse(world, action["daemon"], 0, duration, AFTER)
        world.markers.append("look:false")
    else:
        lengthen(world, action["daemon"], duration)
    world.trace[f"duration_{potion_type}"] = duration
    world.markers.append(f"msg_pot:{potion_type}")


def potion_action(potion_type: int) -> dict[str, Any]:
    table = {
        P_CONFUSE: {"flag": ISHUH, "daemon": "unconfuse", "time": HUHDURATION},
        P_LSD: {"flag": ISHALU, "daemon": "come_down", "time": SEEDURATION},
        P_SEEINVIS: {"flag": CANSEE, "daemon": "unsee", "time": SEEDURATION},
        P_BLIND: {"flag": ISBLIND, "daemon": "sight", "time": SEEDURATION},
        P_LEVIT: {"flag": ISLEVIT, "daemon": "land", "time": HEALTIME},
    }
    return table[potion_type]


def invis_on(world: PotionWorld) -> None:
    world.player_flags |= CANSEE
    for _ in range(world.invisible_visible):
        world.markers.append("draw_invisible")


def turn_see(world: PotionWorld, turn_off: bool) -> bool:
    if turn_off:
        world.player_flags &= ~SEEMONST
        world.markers.append("turn_see:off")
        return False
    hallu: list[str] = []
    for _ in range(world.new_monsters):
        if world.player_flags & ISHALU:
            hallu.append(chr(world.rng.rnd(26) + ord("A")))
    if hallu:
        world.trace["turn_see_hallu"] = hallu
    world.player_flags |= SEEMONST
    world.markers.append(f"turn_see:on:{world.new_monsters}")
    return world.new_monsters != 0


def sight(world: PotionWorld) -> None:
    if world.player_flags & ISBLIND:
        extinguish(world, "sight")
        world.player_flags &= ~ISBLIND
        if not world.proom_gone:
            world.markers.append("enter_room")
        world.markers.append("msg_sight")


def come_down(world: PotionWorld) -> None:
    if not (world.player_flags & ISHALU):
        return
    kill_daemon(world, "visuals")
    world.player_flags &= ~ISHALU
    world.markers.append("come_down")
    if world.player_flags & ISBLIND:
        return
    world.markers.append("redraw_after_hallu")


def raise_level(world: PotionWorld) -> None:
    world.exp = E_LEVELS[world.level - 1] + 1
    check_level(world)


def check_level(world: PotionWorld) -> None:
    next_level = 1
    for threshold in E_LEVELS:
        if threshold == 0 or threshold > world.exp:
            break
        next_level += 1
    old_level = world.level
    world.level = next_level
    if next_level > old_level:
        add = world.rng.roll(next_level - old_level, 10)
        world.max_hp += add
        world.hp += add
        world.trace["level_add"] = add
        world.markers.append(f"welcome:{next_level}")


def add_haste(world: PotionWorld, potion: bool) -> bool:
    if world.player_flags & ISHASTE:
        faint = world.rng.rnd(8)
        world.trace["haste_faint"] = faint
        world.no_command += faint
        world.player_flags &= ~(ISRUN | ISHASTE)
        extinguish(world, "nohaste")
        world.markers.append("msg_faint_exhaustion")
        return False
    world.player_flags |= ISHASTE
    if potion:
        duration = world.rng.rnd(4) + 4
        world.trace["haste_duration"] = duration
        fuse(world, "nohaste", 0, duration, AFTER)
    return True


def restore_strength(world: PotionWorld) -> None:
    if is_ring(world.left_ring, R_ADDSTR):
        world.strength = add_str(world.strength, -world.left_ring.arm)
    if is_ring(world.right_ring, R_ADDSTR):
        world.strength = add_str(world.strength, -world.right_ring.arm)
    if world.strength < world.max_strength:
        world.strength = world.max_strength
    if is_ring(world.left_ring, R_ADDSTR):
        world.strength = add_str(world.strength, world.left_ring.arm)
    if is_ring(world.right_ring, R_ADDSTR):
        world.strength = add_str(world.strength, world.right_ring.arm)


def chg_str(world: PotionWorld, amount: int) -> None:
    if amount == 0:
        return
    world.strength = add_str(world.strength, amount)
    comp = world.strength
    if is_ring(world.left_ring, R_ADDSTR):
        comp = add_str(comp, -world.left_ring.arm)
    if is_ring(world.right_ring, R_ADDSTR):
        comp = add_str(comp, -world.right_ring.arm)
    if comp > world.max_strength:
        world.max_strength = comp


def add_str(value: int, amount: int) -> int:
    value += amount
    if value < 3:
        return 3
    if value > 31:
        return 31
    return value


def is_wearing(world: PotionWorld, which: int) -> bool:
    return is_ring(world.left_ring, which) or is_ring(world.right_ring, which)


def is_ring(ring: SourceRing | None, which: int) -> bool:
    return ring is not None and ring.which == which


def fuse(world: PotionWorld, action: str, arg: int, time: int, action_type: int) -> None:
    world.actions.append(DelayedAction(action, action_type, arg, time))


def start_daemon(world: PotionWorld, action: str, arg: int, action_type: int) -> None:
    world.actions.append(DelayedAction(action, action_type, arg, DAEMON))


def kill_daemon(world: PotionWorld, action: str) -> None:
    for index, delayed in enumerate(world.actions):
        if delayed.action == action:
            world.actions.pop(index)
            return


def lengthen(world: PotionWorld, action: str, extra_time: int) -> None:
    for delayed in world.actions:
        if delayed.action == action:
            delayed.time += extra_time
            return


def extinguish(world: PotionWorld, action: str) -> None:
    for index, delayed in enumerate(world.actions):
        if delayed.action == action:
            world.actions.pop(index)
            return


def source_potions_report() -> dict[str, Any]:
    return {"schema": "gamebench.rogue.source_potions.v1", "cases": [_run_case(case) for case in _cases()]}


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    world = PotionWorld(
        rng=RogueRng(case["seed"]),
        player_flags=case.get("player_flags", 0),
        strength=case.get("strength", 16),
        max_strength=case.get("max_strength", 16),
        level=case.get("level", 5),
        exp=case.get("exp", 100),
        hp=case.get("hp", 12),
        max_hp=case.get("max_hp", 20),
        no_command=case.get("no_command", 0),
        after=case.get("after", True),
        current_weapon_is_obj=case.get("current_weapon_is_obj", False),
        left_ring=_ring(case.get("left_ring")),
        right_ring=_ring(case.get("right_ring")),
        pot_known=case.get("pot_known", [False] * MAXPOTIONS).copy(),
        actions=[DelayedAction(**action) for action in case.get("actions", [])],
        magic_count=case.get("magic_count", 0),
        new_monsters=case.get("new_monsters", 0),
        invisible_visible=case.get("invisible_visible", 0),
        stairs_visible=case.get("stairs_visible", False),
        seenstairs=case.get("seenstairs", False),
        proom_gone=case.get("proom_gone", False),
    )
    result: Any = None
    if case["op"] == "quaff":
        quaff(world, _object(case.get("obj")))
    elif case["op"] == "is_magic":
        result = is_magic(_object(case["obj"]) or PotionObject("none", " ", 0))
    else:
        raise ValueError(case["op"])
    return {"name": case["name"], "seed": case["seed"], "result": result, "world": world.to_dict()}


def _object(payload: dict[str, Any] | None) -> PotionObject | None:
    if payload is None:
        return None
    return PotionObject(
        obj_id=payload.get("id", "obj"),
        obj_type=payload.get("type", POTION),
        which=payload.get("which", 0),
        count=payload.get("count", 1),
        flags=payload.get("flags", 0),
        arm=payload.get("arm", 0),
        hplus=payload.get("hplus", 0),
        dplus=payload.get("dplus", 0),
    )


def _ring(payload: dict[str, Any] | None) -> SourceRing | None:
    if payload is None:
        return None
    return SourceRing(which=payload.get("which", 0), arm=payload.get("arm", 0))


def _potion(which: int, count: int = 1) -> dict[str, Any]:
    return {"id": f"p{which}", "type": POTION, "which": which, "count": count}


def _known(*indices: int) -> list[bool]:
    known = [False] * MAXPOTIONS
    for index in indices:
        known[index] = True
    return known


def _cases() -> list[dict[str, Any]]:
    return [
        {"name": "quaff_non_potion_rejected", "seed": 1, "op": "quaff", "obj": {"id": "food", "type": ":", "which": 0}},
        {"name": "confuse_new", "seed": 1, "op": "quaff", "obj": _potion(P_CONFUSE)},
        {"name": "confuse_lengthens", "seed": 1, "op": "quaff", "player_flags": ISHUH, "actions": [{"action": "unconfuse", "action_type": AFTER, "arg": 0, "time": 5}], "obj": _potion(P_CONFUSE)},
        {"name": "poison_sustained", "seed": 1, "op": "quaff", "left_ring": {"which": R_SUSTSTR}, "obj": _potion(P_POISON)},
        {"name": "poison_strength_loss_come_down", "seed": 1, "op": "quaff", "player_flags": ISHALU, "strength": 16, "actions": [{"action": "visuals", "action_type": BEFORE, "arg": 0, "time": DAEMON}], "obj": _potion(P_POISON)},
        {"name": "healing_caps_hp", "seed": 1, "op": "quaff", "level": 4, "hp": 19, "max_hp": 20, "obj": _potion(P_HEALING)},
        {"name": "strength_updates_max", "seed": 1, "op": "quaff", "strength": 16, "max_strength": 16, "obj": _potion(P_STRENGTH)},
        {"name": "mfind_fleeting", "seed": 1, "op": "quaff", "new_monsters": 0, "obj": _potion(P_MFIND)},
        {"name": "mfind_reveals", "seed": 1, "op": "quaff", "new_monsters": 2, "obj": _potion(P_MFIND)},
        {"name": "tfind_shows_magic", "seed": 1, "op": "quaff", "magic_count": 3, "obj": _potion(P_TFIND)},
        {"name": "tfind_fleeting", "seed": 1, "op": "quaff", "magic_count": 0, "obj": _potion(P_TFIND)},
        {"name": "lsd_starts_visuals", "seed": 1, "op": "quaff", "player_flags": SEEMONST, "new_monsters": 1, "stairs_visible": True, "obj": _potion(P_LSD)},
        {"name": "seeinvis_new", "seed": 1, "op": "quaff", "invisible_visible": 2, "obj": _potion(P_SEEINVIS)},
        {"name": "seeinvis_existing_blind", "seed": 1, "op": "quaff", "player_flags": CANSEE | ISBLIND, "actions": [{"action": "unsee", "action_type": AFTER, "arg": 0, "time": 5}, {"action": "sight", "action_type": AFTER, "arg": 0, "time": 5}], "obj": _potion(P_SEEINVIS)},
        {"name": "raise_level", "seed": 1, "op": "quaff", "level": 5, "exp": 100, "hp": 12, "max_hp": 20, "obj": _potion(P_RAISE)},
        {"name": "xheal_big_come_down_blind", "seed": 1, "op": "quaff", "player_flags": ISHALU | ISBLIND, "level": 5, "hp": 19, "max_hp": 20, "obj": _potion(P_XHEAL)},
        {"name": "haste_new", "seed": 1, "op": "quaff", "after": True, "obj": _potion(P_HASTE)},
        {"name": "haste_exhaustion", "seed": 1, "op": "quaff", "player_flags": ISHASTE | ISRUN, "actions": [{"action": "nohaste", "action_type": AFTER, "arg": 0, "time": 5}], "obj": _potion(P_HASTE)},
        {"name": "restore_with_addstr", "seed": 1, "op": "quaff", "strength": 10, "max_strength": 16, "left_ring": {"which": R_ADDSTR, "arm": 2}, "obj": _potion(P_RESTORE)},
        {"name": "blind_new", "seed": 1, "op": "quaff", "obj": _potion(P_BLIND)},
        {"name": "levit_new_unwields", "seed": 1, "op": "quaff", "current_weapon_is_obj": True, "obj": _potion(P_LEVIT)},
        {"name": "is_magic_protected_armor", "seed": 1, "op": "is_magic", "obj": {"id": "armor", "type": ARMOR, "which": 0, "arm": 8, "flags": ISPROT}},
        {"name": "is_magic_plain_weapon", "seed": 1, "op": "is_magic", "obj": {"id": "weapon", "type": WEAPON, "which": 0, "hplus": 0, "dplus": 0}},
        {"name": "is_magic_enchanted_weapon", "seed": 1, "op": "is_magic", "obj": {"id": "weapon", "type": WEAPON, "which": 0, "hplus": 1, "dplus": 0}},
        {"name": "is_magic_ring", "seed": 1, "op": "is_magic", "obj": {"id": "ring", "type": RING, "which": 0}},
    ]
