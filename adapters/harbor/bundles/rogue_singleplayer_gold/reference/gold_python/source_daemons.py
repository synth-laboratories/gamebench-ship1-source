"""Source-faithful Rogue daemon and fuse behavior slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_rogue import BORE_LEVEL, RogueRng


EMPTY = 0
DAEMON = -1
BEFORE = 1
AFTER = 2
MAXDAEMONS = 20

CANSEE = 0o000002
ISBLIND = 0o000004
ISLEVIT = 0o000010
ISHASTE = 0o000100
ISHUH = 0o001000
ISRUN = 0o020000

R_REGEN = 9
R_DIGEST = 10

MORETIME = 150
STARVETIME = 850


@dataclass
class SourceStats:
    level: int
    hp: int

    def to_dict(self) -> dict[str, int]:
        return {"level": self.level, "hp": self.hp}


@dataclass
class SourceRing:
    which: int


@dataclass
class DelayedAction:
    action: str = ""
    action_type: int = EMPTY
    arg: int = 0
    time: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "type": self.action_type, "arg": self.arg, "time": self.time}


@dataclass
class DaemonWorld:
    rng: RogueRng
    stats: SourceStats
    max_hp: int
    quiet: int = 0
    player_flags: int = ISRUN
    left_ring: SourceRing | None = None
    right_ring: SourceRing | None = None
    food_left: int = 1300
    hungry_state: int = 0
    no_command: int = 0
    terse: bool = False
    amulet: int = 0
    running: bool = True
    to_death: bool = True
    count: int = 3
    proom_gone: bool = False
    visible_invisible: int = 0
    between: int = 0
    actions: list[DelayedAction] = field(default_factory=lambda: [DelayedAction() for _ in range(MAXDAEMONS)])
    markers: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rng_seed": self.rng.seed,
            "stats": self.stats.to_dict(),
            "max_hp": self.max_hp,
            "quiet": self.quiet,
            "player_flags": self.player_flags,
            "food_left": self.food_left,
            "hungry_state": self.hungry_state,
            "no_command": self.no_command,
            "running": self.running,
            "to_death": self.to_death,
            "count": self.count,
            "between": self.between,
            "actions": [action.to_dict() for action in self.actions if action.action_type != EMPTY],
            "markers": self.markers,
            "trace": self.trace,
        }


def doctor(world: DaemonWorld) -> None:
    level = world.stats.level
    old_hp = world.stats.hp
    world.quiet += 1
    if level < 8:
        if world.quiet + (level << 1) > 20:
            world.stats.hp += 1
    elif world.quiet >= 3:
        world.stats.hp += world.rng.rnd(level - 7) + 1
    if _is_ring(world.left_ring, R_REGEN):
        world.stats.hp += 1
    if _is_ring(world.right_ring, R_REGEN):
        world.stats.hp += 1
    if old_hp != world.stats.hp:
        if world.stats.hp > world.max_hp:
            world.stats.hp = world.max_hp
        world.quiet = 0


def swander(world: DaemonWorld) -> None:
    start_daemon(world, "rollwand", 0, BEFORE)


def rollwand(world: DaemonWorld) -> None:
    world.between += 1
    if world.between >= 4:
        roll = world.rng.roll(1, 6)
        world.trace["wander_roll"] = roll
        if roll == 4:
            world.markers.append("wanderer")
            kill_daemon(world, "rollwand")
            fuse(world, "swander", 0, _wandertime(world), BEFORE)
        world.between = 0


def unconfuse(world: DaemonWorld) -> None:
    world.player_flags &= ~ISHUH
    world.markers.append("msg_unconfuse")


def unsee(world: DaemonWorld) -> None:
    for _ in range(world.visible_invisible):
        world.markers.append("restore_invisible")
    world.player_flags &= ~CANSEE


def sight(world: DaemonWorld) -> None:
    if world.player_flags & ISBLIND:
        extinguish(world, "sight")
        world.player_flags &= ~ISBLIND
        if not world.proom_gone:
            world.markers.append("enter_room")
        world.markers.append("msg_sight")


def nohaste(world: DaemonWorld) -> None:
    world.player_flags &= ~ISHASTE
    world.markers.append("msg_nohaste")


def land(world: DaemonWorld) -> None:
    world.player_flags &= ~ISLEVIT
    world.markers.append("msg_land")


def stomach(world: DaemonWorld) -> None:
    original_hungry = world.hungry_state
    if world.food_left <= 0:
        if world.food_left < -STARVETIME:
            world.markers.append("death:s")
        world.food_left -= 1
        if world.no_command or world.rng.rnd(5) != 0:
            return
        faint = world.rng.rnd(8) + 4
        world.trace["faint_roll"] = faint
        world.no_command += faint
        world.hungry_state = 3
        world.markers.append("msg_faint")
    else:
        oldfood = world.food_left
        world.food_left -= _ring_eat(world, world.left_ring) + _ring_eat(world, world.right_ring) + 1 - world.amulet
        if world.food_left < MORETIME and oldfood >= MORETIME:
            world.hungry_state = 2
            world.markers.append("msg_weak")
        elif world.food_left < 2 * MORETIME and oldfood >= 2 * MORETIME:
            world.hungry_state = 1
            world.markers.append("msg_hungry")
    if world.hungry_state != original_hungry:
        world.player_flags &= ~ISRUN
        world.running = False
        world.to_death = False
        world.count = 0


def start_daemon(world: DaemonWorld, action: str, arg: int, action_type: int) -> None:
    slot = _d_slot(world)
    slot.action_type = action_type
    slot.action = action
    slot.arg = arg
    slot.time = DAEMON


def kill_daemon(world: DaemonWorld, action: str) -> None:
    slot = _find_slot(world, action)
    if slot is not None:
        slot.action_type = EMPTY


def do_daemons(world: DaemonWorld, flag: int) -> None:
    for action in list(world.actions):
        if action.action_type == flag and action.time == DAEMON:
            _run_action(world, action.action)


def fuse(world: DaemonWorld, action: str, arg: int, time: int, action_type: int) -> None:
    slot = _d_slot(world)
    slot.action_type = action_type
    slot.action = action
    slot.arg = arg
    slot.time = time


def lengthen(world: DaemonWorld, action: str, xtime: int) -> None:
    slot = _find_slot(world, action)
    if slot is not None:
        slot.time += xtime


def extinguish(world: DaemonWorld, action: str) -> None:
    slot = _find_slot(world, action)
    if slot is not None:
        slot.action_type = EMPTY


def do_fuses(world: DaemonWorld, flag: int) -> None:
    for action in list(world.actions):
        if action.action_type == flag and action.time > 0:
            action.time -= 1
            if action.time == 0:
                action.action_type = EMPTY
                _run_action(world, action.action)


def source_daemons_report() -> dict[str, Any]:
    return {"schema": "gamebench.rogue.source_daemons.v1", "cases": [_run_case(case) for case in _cases()]}


def _ring_eat(world: DaemonWorld, ring: SourceRing | None) -> int:
    uses = [1, 1, 1, -3, -5, 0, 0, -3, -3, 2, -2, 0, 1, 1]
    if ring is None:
        return 0
    eat = uses[ring.which]
    if eat < 0:
        eat = 1 if world.rng.rnd(-eat) == 0 else 0
    if ring.which == R_DIGEST:
        eat = -eat
    return eat


def _run_action(world: DaemonWorld, action: str) -> None:
    if action == "doctor":
        doctor(world)
    elif action == "stomach":
        stomach(world)
    elif action == "swander":
        swander(world)
    elif action == "rollwand":
        rollwand(world)
    elif action == "sight":
        sight(world)
    elif action == "unconfuse":
        unconfuse(world)
    elif action == "unsee":
        unsee(world)
    elif action == "nohaste":
        nohaste(world)
    elif action == "land":
        land(world)
    else:
        world.markers.append(f"run:{action}")


def _d_slot(world: DaemonWorld) -> DelayedAction:
    for action in world.actions:
        if action.action_type == EMPTY:
            return action
    raise RuntimeError("ran out of daemon slots")


def _find_slot(world: DaemonWorld, action: str) -> DelayedAction | None:
    for slot in world.actions:
        if slot.action_type != EMPTY and slot.action == action:
            return slot
    return None


def _wandertime(world: DaemonWorld) -> int:
    return 70 - 70 // 20 + world.rng.rnd(70 // 10)


def _is_ring(ring: SourceRing | None, which: int) -> bool:
    return ring is not None and ring.which == which


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    world = _world(case)
    for action in case.get("setup_actions", []):
        if action["op"] == "start":
            start_daemon(world, action["action"], action.get("arg", 0), action["type"])
        elif action["op"] == "fuse":
            fuse(world, action["action"], action.get("arg", 0), action["time"], action["type"])
        elif action["op"] == "lengthen":
            lengthen(world, action["action"], action["time"])
        elif action["op"] == "extinguish":
            extinguish(world, action["action"])
    op = case["op"]
    if op == "doctor":
        doctor(world)
    elif op == "stomach":
        stomach(world)
    elif op == "swander":
        swander(world)
    elif op == "rollwand":
        rollwand(world)
    elif op == "do_daemons":
        do_daemons(world, case["flag"])
    elif op == "do_fuses":
        do_fuses(world, case["flag"])
    elif op == "unconfuse":
        unconfuse(world)
    elif op == "unsee":
        unsee(world)
    elif op == "sight":
        sight(world)
    elif op == "nohaste":
        nohaste(world)
    elif op == "land":
        land(world)
    else:
        raise ValueError(op)
    return {"name": case["name"], "seed": case["seed"], "world": world.to_dict()}


def _world(case: dict[str, Any]) -> DaemonWorld:
    return DaemonWorld(
        rng=RogueRng(case["seed"]),
        stats=SourceStats(case.get("level", 5), case.get("hp", 10)),
        max_hp=case.get("max_hp", 20),
        quiet=case.get("quiet", 0),
        player_flags=case.get("player_flags", ISRUN),
        left_ring=_ring(case.get("left_ring")),
        right_ring=_ring(case.get("right_ring")),
        food_left=case.get("food_left", 1300),
        hungry_state=case.get("hungry_state", 0),
        no_command=case.get("no_command", 0),
        terse=case.get("terse", False),
        amulet=case.get("amulet", 0),
        running=case.get("running", True),
        to_death=case.get("to_death", True),
        count=case.get("count", 3),
        proom_gone=case.get("proom_gone", False),
        visible_invisible=case.get("visible_invisible", 0),
        between=case.get("between", 0),
    )


def _ring(payload: dict[str, int] | None) -> SourceRing | None:
    if payload is None:
        return None
    return SourceRing(payload["which"])


def _cases() -> list[dict[str, Any]]:
    return [
        {"name": "doctor_low_level_waits", "seed": 1, "op": "doctor", "level": 3, "hp": 10, "max_hp": 20, "quiet": 13},
        {"name": "doctor_low_level_heals", "seed": 1, "op": "doctor", "level": 3, "hp": 10, "max_hp": 20, "quiet": 14},
        {"name": "doctor_high_regen_caps", "seed": 7, "op": "doctor", "level": 10, "hp": 19, "max_hp": 20, "quiet": 2, "left_ring": {"which": R_REGEN}, "right_ring": {"which": R_REGEN}},
        {"name": "stomach_gets_hungry", "seed": 1, "op": "stomach", "food_left": 300, "left_ring": {"which": R_REGEN}},
        {"name": "stomach_gets_weak", "seed": 1, "op": "stomach", "food_left": 150},
        {"name": "stomach_faints", "seed": 1, "op": "stomach", "food_left": 0, "hungry_state": 2, "player_flags": ISRUN, "running": True, "to_death": True, "count": 3},
        {"name": "stomach_starves", "seed": 1, "op": "stomach", "food_left": -851, "no_command": 1},
        {"name": "swander_starts_rollwand", "seed": 1, "op": "swander"},
        {"name": "rollwand_wanderer", "seed": 17, "op": "rollwand", "between": 3, "setup_actions": [{"op": "start", "action": "rollwand", "type": BEFORE}]},
        {"name": "do_daemons_runs_doctor", "seed": 1, "op": "do_daemons", "flag": AFTER, "level": 3, "hp": 10, "max_hp": 20, "quiet": 14, "setup_actions": [{"op": "start", "action": "doctor", "type": AFTER}]},
        {"name": "do_fuses_runs_sight", "seed": 1, "op": "do_fuses", "flag": AFTER, "player_flags": ISRUN | ISBLIND, "setup_actions": [{"op": "fuse", "action": "sight", "type": AFTER, "time": 1}]},
        {"name": "lengthen_fuse_waits", "seed": 1, "op": "do_fuses", "flag": AFTER, "player_flags": ISRUN | ISBLIND, "setup_actions": [{"op": "fuse", "action": "sight", "type": AFTER, "time": 1}, {"op": "lengthen", "action": "sight", "time": 2}]},
        {"name": "extinguish_fuse_removes", "seed": 1, "op": "do_fuses", "flag": AFTER, "player_flags": ISRUN | ISBLIND, "setup_actions": [{"op": "fuse", "action": "sight", "type": AFTER, "time": 1}, {"op": "extinguish", "action": "sight"}]},
        {"name": "unconfuse_clears_flag", "seed": 1, "op": "unconfuse", "player_flags": ISRUN | ISHUH},
        {"name": "unsee_restores_invisible", "seed": 1, "op": "unsee", "player_flags": ISRUN | CANSEE, "visible_invisible": 2},
        {"name": "sight_clears_blind", "seed": 1, "op": "sight", "player_flags": ISRUN | ISBLIND, "setup_actions": [{"op": "fuse", "action": "sight", "type": AFTER, "time": 5}]},
        {"name": "nohaste_clears_haste", "seed": 1, "op": "nohaste", "player_flags": ISRUN | ISHASTE},
        {"name": "land_clears_levitation", "seed": 1, "op": "land", "player_flags": ISRUN | ISLEVIT},
    ]
