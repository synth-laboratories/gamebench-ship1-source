"""Read-only combat-relevant player state from the pinned NLE oracle.

This is deliberately a *source evidence* adapter, not a second NetHack
implementation.  It freezes the few ``struct you`` fields which are causal
for the reset-wall KICK and ordinary player-melee frontiers, then checks every
publicly representable value against the exact pre-action NLE observation.
All offsets below were measured from the pinned commit's headers on the
supported Darwin arm64 ABI; a layout mismatch is an error, never a fallback.
"""

from __future__ import annotations

import ctypes
import hashlib
import re
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.nle_native_entities import EXPECTED_BINARY_SHA256, MAX_OBJECTS, NativeMonst, NativeObj, SOURCE_COMMIT


# Exact Darwin arm64 measurements from commit 2fa1be5.  The C probe used the
# same generated pm.h/onames.h as the pinned NLE CMake build.
EXPECTED_YOU_SIZE = 2392
EXPECTED_ROLE_SIZE = 288
EXPECTED_PROP_SIZE = 24
YOU_OFFSETS = {
    "ux": 0,
    "uy": 1,
    "ulevel": 24,
    "utrap": 32,
    "utraptype": 36,
    "uhunger": 76,
    "uhs": 80,
    "uprops": 88,
    "umonster": 1752,
    "umonnum": 1756,
    "mh": 1760,
    "mhmax": 1764,
    "acurr": 1920,
    "aexe": 1926,
    "abon": 1932,
    "amax": 1938,
    "atemp": 1944,
    "atime": 1950,
    "uluck": 1966,
    "moreluck": 1967,
    "uac": 1970,
    "uhp": 1976,
    "uhpmax": 1980,
    "uen": 1984,
    "uenmax": 1988,
    "weapon_skills": 2232,
    "twoweap": 2388,
}
ROLE_MALENUM_OFFSET = 208
PROP_WOUNDED_LEGS = 26
P_BARE_HANDED_COMBAT = 36
PM_MONK = 333
PM_SAMURAI = 338
PM_SASQUATCH = 234
KICKING_BOOTS = 147
OBJ_INVENT = 3
WOUNDED_LEGS_LEFT = 0x00020000
WOUNDED_LEGS_RIGHT = 0x00040000

EQUIPMENT_SLOTS = ("uwep", "uswapwep", "uquiver", "uarm", "uarmu", "uarmc", "uarmh", "uarms", "uarmg", "uarmf")
PUBLIC_BLSTATS = {
    "x": 0,
    "y": 1,
    "strength": 3,
    "dexterity": 4,
    "constitution": 5,
    "intelligence": 6,
    "wisdom": 7,
    "charisma": 8,
    "hp": 10,
    "hp_max": 11,
    "energy": 14,
    "energy_max": 15,
    "armor_class": 16,
    "experience_level": 18,
    "time": 20,
    "hunger_state": 21,
    "condition": 25,
}


