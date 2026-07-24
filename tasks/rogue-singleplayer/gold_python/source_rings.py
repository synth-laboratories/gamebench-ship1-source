"""Source-faithful Rogue ring behavior slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_rogue import RING, RogueRng


LEFT = 0
RIGHT = 1

ISCURSED = 0o000001
ISKNOW = 0o000002

R_PROTECT = 0
R_ADDSTR = 1
R_SUSTSTR = 2
R_SEARCH = 3
R_SEEINVIS = 4
R_NOP = 5
R_AGGR = 6
R_ADDHIT = 7
R_ADDDAM = 8
R_REGEN = 9
R_DIGEST = 10
R_TELEPORT = 11
R_STEALTH = 12
R_SUSTARM = 13


@dataclass
class RingObject:
    obj_id: str
    obj_type: str
    which: int
    arm: int
    flags: int = 0
    packch: str = "a"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.obj_id, "type": self.obj_type, "which": self.which, "arm": self.arm, "flags": self.flags, "packch": self.packch}


@dataclass
class RingWorld:
    rng: RogueRng
    strength: int = 16
    left_ring: RingObject | None = None
    right_ring: RingObject | None = None
    selected_hand: int = LEFT
    terse: bool = False
    markers: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rng_seed": self.rng.seed,
            "strength": self.strength,
            "left_ring": self.left_ring.to_dict() if self.left_ring is not None else None,
            "right_ring": self.right_ring.to_dict() if self.right_ring is not None else None,
            "markers": self.markers,
            "trace": self.trace,
        }


def ring_on(world: RingWorld, obj: RingObject | None) -> None:
    if obj is None:
        return
    if obj.obj_type != RING:
        world.markers.append("not_ring")
        return
    if _is_current(world, obj):
        world.markers.append("in_use")
        return
    if world.left_ring is None and world.right_ring is None:
        ring = world.selected_hand
        if ring < 0:
            world.markers.append("gethand_cancelled")
            return
    elif world.left_ring is None:
        ring = LEFT
    elif world.right_ring is None:
        ring = RIGHT
    else:
        world.markers.append("wearing_two")
        return
    if ring == LEFT:
        world.left_ring = obj
    else:
        world.right_ring = obj
    if obj.which == R_ADDSTR:
        world.strength += obj.arm
        world.markers.append("chg_str")
    elif obj.which == R_SEEINVIS:
        world.markers.append("invis_on")
    elif obj.which == R_AGGR:
        world.markers.append("aggravate")
    world.markers.append(f"wear:{ring}")


def ring_off(world: RingWorld) -> None:
    if world.left_ring is None and world.right_ring is None:
        world.markers.append("no_rings")
        return
    if world.left_ring is None:
        ring = RIGHT
    elif world.right_ring is None:
        ring = LEFT
    else:
        ring = world.selected_hand
        if ring < 0:
            world.markers.append("gethand_cancelled")
            return
    obj = world.left_ring if ring == LEFT else world.right_ring
    if obj is None:
        world.markers.append("not_wearing")
        return
    if dropcheck(world, obj):
        world.markers.append(f"was_wearing:{obj.packch}")


def dropcheck(world: RingWorld, obj: RingObject | None) -> bool:
    if obj is None:
        return True
    hand = _current_hand(world, obj)
    if hand is None:
        return True
    if obj.flags & ISCURSED:
        world.markers.append("cursed")
        return False
    if hand == LEFT:
        world.left_ring = None
    else:
        world.right_ring = None
    if obj.which == R_ADDSTR:
        world.strength -= obj.arm
        world.markers.append("chg_str")
    elif obj.which == R_SEEINVIS:
        world.markers.append("unsee")
        world.markers.append("extinguish_unsee")
    return True


def ring_eat(world: RingWorld, hand: int) -> int:
    ring = world.left_ring if hand == LEFT else world.right_ring
    uses = [1, 1, 1, -3, -5, 0, 0, -3, -3, 2, -2, 0, 1, 1]
    if ring is None:
        return 0
    eat = uses[ring.which]
    if eat < 0:
        eat = 1 if world.rng.rnd(-eat) == 0 else 0
    if ring.which == R_DIGEST:
        eat = -eat
    world.trace["eat"] = eat
    return eat


def ring_num(obj: RingObject) -> str:
    if not (obj.flags & ISKNOW):
        return ""
    if obj.which in {R_PROTECT, R_ADDSTR, R_ADDDAM, R_ADDHIT}:
        return f" [{_num(obj.arm)}]"
    return ""


def source_rings_report() -> dict[str, Any]:
    return {"schema": "gamebench.rogue.source_rings.v1", "cases": [_run_case(case) for case in _cases()]}


def _num(value: int) -> str:
    return str(value) if value < 0 else f"+{value}"


def _is_current(world: RingWorld, obj: RingObject) -> bool:
    return _same_obj(world.left_ring, obj) or _same_obj(world.right_ring, obj)


def _current_hand(world: RingWorld, obj: RingObject) -> int | None:
    if _same_obj(world.left_ring, obj):
        return LEFT
    if _same_obj(world.right_ring, obj):
        return RIGHT
    return None


def _same_obj(left: RingObject | None, right: RingObject) -> bool:
    return left is not None and left.obj_id == right.obj_id


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    world = RingWorld(
        rng=RogueRng(case["seed"]),
        strength=case.get("strength", 16),
        left_ring=_ring(case.get("left_ring")),
        right_ring=_ring(case.get("right_ring")),
        selected_hand=case.get("selected_hand", LEFT),
        terse=case.get("terse", False),
    )
    result: Any = None
    op = case["op"]
    if op == "ring_on":
        ring_on(world, _ring(case.get("obj")))
    elif op == "ring_off":
        ring_off(world)
    elif op == "dropcheck":
        result = dropcheck(world, _ring(case.get("obj")))
    elif op == "ring_eat":
        result = ring_eat(world, case.get("hand", LEFT))
    elif op == "ring_num":
        result = ring_num(_ring(case["obj"]) or _ring({"id": "none", "type": RING, "which": R_NOP, "arm": 0}))
    else:
        raise ValueError(op)
    return {"name": case["name"], "seed": case["seed"], "result": result, "world": world.to_dict()}


def _ring(payload: dict[str, Any] | None) -> RingObject | None:
    if payload is None:
        return None
    return RingObject(
        obj_id=payload.get("id", payload.get("obj_id", "ring")),
        obj_type=payload.get("type", payload.get("obj_type", RING)),
        which=payload.get("which", R_NOP),
        arm=payload.get("arm", 0),
        flags=payload.get("flags", 0),
        packch=payload.get("packch", "a"),
    )


def _cases() -> list[dict[str, Any]]:
    return [
        {"name": "wear_addstr_chosen_left", "seed": 1, "op": "ring_on", "selected_hand": LEFT, "obj": {"id": "addstr", "type": RING, "which": R_ADDSTR, "arm": 2, "packch": "a"}},
        {"name": "wear_seeinvis_auto_right", "seed": 1, "op": "ring_on", "left_ring": {"id": "left", "type": RING, "which": R_PROTECT, "arm": 1, "packch": "l"}, "obj": {"id": "see", "type": RING, "which": R_SEEINVIS, "arm": 0, "packch": "b"}},
        {"name": "wear_aggravate_auto_left", "seed": 1, "op": "ring_on", "right_ring": {"id": "right", "type": RING, "which": R_PROTECT, "arm": 1, "packch": "r"}, "obj": {"id": "aggr", "type": RING, "which": R_AGGR, "arm": 0, "packch": "c"}},
        {"name": "wear_non_ring_rejected", "seed": 1, "op": "ring_on", "obj": {"id": "food", "type": ":", "which": R_NOP, "arm": 0}},
        {"name": "wear_current_rejected", "seed": 1, "op": "ring_on", "left_ring": {"id": "same", "type": RING, "which": R_PROTECT, "arm": 1}, "obj": {"id": "same", "type": RING, "which": R_PROTECT, "arm": 1}},
        {"name": "wear_two_rejected", "seed": 1, "op": "ring_on", "left_ring": {"id": "left", "type": RING, "which": R_PROTECT, "arm": 1}, "right_ring": {"id": "right", "type": RING, "which": R_ADDHIT, "arm": 1}, "obj": {"id": "third", "type": RING, "which": R_REGEN, "arm": 0}},
        {"name": "off_no_rings", "seed": 1, "op": "ring_off"},
        {"name": "off_addstr_uncursed", "seed": 1, "op": "ring_off", "strength": 18, "left_ring": {"id": "addstr", "type": RING, "which": R_ADDSTR, "arm": 2, "packch": "a"}},
        {"name": "off_cursed_keeps_ring", "seed": 1, "op": "ring_off", "left_ring": {"id": "bad", "type": RING, "which": R_ADDSTR, "arm": 2, "flags": ISCURSED, "packch": "b"}},
        {"name": "off_seeinvis_unsee", "seed": 1, "op": "ring_off", "right_ring": {"id": "see", "type": RING, "which": R_SEEINVIS, "arm": 0, "packch": "c"}},
        {"name": "eat_none", "seed": 1, "op": "ring_eat", "hand": LEFT},
        {"name": "eat_regen", "seed": 1, "op": "ring_eat", "hand": LEFT, "left_ring": {"id": "regen", "type": RING, "which": R_REGEN, "arm": 0}},
        {"name": "eat_search_random", "seed": 1, "op": "ring_eat", "hand": LEFT, "left_ring": {"id": "search", "type": RING, "which": R_SEARCH, "arm": 0}},
        {"name": "eat_digest_negative", "seed": 1, "op": "ring_eat", "hand": LEFT, "left_ring": {"id": "digest", "type": RING, "which": R_DIGEST, "arm": 0}},
        {"name": "num_unknown", "seed": 1, "op": "ring_num", "obj": {"id": "unk", "type": RING, "which": R_ADDSTR, "arm": 2, "flags": 0}},
        {"name": "num_addhit_positive", "seed": 1, "op": "ring_num", "obj": {"id": "hit", "type": RING, "which": R_ADDHIT, "arm": 3, "flags": ISKNOW}},
        {"name": "num_adddam_negative", "seed": 1, "op": "ring_num", "obj": {"id": "dam", "type": RING, "which": R_ADDDAM, "arm": -1, "flags": ISKNOW}},
        {"name": "num_regen_empty", "seed": 1, "op": "ring_num", "obj": {"id": "regen", "type": RING, "which": R_REGEN, "arm": 0, "flags": ISKNOW}},
    ]
