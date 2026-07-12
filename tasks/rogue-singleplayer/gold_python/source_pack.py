"""Source-faithful Rogue pack/inventory slices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from source_rogue import AMULET, ARMOR, FOOD, MAXPACK, POTION, SCROLL, WEAPON


ISFOUND = 0o000020
S_SCARE = 10


@dataclass
class PackObject:
    obj_id: int
    obj_type: str
    which: int = 0
    count: int = 1
    group: int = 0
    flags: int = 0
    packch: str = ""
    pos: tuple[int, int] = (0, 0)

    def copy_for_leave(self, obj_id: int) -> "PackObject":
        return PackObject(
            obj_id=obj_id,
            obj_type=self.obj_type,
            which=self.which,
            count=1,
            group=self.group,
            flags=self.flags,
            packch=self.packch,
            pos=self.pos,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.obj_id,
            "type": self.obj_type,
            "which": self.which,
            "count": self.count,
            "group": self.group,
            "flags": self.flags,
            "packch": self.packch,
            "pos": list(self.pos),
        }


class SourcePack:
    def __init__(self) -> None:
        self.pack: list[PackObject] = []
        self.level_objects: list[PackObject] = []
        self.discarded: list[int] = []
        self.returned: list[PackObject] = []
        self.inpack = 0
        self.pack_used = [False for _ in range(26)]
        self.amulet = False
        self.next_id = 1
        self.last_pick: int | None = None

    def make(self, obj_type: str, which: int = 0, count: int = 1, group: int = 0, flags: int = 0, pos: tuple[int, int] = (0, 0)) -> PackObject:
        obj = PackObject(self.next_id, obj_type=obj_type, which=which, count=count, group=group, flags=flags, pos=pos)
        self.next_id += 1
        return obj

    def add_floor(self, obj: PackObject) -> None:
        self.level_objects.insert(0, obj)

    def add_pack(self, obj: PackObject, *, from_floor: bool = False) -> str:
        if obj.obj_type == SCROLL and obj.which == S_SCARE and obj.flags & ISFOUND:
            if from_floor:
                self._detach_level_object(obj)
            self.discarded.append(obj.obj_id)
            return "scare_dust"
        if not self.pack:
            self.pack.append(obj)
            obj.packch = self.pack_char()
            self.inpack += 1
        else:
            lp_index: int | None = None
            op_index = 0
            while op_index < len(self.pack):
                op = self.pack[op_index]
                if op.obj_type != obj.obj_type:
                    lp_index = op_index
                    op_index += 1
                    continue
                while op.obj_type == obj.obj_type and op.which != obj.which:
                    lp_index = op_index
                    if op_index + 1 == len(self.pack):
                        break
                    op_index += 1
                    op = self.pack[op_index]
                if op.obj_type == obj.obj_type and op.which == obj.which:
                    if _is_mult(op.obj_type):
                        if not self.pack_room(from_floor, obj):
                            return "no_room"
                        op.count += 1
                        self.discarded.append(obj.obj_id)
                        obj = op
                        lp_index = None
                        break
                    if obj.group:
                        lp_index = op_index
                        while op.obj_type == obj.obj_type and op.which == obj.which and op.group != obj.group:
                            lp_index = op_index
                            if op_index + 1 == len(self.pack):
                                break
                            op_index += 1
                            op = self.pack[op_index]
                        if op.obj_type == obj.obj_type and op.which == obj.which and op.group == obj.group:
                            op.count += obj.count
                            self.inpack -= 1
                            if not self.pack_room(from_floor, obj):
                                return "no_room"
                            self.discarded.append(obj.obj_id)
                            obj = op
                            lp_index = None
                            break
                    else:
                        lp_index = op_index
                break
            if lp_index is not None:
                if not self.pack_room(from_floor, obj):
                    return "no_room"
                obj.packch = self.pack_char()
                self.pack.insert(lp_index + 1, obj)
        obj.flags |= ISFOUND
        if obj.obj_type == AMULET:
            self.amulet = True
        return "added"

    def pack_room(self, from_floor: bool, obj: PackObject) -> bool:
        self.inpack += 1
        if self.inpack > MAXPACK:
            self.inpack = MAXPACK
            return False
        if from_floor:
            self._detach_level_object(obj)
        return True

    def leave_pack(self, obj_id: int, *, newobj: bool, all_items: bool) -> PackObject:
        obj = self._pack_object(obj_id)
        self.inpack -= 1
        returned = obj
        if obj.count > 1 and not all_items:
            self.last_pick = obj.obj_id
            obj.count -= 1
            if obj.group:
                self.inpack += 1
            if newobj:
                returned = obj.copy_for_leave(self.next_id)
                self.next_id += 1
        else:
            self.last_pick = None
            if obj.packch:
                self.pack_used[ord(obj.packch) - ord("a")] = False
            self.pack.remove(obj)
        self.returned.append(returned)
        return returned

    def pack_char(self) -> str:
        for index, used in enumerate(self.pack_used):
            if not used:
                self.pack_used[index] = True
                return chr(ord("a") + index)
        raise RuntimeError("Rogue pack_char exhausted")

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack": [obj.to_dict() for obj in self.pack],
            "level_objects": [obj.to_dict() for obj in self.level_objects],
            "discarded": list(self.discarded),
            "returned": [obj.to_dict() for obj in self.returned],
            "inpack": self.inpack,
            "pack_used": "".join(chr(ord("a") + index) for index, used in enumerate(self.pack_used) if used),
            "amulet": self.amulet,
            "last_pick": self.last_pick,
        }

    def _detach_level_object(self, obj: PackObject) -> None:
        self.level_objects.remove(obj)

    def _pack_object(self, obj_id: int) -> PackObject:
        for obj in self.pack:
            if obj.obj_id == obj_id:
                return obj
        raise RuntimeError(f"object {obj_id} not in pack")


def source_pack_report() -> dict[str, Any]:
    return {
        "cases": [
            _case_initial_order(),
            _case_multi_merge(),
            _case_group_merge_and_split(),
            _case_pack_overflow(),
            _case_scare_scroll_dust(),
            _case_leave_all_removes_packch(),
            _case_amulet_flag(),
        ]
    }


def _case_initial_order() -> dict[str, Any]:
    state = SourcePack()
    for obj in [
        state.make(FOOD),
        state.make(ARMOR, which=1),
        state.make(WEAPON, which=0),
        state.make(WEAPON, which=2),
        state.make(WEAPON, which=3, count=31, group=2),
    ]:
        state.add_pack(obj)
    return {"name": "initial_order", "state": state.to_dict()}


def _case_multi_merge() -> dict[str, Any]:
    state = SourcePack()
    first = state.make(FOOD, which=0)
    second = state.make(FOOD, which=0)
    state.add_pack(first)
    state.add_pack(second)
    state.leave_pack(first.obj_id, newobj=True, all_items=False)
    return {"name": "multi_merge_leave_one", "state": state.to_dict()}


def _case_group_merge_and_split() -> dict[str, Any]:
    state = SourcePack()
    arrows = state.make(WEAPON, which=3, count=10, group=7)
    same_group = state.make(WEAPON, which=3, count=5, group=7)
    other_group = state.make(WEAPON, which=3, count=4, group=8)
    state.add_pack(arrows)
    state.add_pack(same_group)
    state.add_pack(other_group)
    state.leave_pack(arrows.obj_id, newobj=True, all_items=False)
    return {"name": "group_merge_split", "state": state.to_dict()}


def _case_pack_overflow() -> dict[str, Any]:
    state = SourcePack()
    for index in range(MAXPACK):
        state.add_pack(state.make(ARMOR, which=index))
    extra = state.make(ARMOR, which=99)
    result = state.add_pack(extra)
    return {"name": "pack_overflow", "result": result, "state": state.to_dict(), "extra": extra.to_dict()}


def _case_scare_scroll_dust() -> dict[str, Any]:
    state = SourcePack()
    scroll = state.make(SCROLL, which=S_SCARE, flags=ISFOUND, pos=(3, 4))
    state.add_floor(scroll)
    result = state.add_pack(scroll, from_floor=True)
    return {"name": "scare_scroll_dust", "result": result, "state": state.to_dict()}


def _case_leave_all_removes_packch() -> dict[str, Any]:
    state = SourcePack()
    food = state.make(FOOD, count=3)
    state.add_pack(food)
    state.leave_pack(food.obj_id, newobj=False, all_items=True)
    replacement = state.make(POTION, which=2)
    state.add_pack(replacement)
    return {"name": "leave_all_reuses_packch", "state": state.to_dict()}


def _case_amulet_flag() -> dict[str, Any]:
    state = SourcePack()
    state.add_pack(state.make(AMULET))
    return {"name": "amulet_flag", "state": state.to_dict()}


def _is_mult(obj_type: str) -> bool:
    return obj_type in {POTION, SCROLL, FOOD}