class NativeYou(ctypes.Structure):
    _fields_ = [("raw", ctypes.c_ubyte * EXPECTED_YOU_SIZE)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _address(value: Any) -> int:
    return int(value or 0)


def _aligned_nonzero(pointer: int, *, what: str) -> None:
    if pointer <= 0 or pointer % ctypes.alignment(ctypes.c_void_p):
        raise RuntimeError(f"invalid {what} pointer")


def _symbol_offsets(path: Path) -> dict[str, int]:
    if sys.platform != "darwin":
        raise RuntimeError("native player oracle reader supports the pinned macOS NLE wheel only")
    wanted = {"u", "youmonst", "urole", "context", "invent", "moves", "movemon", "rn2", "acurr", *EQUIPMENT_SLOTS}
    pattern = re.compile(r"^([0-9A-Fa-f]+)\s+\w\s+_(" + "|".join(sorted(wanted)) + r")$")
    result = subprocess.run(["nm", "-a", str(path)], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    offsets: dict[str, int] = {}
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            offsets[match.group(2)] = int(match.group(1), 16)
    if set(offsets) != wanted:
        raise RuntimeError(f"pinned NLE binary lacks required unambiguous player symbols: {sorted(wanted - set(offsets))}")
    return offsets


def _assert_layout() -> None:
    checks = (
        (ctypes.sizeof(NativeYou), EXPECTED_YOU_SIZE, "you size"),
        (ctypes.sizeof(NativeObj), 96, "obj size"),
        (YOU_OFFSETS["ulevel"], 24, "you.ulevel"),
        (YOU_OFFSETS["uprops"], 88, "you.uprops"),
        (YOU_OFFSETS["acurr"], 1920, "you.acurr"),
        (YOU_OFFSETS["uhp"], 1976, "you.uhp"),
        (YOU_OFFSETS["twoweap"], 2388, "you.twoweap"),
        (ROLE_MALENUM_OFFSET, 208, "Role.malenum"),
    )
    failed = [f"{name}: {actual} != {expected}" for actual, expected, name in checks if actual != expected]
    if failed:
        raise RuntimeError("pinned NLE native player ABI layout mismatch: " + "; ".join(failed))


def _i8(raw: bytes, offset: int) -> int:
    return struct.unpack_from("b", raw, offset)[0]


def _i16(raw: bytes, offset: int) -> int:
    return struct.unpack_from("h", raw, offset)[0]


def _i32(raw: bytes, offset: int) -> int:
    return struct.unpack_from("i", raw, offset)[0]


def _u32(raw: bytes, offset: int) -> int:
    return struct.unpack_from("I", raw, offset)[0]


def dokick_martial_predicate(role_species_id: int, current_species_id: int, footwear_object_type: int | None) -> dict[str, bool]:
    """Freeze ``dokick.c``'s exact ``martial()`` macro as source evidence."""
    role_bonus = int(role_species_id) in (PM_MONK, PM_SAMURAI)
    sasquatch_form = int(current_species_id) == PM_SASQUATCH
    kicking_boots = footwear_object_type == KICKING_BOOTS
    return {
        "role_bonus": role_bonus,
        "sasquatch_form": sasquatch_form,
        "kicking_boots": kicking_boots,
        "effective": role_bonus or sasquatch_form or kicking_boots,
    }


def _i64(raw: bytes, offset: int) -> int:
    return struct.unpack_from("q", raw, offset)[0]


@dataclass(frozen=True)
class NativePlayerSnapshot:
    binary_sha256: str
    source_turn: int
    player: dict[str, Any]

    def public_record(self) -> dict[str, Any]:
        return {
            "schema": "gamebench.nethack.native_player_combat_snapshot.v1",
            "source_commit": SOURCE_COMMIT,
            "binary_sha256": self.binary_sha256,
            "source_turn": self.source_turn,
            "scope": "read-only pre-action source evidence for KICK/basic melee assertions only; never a gold input or behavior implementation",
            "player": self.player,
        }


def validate_player_record(record: dict[str, Any]) -> list[str]:
    """Validate stored player evidence after its outer tape hash is checked.

    This intentionally repeats only structural/source-semantic invariants; it
    never tries to reconstruct combat or feed this data to gold.
    """
    failures: list[str] = []
    if record.get("schema") != "gamebench.nethack.native_player_combat_snapshot.v1":
        return ["player schema mismatch"]
    if record.get("source_commit") != SOURCE_COMMIT or record.get("binary_sha256") != EXPECTED_BINARY_SHA256:
        failures.append("player source or binary pin mismatch")
    if type(record.get("source_turn")) is not int or int(record.get("source_turn", -1)) < 0:
        failures.append("player source turn is invalid")
    player = record.get("player")
    if not isinstance(player, dict):
        return [*failures, "player payload missing"]
    coordinates = player.get("coordinates")
    resources = player.get("resources")
    attributes = player.get("attributes")
    exercise_state = player.get("exercise_state")
    combat = player.get("combat")
    conditions = player.get("conditions")
    equipment = player.get("equipment")
    completeness = player.get("completeness")
    if not all(isinstance(value, dict) for value in (coordinates, resources, attributes, combat, conditions, equipment, completeness)):
        return [*failures, "player required section missing"]
    # Historical v1 receipts predate the exercise export and remain readable;
    # every fresh native capture includes it so KICK promotion cannot mistake
    # visible attributes for the complete causal player state.
    if exercise_state is not None:
        attr_names = ("strength", "intelligence", "wisdom", "dexterity", "constitution", "charisma")
        if (
            not isinstance(exercise_state, dict)
            or not isinstance(exercise_state.get("aexe"), dict)
            or not isinstance(exercise_state.get("atime"), dict)
            or any(type(exercise_state["aexe"].get(name)) is not int for name in attr_names)
            or any(type(exercise_state["atime"].get(name)) is not int for name in attr_names)
            or type(exercise_state.get("next_attrib_check")) is not int
            or exercise_state["next_attrib_check"] < 0
        ):
            failures.append("player exercise-state contract mismatch")
    # Fresh captures expose the hero's native scheduler as source evidence.
    # Historical v1 sidecars remain readable, but the extension is validated
    # completely whenever present and is never a gold-runtime input.
    scheduler = player.get("scheduler")
    if scheduler is not None:
        if (not isinstance(scheduler, dict) or
                type(scheduler.get("movement_points")) is not int or
                type(scheduler.get("source_moves")) is not int or
                scheduler.get("source_moves") != record.get("source_turn")):
            failures.append("player scheduler evidence mismatch")
    if not all(type(coordinates.get(key)) is int for key in ("native_x", "native_y", "nle_x", "nle_y")) or not (1 <= coordinates.get("native_x", 0) <= 79 and 0 <= coordinates.get("native_y", -1) < 21 and coordinates.get("nle_x") == coordinates.get("native_x") - 1 and coordinates.get("nle_y") == coordinates.get("native_y")):
        failures.append("player coordinate contract mismatch")
    numeric_resources = ("experience_level", "hp", "hp_max", "human_hp", "human_hp_max", "energy", "energy_max", "armor_class", "hunger", "hunger_state")
    if not all(type(resources.get(key)) is int for key in numeric_resources) or not (1 <= resources.get("experience_level", 0) <= 30 and 0 <= resources.get("hp", -1) <= resources.get("hp_max", -1) and resources.get("hp_max", 0) > 0):
        failures.append("player resource contract mismatch")
    effective = attributes.get("effective")
    components = attributes.get("components")
    attr_names = ("strength", "intelligence", "wisdom", "dexterity", "constitution", "charisma")
    if not isinstance(effective, dict) or not isinstance(components, dict) or not all(type(effective.get(name)) is int and isinstance(components.get(name), dict) and all(type(components[name].get(part)) is int for part in ("base", "bonus", "temporary")) for name in attr_names):
        failures.append("player attribute contract mismatch")
    martial = combat.get("martial")
    form = combat.get("monster_form")
    luck = combat.get("luck")
    if not isinstance(martial, dict) or not isinstance(form, dict) or not isinstance(luck, dict):
        failures.append("player combat contract missing")
    else:
        if not all(type(luck.get(key)) is int for key in ("base", "bonus", "total")) or luck.get("total") != luck.get("base") + luck.get("bonus") or type(combat.get("polymorphed")) is not bool or type(combat.get("two_weapon")) is not bool or not all(type(form.get(key)) is int for key in ("base_species_id", "current_species_id")):
            failures.append("player combat state mismatch")
        footwear = equipment.get("slots", {}).get("uarmf") if isinstance(equipment.get("slots"), dict) else None
        footwear_type = None if footwear is None else footwear.get("object_type") if isinstance(footwear, dict) else None
        expected_martial = dokick_martial_predicate(martial.get("role_species_id", -1), form.get("current_species_id", -1), footwear_type)
        if martial.get("source_macro") != "martial_bonus() || is_bigfoot(youmonst.data) || (uarmf && uarmf->otyp == KICKING_BOOTS)" or martial.get("constants") != {"pm_sasquatch": PM_SASQUATCH, "kicking_boots_object_type": KICKING_BOOTS} or martial.get("role_is_monk") is not (martial.get("role_species_id") == PM_MONK) or martial.get("role_is_samurai") is not (martial.get("role_species_id") == PM_SAMURAI) or any(martial.get(key) is not value for key, value in expected_martial.items()):
            failures.append("player martial predicate mismatch")
    wounded = conditions.get("wounded_legs")
    if not isinstance(wounded, dict) or not all(type(wounded.get(key)) is int for key in ("intrinsic", "extrinsic_sides")) or not all(type(wounded.get(key)) is bool for key in ("active", "left", "right")) or wounded.get("active") != bool(wounded.get("intrinsic") or wounded.get("extrinsic_sides")) or wounded.get("left") != bool(wounded.get("extrinsic_sides", 0) & WOUNDED_LEGS_LEFT) or wounded.get("right") != bool(wounded.get("extrinsic_sides", 0) & WOUNDED_LEGS_RIGHT):
        failures.append("player wounded-legs contract mismatch")
    inventory = equipment.get("inventory")
    slots = equipment.get("slots")
    if not isinstance(inventory, list) or not isinstance(slots, dict) or set(slots) != set(EQUIPMENT_SLOTS):
        failures.append("player equipment contract missing")
    else:
        ids: set[int] = set()
        normalized: set[tuple[int, int, int, str]] = set()
        for item in inventory:
            if not isinstance(item, dict) or not all(type(item.get(key)) is int for key in ("object_id", "object_type", "object_class", "quantity", "spe", "artifact", "worn_mask")) or not isinstance(item.get("inventory_letter"), str) or len(item["inventory_letter"]) != 1:
                failures.append("player inventory item malformed")
                break
            ids.add(item["object_id"])
            normalized.add((item["object_id"], item["object_type"], item["object_class"], item["inventory_letter"]))
        if len(ids) != len(inventory) or len(normalized) != len(inventory):
            failures.append("player inventory uniqueness mismatch")
        for slot, item in slots.items():
            if item is not None:
                if not isinstance(item, dict) or (item.get("object_id"), item.get("object_type"), item.get("object_class"), item.get("inventory_letter")) not in normalized:
                    failures.append(f"player equipment slot {slot} is not an inventory reference")
    expected_fields = ["attributes.effective.constitution", "attributes.effective.dexterity", "combat.luck", "conditions.wounded_legs", "resources.hp", "resources.armor_class", "combat.martial.effective"]
    reset_wall = completeness.get("reset_wall_kick")
    reset_wall_portable = completeness.get("reset_wall_kick_portable")
    basic_melee = completeness.get("basic_melee")
    if not isinstance(reset_wall, dict) or reset_wall.get("complete") is not True or reset_wall.get("fields") != expected_fields or not isinstance(basic_melee, dict) or basic_melee.get("complete") is not False or not isinstance(basic_melee.get("blockers"), list) or not basic_melee["blockers"]:
        failures.append("player completeness matrix mismatch")
    if reset_wall_portable is not None and (
        not isinstance(reset_wall_portable, dict)
        or reset_wall_portable.get("complete") is not False
        or not isinstance(reset_wall_portable.get("blockers"), list)
        or not reset_wall_portable["blockers"]
    ):
        failures.append("player portable wall-kick completeness mismatch")
    return failures


class PinnedNlePlayerReader:
    """Pinned read-only view of combat-relevant ``u``/inventory state."""

    def __init__(self, nethack_instance: Any):
        if getattr(sys, "platform", "") != "darwin":
            raise RuntimeError("native player oracle reader supports the pinned macOS NLE wheel only")
        path = Path(str(getattr(nethack_instance, "dlpath", ""))).resolve()
        if not path.is_file():
            raise RuntimeError("live NLE instance does not expose its copied libnethack path")
        try:
            import nle
            from nle.nethack.nethack import DLPATH
        except ImportError as error:  # pragma: no cover - live runtime guard
            raise RuntimeError("pinned NLE runtime identity is unavailable") from error
        if getattr(nle, "__version__", None) != "0.9.0":
            raise RuntimeError(f"native player reader requires NLE 0.9.0, saw {getattr(nle, '__version__', 'unknown')}")
        self._binary_sha256 = _sha256(path)
        if self._binary_sha256 != EXPECTED_BINARY_SHA256 or self._binary_sha256 != _sha256(Path(DLPATH).resolve()):
            raise RuntimeError("live libnethack does not match the pinned native player oracle binary")
        _assert_layout()
        offsets = _symbol_offsets(path)
        library = ctypes.CDLL(str(path))
        anchors = {name: _address(ctypes.cast(getattr(library, name), ctypes.c_void_p).value) for name in ("movemon", "rn2", "acurr")}
        slides = {anchors[name] - offsets[name] for name in anchors}
        if len(slides) != 1 or next(iter(slides)) <= 0:
            raise RuntimeError("NLE player symbol slide is inconsistent")
        base = next(iter(slides))
        self._library = library
        self._u_address = base + offsets["u"]
        self._youmonst_address = base + offsets["youmonst"]
        self._urole_address = base + offsets["urole"]
        self._context_address = base + offsets["context"]
        _aligned_nonzero(self._u_address, what="player u")
        _aligned_nonzero(self._youmonst_address, what="player youmonst")
        _aligned_nonzero(self._urole_address, what="player role")
        _aligned_nonzero(self._context_address, what="player context")
        self._youmonst = NativeMonst.from_address(self._youmonst_address)
        self._invent = ctypes.c_void_p.from_address(base + offsets["invent"])
        self._equipment = {slot: ctypes.c_void_p.from_address(base + offsets[slot]) for slot in EQUIPMENT_SLOTS}
        self._moves = ctypes.c_long.from_address(base + offsets["moves"])
        self._acurr = getattr(library, "acurr")
        self._acurr.argtypes = [ctypes.c_int]
        self._acurr.restype = ctypes.c_byte

    def _inventory(self) -> tuple[dict[int, dict[str, int]], dict[str, dict[str, int] | None]]:
        objects: dict[int, dict[str, int]] = {}
        address = _address(self._invent.value)
        for _ in range(MAX_OBJECTS):
            if not address:
                break
            _aligned_nonzero(address, what="player inventory object")
            if address in objects:
                raise RuntimeError("cycle in source invent list")
            obj = NativeObj.from_address(address)
            if int(obj.where) != OBJ_INVENT or int(obj.o_id) <= 0 or not (32 <= int(obj.invlet) <= 126):
                raise RuntimeError("invalid source inventory object")
            # NativeObj's pinned ABI carries the object status bits in the
            # six-byte padding field verified by nle_native_entities.  Keep
            # the named curse/bless facts in the reset projection so source
            # consumers (notably dogfood()) do not have to treat an omitted
            # bit as a guessed value.
            bits = bytes(int(value) for value in obj._bits_padding)
            objects[address] = {
                "object_id": int(obj.o_id),
                "object_type": int(obj.otyp),
                "object_class": int(obj.oclass),
                "inventory_letter": chr(int(obj.invlet)),
                "quantity": int(obj.quan),
                "spe": int(obj.spe),
                "artifact": int(obj.oartifact),
                "worn_mask": int(obj.owornmask),
                "cursed": bool(bits[0] & 0x01),
                "blessed": bool(bits[0] & 0x02),
            }
            address = _address(obj.nobj)
        else:
            raise RuntimeError("source invent list exceeded bounded traversal limit")
        if len({item["object_id"] for item in objects.values()}) != len(objects):
            raise RuntimeError("source invent list has duplicate object IDs")
        slots: dict[str, dict[str, int] | None] = {}
        for slot, pointer in self._equipment.items():
            address = _address(pointer.value)
            if not address:
                slots[slot] = None
            elif address not in objects:
                raise RuntimeError(f"source {slot} does not point into source inventory")
            else:
                slots[slot] = objects[address]
        return objects, slots

    def snapshot(self) -> NativePlayerSnapshot:
        raw = ctypes.string_at(self._u_address, EXPECTED_YOU_SIZE)
        if len(raw) != EXPECTED_YOU_SIZE:
            raise RuntimeError("short source player read")
        attrs_effective = {
            name: int(self._acurr(index))
            for index, name in enumerate(("strength", "intelligence", "wisdom", "dexterity", "constitution", "charisma"))
        }
        attrs_raw = {
            name: {
                "base": _i8(raw, YOU_OFFSETS["acurr"] + index),
                "bonus": _i8(raw, YOU_OFFSETS["abon"] + index),
                "temporary": _i8(raw, YOU_OFFSETS["atemp"] + index),
            }
            for index, name in enumerate(("strength", "intelligence", "wisdom", "dexterity", "constitution", "charisma"))
        }
        # ``dokick.c`` calls exercise() before its injury RNG.  The resulting
        # public attribute changes are gated by these reset-only accumulators
        # and by context.next_attrib_check, so preserve them as source
        # evidence rather than claiming the visible attributes are sufficient
        # for a portable wall-KICK implementation.
        attr_names = ("strength", "intelligence", "wisdom", "dexterity", "constitution", "charisma")
        exercise_state = {
            "aexe": {name: _i8(raw, YOU_OFFSETS["aexe"] + index) for index, name in enumerate(attr_names)},
            "atime": {name: _i8(raw, YOU_OFFSETS["atime"] + index) for index, name in enumerate(attr_names)},
            # Darwin arm64 keeps the first long in context_info at offset 32:
            # four unsigned ints (0..24), then the aligned long.
            "next_attrib_check": _i64(ctypes.string_at(self._context_address, 40), 32),
        }
        intrinsic = _i64(raw, YOU_OFFSETS["uprops"] + PROP_WOUNDED_LEGS * EXPECTED_PROP_SIZE + 16)
        extrinsic = _i64(raw, YOU_OFFSETS["uprops"] + PROP_WOUNDED_LEGS * EXPECTED_PROP_SIZE)
        inventory, equipment = self._inventory()
        role_malenum = ctypes.c_int16.from_address(self._urole_address + ROLE_MALENUM_OFFSET).value
        martial_skill = raw[YOU_OFFSETS["weapon_skills"] + P_BARE_HANDED_COMBAT * 4]
        martial_max_skill = raw[YOU_OFFSETS["weapon_skills"] + P_BARE_HANDED_COMBAT * 4 + 1]
        current_species_id = _i32(raw, YOU_OFFSETS["umonnum"])
        if int(self._youmonst.mnum) != current_species_id:
            raise RuntimeError("source u.umonnum disagrees with source youmonst species")
        footwear = equipment["uarmf"]
        martial = dokick_martial_predicate(
            role_malenum,
            current_species_id,
            None if footwear is None else int(footwear["object_type"]),
        )
        upolyd = current_species_id != _i32(raw, YOU_OFFSETS["umonster"])
        hp = _i32(raw, YOU_OFFSETS["mh"] if upolyd else YOU_OFFSETS["uhp"])
        hp_max = _i32(raw, YOU_OFFSETS["mhmax"] if upolyd else YOU_OFFSETS["uhpmax"])
        if not (1 <= _i32(raw, YOU_OFFSETS["ulevel"]) <= 30 and 0 <= hp <= hp_max and hp_max > 0):
            raise RuntimeError("invalid source player level or HP state")
        player = {
            "coordinates": {"native_x": _i8(raw, YOU_OFFSETS["ux"]), "native_y": _i8(raw, YOU_OFFSETS["uy"]), "nle_x": _i8(raw, YOU_OFFSETS["ux"]) - 1, "nle_y": _i8(raw, YOU_OFFSETS["uy"])},
            "resources": {"experience_level": _i32(raw, YOU_OFFSETS["ulevel"]), "hp": hp, "hp_max": hp_max, "human_hp": _i32(raw, YOU_OFFSETS["uhp"]), "human_hp_max": _i32(raw, YOU_OFFSETS["uhpmax"]), "energy": _i32(raw, YOU_OFFSETS["uen"]), "energy_max": _i32(raw, YOU_OFFSETS["uenmax"]), "armor_class": _i8(raw, YOU_OFFSETS["uac"]), "hunger": _i32(raw, YOU_OFFSETS["uhunger"]), "hunger_state": _u32(raw, YOU_OFFSETS["uhs"])},
            "attributes": {"effective": attrs_effective, "components": attrs_raw},
            "exercise_state": exercise_state,
            "combat": {"luck": {"base": _i8(raw, YOU_OFFSETS["uluck"]), "bonus": _i8(raw, YOU_OFFSETS["moreluck"]), "total": _i8(raw, YOU_OFFSETS["uluck"]) + _i8(raw, YOU_OFFSETS["moreluck"])}, "polymorphed": upolyd, "monster_form": {"base_species_id": _i32(raw, YOU_OFFSETS["umonster"]), "current_species_id": current_species_id}, "two_weapon": bool(raw[YOU_OFFSETS["twoweap"]]), "martial": {"source_macro": "martial_bonus() || is_bigfoot(youmonst.data) || (uarmf && uarmf->otyp == KICKING_BOOTS)", "constants": {"pm_sasquatch": PM_SASQUATCH, "kicking_boots_object_type": KICKING_BOOTS}, "role_species_id": int(role_malenum), "role_is_monk": role_malenum == PM_MONK, "role_is_samurai": role_malenum == PM_SAMURAI, **martial, "bare_handed_skill": int(martial_skill), "bare_handed_max_skill": int(martial_max_skill)}},
            "conditions": {"trap_timeout": _u32(raw, YOU_OFFSETS["utrap"]), "trap_type": _u32(raw, YOU_OFFSETS["utraptype"]), "wounded_legs": {"intrinsic": intrinsic, "extrinsic_sides": extrinsic, "active": bool(intrinsic or extrinsic), "left": bool(extrinsic & WOUNDED_LEGS_LEFT), "right": bool(extrinsic & WOUNDED_LEGS_RIGHT)}},
            "equipment": {"inventory": list(inventory.values()), "slots": equipment},
            "scheduler": {"movement_points": int(self._youmonst.movement), "source_moves": int(self._moves.value)},
            "completeness": {"reset_wall_kick": {"complete": True, "fields": ["attributes.effective.constitution", "attributes.effective.dexterity", "combat.luck", "conditions.wounded_legs", "resources.hp", "resources.armor_class", "combat.martial.effective"]}, "reset_wall_kick_portable": {"complete": False, "blockers": ["exercise_state and whole-turn draw ownership still require an action-bound portable contract"]}, "basic_melee": {"complete": False, "blockers": ["weapon damage tables, monster AC/resistance, attack sequence, and full skill/object semantics are intentionally not exported"]}},
        }
        return NativePlayerSnapshot(binary_sha256=self._binary_sha256, source_turn=int(self._moves.value), player=player)

    def validate_against_public_pre_action(self, snapshot: NativePlayerSnapshot, observation: dict[str, Any]) -> dict[str, int]:
        """Fail hard if exact source fields disagree with public NLE planes."""
        blstats = observation.get("blstats")
        if getattr(blstats, "shape", None) != (27,):
            raise ValueError("expected exact 27-element NLE blstats plane")
        player = snapshot.player
        effective = player["attributes"]["effective"]
        expected = {
            "x": player["coordinates"]["nle_x"], "y": player["coordinates"]["nle_y"], "strength": effective["strength"], "dexterity": effective["dexterity"], "constitution": effective["constitution"], "intelligence": effective["intelligence"], "wisdom": effective["wisdom"], "charisma": effective["charisma"], "hp": player["resources"]["hp"], "hp_max": player["resources"]["hp_max"], "energy": player["resources"]["energy"], "energy_max": player["resources"]["energy_max"], "armor_class": player["resources"]["armor_class"], "experience_level": player["resources"]["experience_level"], "time": snapshot.source_turn, "hunger_state": player["resources"]["hunger_state"],
        }
        mismatches = {name: (value, int(blstats[PUBLIC_BLSTATS[name]])) for name, value in expected.items() if value != int(blstats[PUBLIC_BLSTATS[name]])}
        if mismatches:
            raise RuntimeError(f"native player source/public blstats disagreement: {mismatches}")
        letters = observation.get("inv_letters")
        oclasses = observation.get("inv_oclasses")
        if getattr(letters, "shape", None) != (55,) or getattr(oclasses, "shape", None) != (55,):
            raise ValueError("expected exact 55-element NLE inventory planes")
        public_inventory = {(chr(int(letter)), int(oclass)) for letter, oclass in zip(letters, oclasses, strict=True) if int(letter)}
        native_inventory = {(item["inventory_letter"], item["object_class"]) for item in player["equipment"]["inventory"]}
        if public_inventory != native_inventory:
            raise RuntimeError("native player inventory letters/classes disagree with public NLE inventory planes")
        return {"verified_blstats": len(expected), "verified_inventory_entries": len(native_inventory), "public_condition_mask": int(blstats[PUBLIC_BLSTATS["condition"]])}
