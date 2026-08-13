"""Read-only authoritative entity/underlay snapshots from pinned NLE 0.9.0.

Unlike NLE's rendered observation planes, NetHack's in-process ``level``
object contains the actual current-level monster and floor-object lists.  The
macOS v0.9.0 wheel keeps the local ``_level`` symbol.  This module resolves it
only after proving the copied per-environment Mach-O is byte-identical to the
installed oracle binary and after two exported function addresses produce the
same ASLR slide.

The ctypes ABI below is pinned to source commit
``2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa`` and independently checked with
an exact-header ``sizeof``/``offsetof`` helper during development.  Readers
only copy memory.  They expose no pointer addresses, write operation, restore
operation, or source-derived behaviour; this is an oracle-side export.
"""

from __future__ import annotations

import ctypes
import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SOURCE_COMMIT = "2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa"
EXPECTED_BINARY_SHA256 = "7ac1270dfd5fa0a5fb2f715ef6a7151058f06cda595e4b722ac6d070ce0f2057"
COLNO = 80
ROWNO = 21
MAX_MONSTERS = 4096
MAX_OBJECTS = 8192
MAX_OBJECT_TYPES = 453
MAX_SPECIES = 381
NATTK = 6
ATTACK_STRUCT_SIZE = 4
GLYPH_OBJ_OFF = 1906
CORPSE_OBJECT_TYPE = 240
BOULDER_OBJECT_TYPE = 447
STATUE_OBJECT_TYPE = 448
NORMAL_SPEED = 12

# ``include/monflag.h`` static species capabilities.  These values are
# exported as reset facts, not interpreted as a destination policy.  Keeping
# the names here makes a later scheduler gate auditable against the pinned
# source header instead of relying on a species-id allowlist.
M1_SWIM = 0x00000002
M1_AMORPHOUS = 0x00000004
M1_WALLWALK = 0x00000008
M1_TUNNEL = 0x00000020
M1_CONCEAL = 0x00000080
M1_HIDE = 0x00000100
M1_NOTAKE = 0x00000800
M1_NOEYES = 0x00001000
M1_NOHANDS = 0x00002000
M1_TPORT = 0x02000000
M2_DOMESTIC = 0x00400000
M2_WANDER = 0x00800000
M2_STALK = 0x01000000
M2_GREEDY = 0x10000000
M2_JEWELS = 0x20000000
M2_COLLECT = 0x40000000
M2_MAGIC = 0x80000000
M3_COVETOUS = 0x001F

# ``include/monflag.h`` generation/corpse bits.  These are exported as the
# exact packed ``permonst._geno`` value plus decoded convenience fields; the
# latter are checked against the former by the snapshot validator.
G_FREQ_MASK = 0x0007
G_NOCORPSE = 0x0010

# Exact Darwin arm64 ABI measurements from the pinned NLE 0.9.0 headers.
EXPECTED_MONST_SIZE = 144
EXPECTED_PERMONST_SIZE = 72
EXPECTED_OBJ_SIZE = 96
EXPECTED_OBJCLASS_SIZE = 40
EXPECTED_RM_SIZE = 8
EXPECTED_DLEVEL_SIZE = 40368
EXPECTED_LEVEL_MONLIST_OFFSET = 40336
EXPECTED_MEXTRA_SIZE = 56
EXPECTED_EDOG_SIZE = 56


class NativeRm(ctypes.Structure):
    _fields_ = [("glyph", ctypes.c_int), ("typ", ctypes.c_int8), ("seenv", ctypes.c_uint8), ("_flags", ctypes.c_uint16)]


class NativeCoord(ctypes.Structure):
    """Pinned ``coord``/``xchar`` pair; signedness preserves sentinels."""

    _fields_ = [("x", ctypes.c_int8), ("y", ctypes.c_int8)]


class NativeMonst(ctypes.Structure):
    _fields_ = [
        ("nmon", ctypes.c_void_p),
        ("data", ctypes.c_void_p),
        ("m_id", ctypes.c_uint),
        ("mnum", ctypes.c_int16),
        ("cham", ctypes.c_int16),
        ("movement", ctypes.c_int16),
        ("m_lev", ctypes.c_uint8),
        ("malign", ctypes.c_int8),
        ("mx", ctypes.c_int8),
        ("my", ctypes.c_int8),
        ("mux", ctypes.c_int8),
        ("muy", ctypes.c_int8),
        ("mtrack", NativeCoord * 4),
        ("mhp", ctypes.c_int),
        ("mhpmax", ctypes.c_int),
        ("mappearance", ctypes.c_uint),
        ("m_ap_type", ctypes.c_uint8),
        ("mtame", ctypes.c_int8),
        ("mextrinsics", ctypes.c_uint16),
        ("mspec_used", ctypes.c_int),
        # Seven source ``unsigned`` bitfield storage bytes, then padding.
        ("_bits", ctypes.c_uint8 * 12),
        ("mstrategy", ctypes.c_ulong),
        ("mtrapseen", ctypes.c_long),
        ("mlstmv", ctypes.c_long),
        ("mspare1", ctypes.c_long),
        ("minvent", ctypes.c_void_p),
        ("mw", ctypes.c_void_p),
        ("misc_worn_check", ctypes.c_long),
        ("weapon_check", ctypes.c_int8),
        ("_weapon_padding", ctypes.c_uint8 * 3),
        ("meating", ctypes.c_int),
        ("mextra", ctypes.c_void_p),
    ]


class NativeMextra(ctypes.Structure):
    """ABI-checked prefix required to locate an optional ``edog`` record."""

    _fields_ = [
        ("mname", ctypes.c_void_p),
        ("egd", ctypes.c_void_p),
        ("epri", ctypes.c_void_p),
        ("eshk", ctypes.c_void_p),
        ("emin", ctypes.c_void_p),
        ("edog", ctypes.c_void_p),
        ("mcorpsenm", ctypes.c_int),
    ]


class NativeEdog(ctypes.Structure):
    """Exact Darwin arm64 ``struct edog`` layout from the pinned headers."""

    _fields_ = [
        ("droptime", ctypes.c_long),
        ("dropdist", ctypes.c_uint),
        ("apport", ctypes.c_int),
        ("whistletime", ctypes.c_long),
        ("hungrytime", ctypes.c_long),
        ("ogoal", NativeCoord),
        ("abuse", ctypes.c_int),
        ("revivals", ctypes.c_int),
        ("mhpmax_penalty", ctypes.c_int),
        ("_flags", ctypes.c_uint8),
    ]


class NativePermonst(ctypes.Structure):
    _fields_ = [
        ("mname", ctypes.c_void_p),
        ("mlet", ctypes.c_char),
        ("mlevel", ctypes.c_int8),
        ("mmove", ctypes.c_int8),
        ("ac", ctypes.c_int8),
        ("mr", ctypes.c_int8),
        ("maligntyp", ctypes.c_int8),
        ("_geno", ctypes.c_uint16),
        ("_attacks", ctypes.c_uint8 * 24),
        ("_cwt", ctypes.c_uint16),
        ("_cnutrit", ctypes.c_uint16),
        ("msound", ctypes.c_uint8),
        ("msize", ctypes.c_uint8),
        ("mresists", ctypes.c_uint8),
        ("mconveys", ctypes.c_uint8),
        ("mflags1", ctypes.c_uint64),
        ("mflags2", ctypes.c_uint64),
        ("mflags3", ctypes.c_uint16),
        ("difficulty", ctypes.c_uint8),
        ("mcolor", ctypes.c_uint8),
    ]


# ``src/drawing.c:def_monsyms`` and ``include/monsym.h`` are the pinned
# default symbol contract.  ``permonst.mlet`` stores the class index, not the
# printable screen character; keep this table explicit and independent of
# the NLE Python module.
MONSTER_CLASS_CHARS = {
    **{index: chr(ord("a") + index - 1) for index in range(1, 27)},
    **{index: chr(ord("A") + index - 27) for index in range(27, 53)},
    53: "@", 54: " ", 55: "'", 56: "&", 57: ";", 58: ":", 59: "~", 60: "]",
}


class NativeObj(ctypes.Structure):
    _fields_ = [
        ("nobj", ctypes.c_void_p),
        ("nexthere", ctypes.c_void_p),
        ("cobj", ctypes.c_void_p),
        ("o_id", ctypes.c_uint),
        ("ox", ctypes.c_int8),
        ("oy", ctypes.c_int8),
        ("otyp", ctypes.c_int16),
        ("owt", ctypes.c_uint),
        ("_weight_padding", ctypes.c_uint8 * 4),
        ("quan", ctypes.c_long),
        ("spe", ctypes.c_int8),
        ("oclass", ctypes.c_int8),
        ("invlet", ctypes.c_int8),
        ("oartifact", ctypes.c_int8),
        ("where", ctypes.c_int8),
        ("timed", ctypes.c_int8),
        ("_bits_padding", ctypes.c_uint8 * 6),
        ("corpsenm", ctypes.c_int),
        ("usecount", ctypes.c_int),
        ("oeaten", ctypes.c_uint),
        ("age", ctypes.c_long),
        ("owornmask", ctypes.c_long),
        ("oextra", ctypes.c_void_p),
    ]


class NativeObjClass(ctypes.Structure):
    """Pinned prefix of ``struct objclass`` used for reset mapglyph data.

    The NLE RL window remaps a normal object's raw type through the runtime
    ``oc_descr_idx`` table before exposing its glyph.  This prefix is enough
    to read that source-owned display mapping; mapglyph's class/color still
    come from the original object entry.  The ABI is
    checked below instead of relying on a Python object-class table (which
    deliberately reports the unshuffled compile-time descriptions).
    """

    _fields_ = [
        ("oc_name_idx", ctypes.c_int16),
        ("oc_descr_idx", ctypes.c_int16),
        ("_pointer_padding", ctypes.c_int32),
        ("oc_uname", ctypes.c_void_p),
        # The pinned NLE build's clang ABI packs the twelve unsigned
        # bitfields into three bytes (verified independently against the
        # headers); do not assume a host compiler's ctypes bitfield rules.
        ("_bits", ctypes.c_uint8 * 3),
        ("oc_subtyp", ctypes.c_int8),
        ("oc_oprop", ctypes.c_uint8),
        ("oc_class", ctypes.c_int8),
        ("oc_delay", ctypes.c_int8),
        ("oc_color", ctypes.c_uint8),
        ("oc_prob", ctypes.c_int16),
        ("oc_weight", ctypes.c_uint16),
        ("oc_cost", ctypes.c_int16),
        ("oc_wsdam", ctypes.c_int8),
        ("oc_wldam", ctypes.c_int8),
        ("oc_oc1", ctypes.c_int8),
        ("oc_oc2", ctypes.c_int8),
        ("oc_nutrition", ctypes.c_uint16),
    ]


def _native_object_record(obj: NativeObj) -> dict[str, Any]:
    """Copy the reset object semantics needed by source ``dogfood``.

    ``obj.h`` stores ``cursed`` as the first bit of the pinned object
    bitfield.  The raw bytes are retained as an ABI-checked, pointer-free
    reset fact; gold consumers may use only the named semantic bits below.
    Legacy readers continue to accept the original id/type/quantity subset.
    """

    bits = bytes(int(value) for value in obj._bits_padding)
    return {
        "object_id": int(obj.o_id),
        "object_type": int(obj.otyp),
        "quantity": int(obj.quan),
        "object_class": int(obj.oclass),
        "cursed": bool(bits[0] & 0x01),
        "blessed": bool(bits[0] & 0x02),
        "artifact": int(obj.oartifact),
        "corpsenm": int(obj.corpsenm),
        "age": int(obj.age),
        "spe": int(obj.spe),
        "worn_mask": int(obj.owornmask),
        "bitfield_hex": bits.hex(),
    }


def _monster_presentation(species: NativePermonst, species_id: int, *, tame: bool) -> dict[str, Any]:
    raw_mlet = species.mlet
    if isinstance(raw_mlet, bytes):
        mlet = int(raw_mlet[0]) if raw_mlet else -1
    else:
        mlet = int(raw_mlet)
    char = MONSTER_CLASS_CHARS.get(mlet)
    if not isinstance(char, str) or len(char) != 1:
        raise RuntimeError(f"pinned source monster class {mlet} has no default presentation symbol")
    glyph = 381 + species_id if tame else species_id
    return {
        "char": char,
        "glyph": int(glyph),
        "color": int(species.mcolor),
        "monster_class": mlet,
        "provenance": "nle_reset_monster_class_symbol",
    }


def _source_string(pointer: int, *, what: str, limit: int = 128) -> str:
    """Read one bounded NUL-terminated static source string.

    ``permonst.mname`` is a pointer into the pinned binary's read-only data.
    It is useful evidence for reports, but it must never become an unchecked
    native-pointer dependency in a reset projection.
    """

    if pointer <= 0:
        raise RuntimeError(f"invalid {what} pointer")
    raw = ctypes.string_at(pointer, limit)
    if b"\x00" not in raw:
        raise RuntimeError(f"{what} is not a bounded NUL-terminated source string")
    value = raw.split(b"\x00", 1)[0]
    try:
        decoded = value.decode("ascii")
    except UnicodeDecodeError as error:
        raise RuntimeError(f"{what} is not ASCII in the pinned source table") from error
    if not decoded:
        raise RuntimeError(f"{what} is empty in the pinned source table")
    return decoded


def _monster_species_rules(species: NativePermonst, species_id: int) -> dict[str, Any]:
    """Copy static ``permonst`` branch inputs without selecting behavior.

    ``m_move`` dispatches on runtime flags first (tame/shopkeeper/guard/etc.)
    and then on static species capabilities.  This compact reset record is a
    source identity join for validity reports and scheduler eligibility; it
    intentionally does not claim that any profile is implemented by gold.
    """

    if not 0 <= int(species_id) < MAX_SPECIES:
        raise RuntimeError("source species ID is outside the pinned mons table")
    mflags1, mflags2, mflags3 = int(species.mflags1), int(species.mflags2), int(species.mflags3)
    capability_bits = {
        "swim": bool(mflags1 & M1_SWIM),
        "amorphous": bool(mflags1 & M1_AMORPHOUS),
        "wallwalk": bool(mflags1 & M1_WALLWALK),
        "tunnel": bool(mflags1 & M1_TUNNEL),
        "conceal_underlay": bool(mflags1 & M1_CONCEAL),
        "hide": bool(mflags1 & M1_HIDE),
        "cannot_pickup": bool(mflags1 & M1_NOTAKE),
        "no_eyes": bool(mflags1 & M1_NOEYES),
        "no_hands": bool(mflags1 & M1_NOHANDS),
        "teleport": bool(mflags1 & M1_TPORT),
        "domestic": bool(mflags2 & M2_DOMESTIC),
        "wander": bool(mflags2 & M2_WANDER),
        "stalk": bool(mflags2 & M2_STALK),
        "likes_gold": bool(mflags2 & M2_GREEDY),
        "likes_gems": bool(mflags2 & M2_JEWELS),
        "collects_objects": bool(mflags2 & M2_COLLECT),
        "likes_magic": bool(mflags2 & M2_MAGIC),
        "covetous": bool(mflags3 & M3_COVETOUS),
        # monmove.c::m_move computes ``can_open`` as
        # ``!(nohands(ptr) || verysmall(ptr))``.  Preserve the independent
        # permonst size bit so a gold scheduler may admit only the exact
        # D_CLOSED -> D_ISOPEN branch; older receipts without this field stay
        # valid but cannot claim door-opening eligibility.
        "very_small": int(species.msize) < 1,  # MZ_SMALL == 1
    }
    # This label is deliberately descriptive: it records which source-owned
    # family must be handled before ordinary m_move, without asserting that
    # a gold implementation exists for that family.
    if capability_bits["domestic"]:
        branch_profile = "dog_move_domestic"
    elif capability_bits["covetous"]:
        branch_profile = "covetous_special"
    elif capability_bits["teleport"]:
        branch_profile = "species_teleport_capability"
    elif capability_bits["swim"]:
        # The pinned dlvl-1 newt (PM_NEWT) still uses the common m_move /
        # mfndpos selector, but its swimmer predicate admits pools and its
        # source presentation must conserve the water underlay.  Keep this
        # distinct from unimplemented wallwalk/tunnel/conceal branches.
        branch_profile = "swimming_m_move_candidate"
    elif any(capability_bits[name] for name in ("conceal_underlay", "hide", "tunnel", "wallwalk", "amorphous")):
        branch_profile = "terrain_or_underlay_special"
    elif any(capability_bits[name] for name in ("likes_gold", "likes_gems", "collects_objects", "likes_magic")):
        branch_profile = "object_interest_special"
    elif capability_bits["wander"] or capability_bits["stalk"]:
        branch_profile = "target_or_wander_special"
    else:
        branch_profile = "ordinary_m_move_candidate"
    raw_mlet = species.mlet
    mlet = int(raw_mlet[0]) if isinstance(raw_mlet, bytes) and raw_mlet else int(raw_mlet)
    raw_attacks = tuple(int(value) for value in species._attacks)
    expected_attack_bytes = NATTK * ATTACK_STRUCT_SIZE
    if len(raw_attacks) != expected_attack_bytes:
        # This is an ABI/schema failure, not a reason to truncate or guess a
        # source attack matrix.  NativePermonst's layout assertion below also
        # checks the array offset and total size.
        raise RuntimeError(
            f"pinned permonst attack matrix has {len(raw_attacks)} bytes; "
            f"expected {expected_attack_bytes}"
        )
    attacks = [
        {
            "slot": slot,
            # Keep the exact source field names from struct attack.  These are
            # IDs, not gold-side behavior labels; interpretation belongs to a
            # source-backed combat implementation.
            "aatyp": raw_attacks[offset],
            "adtyp": raw_attacks[offset + 1],
            "damn": raw_attacks[offset + 2],
            "damd": raw_attacks[offset + 3],
        }
        for slot, offset in enumerate(range(0, expected_attack_bytes, ATTACK_STRUCT_SIZE))
    ]
    combat_profile = {
        "armor_class": int(species.ac),
        "level": int(species.mlevel),
        "magic_resistance": int(species.mr),
        "resistances": int(species.mresists),
        "attacks": attacks,
        "attack_bytes_hex": bytes(raw_attacks).hex(),
        "provenance": "nle_reset_permonst_attack_profile_v1",
    }
    geno = int(species._geno)
    return {
        "species_id": int(species_id),
        "name": _source_string(_address(species.mname), what="permonst.mname"),
        "monster_class": mlet,
        "base_speed": int(species.mmove),
        "mflags1": mflags1,
        "mflags2": mflags2,
        "mflags3": mflags3,
        "capabilities": capability_bits,
        "branch_profile": branch_profile,
        "combat": combat_profile,
        "geno": geno,
        "generation_frequency": geno & G_FREQ_MASK,
        "corpse_weight": int(species._cwt),
        "corpse_nutrition": int(species._cnutrit),
        "no_corpse": bool(geno & G_NOCORPSE),
        "provenance": "nle_reset_permonst_static_profile_v2",
    }


class NativeLevel(ctypes.Structure):
    _fields_ = [
        ("locations", (NativeRm * ROWNO) * COLNO),
        ("objects", ctypes.c_void_p * (COLNO * ROWNO)),
        ("monsters", ctypes.c_void_p * (COLNO * ROWNO)),
        ("objlist", ctypes.c_void_p),
        ("buriedobjlist", ctypes.c_void_p),
        ("monlist", ctypes.c_void_p),
        ("damagelist", ctypes.c_void_p),
        ("bonesinfo", ctypes.c_void_p),
        ("_flags", ctypes.c_uint8 * 8),
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _symbol_offsets(path: Path) -> dict[str, int]:
    if sys.platform != "darwin":
        raise RuntimeError("native entity oracle reader supports the pinned macOS NLE wheel only")
    result = subprocess.run(["nm", "-a", str(path)], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    wanted = {"level", "moves", "monstermoves", "movemon", "rn2", "objects", "mons"}
    pattern = re.compile(r"^([0-9A-Fa-f]+)\s+\w\s+_(level|moves|monstermoves|movemon|rn2|objects|mons)$")
    offsets: dict[str, int] = {}
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            offsets[match.group(2)] = int(match.group(1), 16)
    if set(offsets) != wanted:
        raise RuntimeError(f"pinned NLE binary lacks required unambiguous entity symbols: {sorted(offsets)}")
    return offsets


def _assert_layout() -> None:
    checks = (
        (ctypes.sizeof(NativeRm), EXPECTED_RM_SIZE, "rm size"),
        (ctypes.sizeof(NativeCoord), 2, "coord size"),
        (ctypes.sizeof(NativeMonst), EXPECTED_MONST_SIZE, "monst size"),
        (ctypes.sizeof(NativePermonst), EXPECTED_PERMONST_SIZE, "permonst size"),
        (NativePermonst.mlevel.offset, 9, "permonst.mlevel"),
        (NativePermonst.mlet.offset, 8, "permonst.mlet"),
        (NativePermonst.mmove.offset, 10, "permonst.mmove"),
        (NativePermonst.ac.offset, 11, "permonst.ac"),
        (NativePermonst.mr.offset, 12, "permonst.mr"),
        (NativePermonst._attacks.offset, 16, "permonst.mattk"),
        (NativePermonst.mresists.offset, 46, "permonst.mresists"),
        (NativePermonst.mflags1.offset, 48, "permonst.mflags1"),
        (NativePermonst.mflags2.offset, 56, "permonst.mflags2"),
        (NativePermonst.mflags3.offset, 64, "permonst.mflags3"),
        (NativePermonst.mcolor.offset, 67, "permonst.mcolor"),
        (ctypes.sizeof(NativeObj), EXPECTED_OBJ_SIZE, "obj size"),
        (ctypes.sizeof(NativeObjClass), EXPECTED_OBJCLASS_SIZE, "objclass size"),
        (NativeObjClass.oc_descr_idx.offset, 2, "objclass.oc_descr_idx"),
        (NativeObjClass.oc_class.offset, 21, "objclass.oc_class"),
        (NativeObjClass.oc_color.offset, 23, "objclass.oc_color"),
        (ctypes.sizeof(NativeMextra), EXPECTED_MEXTRA_SIZE, "mextra size"),
        (ctypes.sizeof(NativeEdog), EXPECTED_EDOG_SIZE, "edog size"),
        (ctypes.sizeof(NativeLevel), EXPECTED_DLEVEL_SIZE, "dlevel size"),
        (NativeMonst.m_id.offset, 16, "monst.m_id"),
        (NativeMonst.movement.offset, 24, "monst.movement"),
        (NativeMonst.m_lev.offset, 26, "monst.m_lev"),
        (NativeMonst.mx.offset, 28, "monst.mx"),
        (NativeMonst.my.offset, 29, "monst.my"),
        (NativeMonst.mux.offset, 30, "monst.mux"),
        (NativeMonst.muy.offset, 31, "monst.muy"),
        (NativeMonst.mtrack.offset, 32, "monst.mtrack"),
        (NativeMonst.mhp.offset, 40, "monst.mhp"),
        (NativeMonst.mtame.offset, 53, "monst.mtame"),
        (NativeMonst._bits.offset, 60, "monst bitfields"),
        (NativeMonst.mstrategy.offset, 72, "monst.mstrategy"),
        (NativeMonst.mtrapseen.offset, 80, "monst.mtrapseen"),
        (NativeMonst.mlstmv.offset, 88, "monst.mlstmv"),
        (NativeMonst.meating.offset, 132, "monst.meating"),
        (NativeMonst.mextra.offset, 136, "monst.mextra"),
        (NativeMextra.edog.offset, 40, "mextra.edog"),
        (NativeMextra.mcorpsenm.offset, 48, "mextra.mcorpsenm"),
        (NativeEdog.droptime.offset, 0, "edog.droptime"),
        (NativeEdog.dropdist.offset, 8, "edog.dropdist"),
        (NativeEdog.apport.offset, 12, "edog.apport"),
        (NativeEdog.whistletime.offset, 16, "edog.whistletime"),
        (NativeEdog.hungrytime.offset, 24, "edog.hungrytime"),
        (NativeEdog.ogoal.offset, 32, "edog.ogoal"),
        (NativeEdog.abuse.offset, 36, "edog.abuse"),
        (NativeEdog.revivals.offset, 40, "edog.revivals"),
        (NativeEdog.mhpmax_penalty.offset, 44, "edog.mhpmax_penalty"),
        (NativeObj.nexthere.offset, 8, "obj.nexthere"),
        (NativeObj.where.offset, 52, "obj.where"),
        (NativeLevel.monlist.offset, EXPECTED_LEVEL_MONLIST_OFFSET, "level.monlist"),
    )
    failed = [f"{name}: {actual} != {expected}" for actual, expected, name in checks if actual != expected]
    if failed:
        raise RuntimeError("pinned NLE native ABI layout mismatch: " + "; ".join(failed))


def _address(value: Any) -> int:
    return int(value or 0)


def _aligned_nonzero(pointer: int, *, what: str) -> None:
    if pointer <= 0 or pointer % ctypes.alignment(ctypes.c_void_p):
        raise RuntimeError(f"invalid {what} pointer")


@dataclass(frozen=True)
class NativeEntitySnapshot:
    binary_sha256: str
    moves: int
    monstermoves: int
    entities: tuple[dict[str, Any], ...]
    object_stacks: tuple[dict[str, Any], ...] = ()

    def public_record(self) -> dict[str, Any]:
        record = {
            "schema": "gamebench.nethack.native_entity_snapshot.v1",
            "source_commit": SOURCE_COMMIT,
            "binary_sha256": self.binary_sha256,
            "coordinate_contract": "native level (x,y) is emitted as NLE plane (x-1,y); native_x preserves the source level coordinate",
            "source_turn": {"moves": self.moves, "monstermoves": self.monstermoves},
            "turn_queue": [entity["entity_id"] for entity in self.entities],
            "entities": list(self.entities),
        }
        if self.object_stacks:
            record["object_stacks"] = list(self.object_stacks)
        return record

    def scheduler_export(self) -> dict[str, Any]:
        """Return a pre-action export accepted by the generic validity gate.

        The caller must invoke this only at a source observation boundary
        before forwarding the next action.  The native snapshot's ``moves``
        counter is a source time coordinate, not a seed-derived schedule.
        """

        return {
            "schema": "gamebench.nethack.authoritative_entity_scheduler_export.v1",
            "source_adapter": "pinned_native_macho_v1",
            "source_step": self.moves,
            "captured_before_action": True,
            "gold_scheduler_implementation_eligible": False,
            "scope": "assertion-only native source evidence; no general AI/pathing/collision/combat or destination implementation because mux/muy, mtrack, full status/strategy context, player state, and map decision inputs are not exported",
            "turn_queue": [entity["entity_id"] for entity in self.entities],
            "entities": list(self.entities),
        }


class PinnedNleEntityReader:
    """Verified, read-only view of NLE's exact current-level dynamic state."""

    def __init__(self, nethack_instance: Any):
        if getattr(sys, "platform", "") != "darwin":
            raise RuntimeError("native entity oracle reader supports the pinned macOS NLE wheel only")
        path = Path(str(getattr(nethack_instance, "dlpath", ""))).resolve()
        if not path.is_file():
            raise RuntimeError("live NLE instance does not expose its copied libnethack path")
        try:
            import nle
            from nle.nethack.nethack import DLPATH
        except ImportError as error:  # pragma: no cover - live runtime guard
            raise RuntimeError("pinned NLE runtime identity is unavailable") from error
        if getattr(nle, "__version__", None) != "0.9.0":
            raise RuntimeError(f"native entity reader requires NLE 0.9.0, saw {getattr(nle, '__version__', 'unknown')}")
        self._binary_sha256 = _sha256(path)
        if self._binary_sha256 != EXPECTED_BINARY_SHA256:
            raise RuntimeError("installed NLE binary hash is not the pinned v0.9.0 native entity oracle")
        if self._binary_sha256 != _sha256(Path(DLPATH).resolve()):
            raise RuntimeError("live copied libnethack does not match installed pinned oracle binary")
        _assert_layout()
        offsets = _symbol_offsets(path)
        library = ctypes.CDLL(str(path))
        anchors = {name: _address(ctypes.cast(getattr(library, name), ctypes.c_void_p).value) for name in ("movemon", "rn2")}
        slides = {anchors[name] - offsets[name] for name in anchors}
        if len(slides) != 1 or next(iter(slides)) <= 0:
            raise RuntimeError("NLE entity symbol slide is inconsistent")
        base = next(iter(slides))
        level_address = base + offsets["level"]
        objects_address = base + offsets["objects"]
        mons_address = base + offsets["mons"]
        _aligned_nonzero(level_address, what="level")
        _aligned_nonzero(objects_address, what="object-class table")
        _aligned_nonzero(mons_address, what="permonst table")
        self._library = library  # retain dlopen handle while raw views exist
        self._level = NativeLevel.from_address(level_address)
        self._objects = (NativeObjClass * MAX_OBJECT_TYPES).from_address(objects_address)
        self._mons = (NativePermonst * MAX_SPECIES).from_address(mons_address)
        self._mons_addresses = {
            ctypes.addressof(self._mons[index]): index for index in range(MAX_SPECIES)
        }
        self._moves = ctypes.c_long.from_address(base + offsets["moves"])
        self._monstermoves = ctypes.c_long.from_address(base + offsets["monstermoves"])

    def _object_display_contract(self, object_type: int) -> dict[str, int | str]:
        """Return the runtime shuffled mapglyph contract for one object.

        NLE's RL adapter applies ``objects[otyp].oc_descr_idx`` to the raw
        glyph, then ``mapglyph`` derives the visible class/color from that
        shuffled description entry.  The public ``nethack.objclass`` helper
        intentionally resets those indices to their compile-time values, so
        this read must come from the pinned live table and be exported only
        at reset.
        """

        if not 0 <= int(object_type) < MAX_OBJECT_TYPES:
            raise RuntimeError("source object type is outside the pinned object table")
        source = self._objects[int(object_type)]
        display_type = int(source.oc_descr_idx)
        if not 0 <= display_type < MAX_OBJECT_TYPES:
            raise RuntimeError("source object description index is outside the pinned object table")
        display = self._objects[display_type]
        # Corpses/statues have distinct mapglyph branches; leave those
        # explicitly unsupported instead of pretending the normal-object
        # description mapping covers them.
        mode = "normal"
        if int(object_type) in {CORPSE_OBJECT_TYPE, STATUE_OBJECT_TYPE}:
            mode = "unsupported_special_object"
        return {
            "display_mode": mode,
            "display_object_type": display_type,
            "display_glyph": GLYPH_OBJ_OFF + display_type,
            # ``mapglyph`` derives the terminal char/color from the original
            # object glyph; only the RL tile glyph is remapped through the
            # shuffled description index.
            "display_class": int(source.oc_class),
            "display_color": int(source.oc_color),
        }

    @staticmethod
    def _monster_flags(monster: NativeMonst) -> dict[str, bool | int]:
        # Exact source bit layout from include/monst.h: bits[0] holds
        # cancellation/vision, bits[1] speed/flee, bits[2..4] timeouts and
        # moveability, and bits[5] the state used by dochug()/dog_move().
        bits = monster._bits
        return {
            "speed_state": int(bits[1] & 0x03),
            "can_move": bool(bits[4] & 0x80),
            "sleeping": bool(bits[2] & 0x80),
            "fleeing": bool(bits[1] & 0x80),
            "peaceful": bool(bits[5] & 0x02),
            "cancelled": bool(bits[0] & 0x10),
            "can_see": bool(bits[0] & 0x80),
            "invisible": bool(bits[0] & 0x02),
            "undetected": bool(bits[0] & 0x40),
            "flee_timeout": int(bits[2] & 0x7F),
            "blind_timeout": int(bits[3] & 0x7F),
            "stunned": bool(bits[3] & 0x80),
            "frozen_timeout": int(bits[4] & 0x7F),
            "confused": bool(bits[5] & 0x01),
            "trapped": bool(bits[5] & 0x04),
            "leashed": bool(bits[5] & 0x08),
            "is_minion": bool(bits[5] & 0x20),
        }

    @staticmethod
    def _edog_path_state(monster: NativeMonst, flags: dict[str, bool | int]) -> dict[str, Any] | None:
        """Copy a tame non-minion's ABI-verified pet state, or hard-fail.

        ``dog_move`` explicitly documents the tame-minion exception: those
        entities have a different extension and must never be reinterpreted as
        ``struct edog``.  For every other tame monster, a missing/misaligned
        ``mextra`` or ``edog`` pointer is an unsafe ABI assumption, not an
        invitation to emit guessed zero values.
        """

        if int(monster.mtame) <= 0 or bool(flags["is_minion"]):
            return None
        mextra_address = _address(monster.mextra)
        _aligned_nonzero(mextra_address, what="tame monster mextra")
        mextra = NativeMextra.from_address(mextra_address)
        edog_address = _address(mextra.edog)
        _aligned_nonzero(edog_address, what="tame monster edog")
        edog = NativeEdog.from_address(edog_address)
        return {
            "droptime": int(edog.droptime),
            "dropdist": int(edog.dropdist),
            "apport": int(edog.apport),
            "whistletime": int(edog.whistletime),
            "hungrytime": int(edog.hungrytime),
            "ogoal_native": {"x": int(edog.ogoal.x), "y": int(edog.ogoal.y)},
            "abuse": int(edog.abuse),
            "revivals": int(edog.revivals),
            "mhpmax_penalty": int(edog.mhpmax_penalty),
            "killed_by_u": bool(edog._flags & 0x01),
        }

    def _floor_object_index(self) -> dict[tuple[int, int], list[dict[str, Any]]]:
        """Cross-check the complete floor list against every map stack."""

        global_nodes: dict[int, dict[str, Any]] = {}
        address = _address(self._level.objlist)
        for _ in range(MAX_OBJECTS):
            if not address:
                break
            _aligned_nonzero(address, what="floor object")
            if address in global_nodes:
                raise RuntimeError("cycle in source level.objlist")
            obj = NativeObj.from_address(address)
            if int(obj.where) != 1:  # OBJ_FLOOR, exact source enum
                raise RuntimeError("level.objlist contains non-floor object")
            if not (0 <= int(obj.ox) < COLNO and 0 <= int(obj.oy) < ROWNO and int(obj.o_id) > 0):
                raise RuntimeError("invalid floor object source coordinates or ID")
            record = self._object_record(obj)
            # dogmove.c::dog_goal iterates the global fobj chain, not the
            # x/y-sorted level.objects grid.  Preserve that source order as a
            # pointer-free reset fact so both gold lanes can replay the same
            # object_resists/dogfood chronology without reconstructing links.
            record["source_order"] = len(global_nodes)
            global_nodes[address] = record
            address = _address(obj.nobj)
        else:
            raise RuntimeError("level.objlist exceeded bounded traversal limit")

        stacked: dict[tuple[int, int], list[dict[str, int]]] = {}
        grid_nodes: set[int] = set()
        for x in range(COLNO):
            for y in range(ROWNO):
                address = _address(self._level.objects[x * ROWNO + y])
                records: list[dict[str, int]] = []
                local_seen: set[int] = set()
                for _ in range(MAX_OBJECTS):
                    if not address:
                        break
                    _aligned_nonzero(address, what="floor object stack")
                    if address in local_seen:
                        raise RuntimeError("cycle in source floor-object stack")
                    if address not in global_nodes:
                        raise RuntimeError("floor-object stack contains node absent from level.objlist")
                    obj = NativeObj.from_address(address)
                    if (int(obj.ox), int(obj.oy)) != (x, y):
                        raise RuntimeError("floor-object stack coordinate disagrees with source grid")
                    local_seen.add(address)
                    grid_nodes.add(address)
                    records.append(global_nodes[address])
                    address = _address(obj.nexthere)
                else:
                    raise RuntimeError("floor-object stack exceeded bounded traversal limit")
                if records:
                    stacked[(x, y)] = records
        if set(global_nodes) != grid_nodes:
            raise RuntimeError("level.objlist and level.objects stacks disagree; object underlay is not complete")
        return stacked

    def _object_record(self, obj: NativeObj) -> dict[str, Any]:
        record = _native_object_record(obj)
        record.update(self._object_display_contract(int(obj.otyp)))
        return record

    @staticmethod
    def _monster_inventory(monster: NativeMonst) -> list[dict[str, int]]:
        """Copy a monster's private inventory for reset-owned pet decisions."""

        records: list[dict[str, int]] = []
        address = _address(monster.minvent)
        seen: set[int] = set()
        for _ in range(MAX_OBJECTS):
            if not address:
                break
            _aligned_nonzero(address, what="monster inventory object")
            if address in seen:
                raise RuntimeError("cycle in monster inventory")
            seen.add(address)
            obj = NativeObj.from_address(address)
            if int(obj.where) != 4:  # OBJ_MINVENT, exact source enum
                raise RuntimeError("monster inventory contains non-inventory object")
            if int(obj.o_id) <= 0 or int(obj.quan) <= 0:
                raise RuntimeError("monster inventory object has invalid identity or quantity")
            records.append(_native_object_record(obj))
            address = _address(obj.nobj)
        else:
            raise RuntimeError("monster inventory exceeded bounded traversal limit")
        return records

    def snapshot(self) -> NativeEntitySnapshot:
        stacks = self._floor_object_index()
        listed: set[int] = set()
        entities: list[dict[str, Any]] = []
        address = _address(self._level.monlist)
        for order in range(MAX_MONSTERS):
            if not address:
                break
            _aligned_nonzero(address, what="monster")
            if address in listed:
                raise RuntimeError("cycle in source level.monlist")
            listed.add(address)
            monster = NativeMonst.from_address(address)
            # NetHack can leave an overkilled monster in ``monlist`` for the
            # remainder of the source boundary with a negative ``mhp``. It
            # is still an exact identity/list/underlay record, but it is not
            # an eligible live actor. Preserve that lifecycle state instead
            # of aborting the entire fuzz campaign or silently dropping it.
            if not (
                int(monster.m_id) > 0
                and 0 <= int(monster.mnum) < 4096
                and int(monster.mhpmax) > 0
                and int(monster.mhp) <= int(monster.mhpmax)
            ):
                raise RuntimeError(
                    "invalid source monster identity/species/HP state: "
                    f"m_id={int(monster.m_id)} mnum={int(monster.mnum)} "
                    f"mhp={int(monster.mhp)} mhpmax={int(monster.mhpmax)}"
                )
            native_x, y = int(monster.mx), int(monster.my)
            # NLE presents COLNO-1 columns and omits NetHack level x=0.
            # Require current source entities to map to an exact public plane
            # coordinate instead of silently publishing a shifted location.
            if not (1 <= native_x < COLNO and 0 <= y < ROWNO):
                raise RuntimeError("off-map monster in current source level list")
            if _address(self._level.monsters[native_x * ROWNO + y]) != address:
                raise RuntimeError("source monster position disagrees with level.monsters grid")
            data_address = _address(monster.data)
            _aligned_nonzero(data_address, what="monster species")
            species = NativePermonst.from_address(data_address)
            # ``data`` is normally an address into the pinned ``mons`` table;
            # permit only that exact static table identity for reset evidence.
            # A polymorphed/shape-shifted runtime pointer is a distinct source
            # branch and must not be silently flattened into the mnum index.
            species_table_id = self._mons_addresses.get(data_address)
            if species_table_id is None:
                raise RuntimeError("source monster species pointer is not a unique pinned mons entry")
            if species_table_id != int(monster.mnum):
                raise RuntimeError("source monster mnum disagrees with its pinned mons-table species pointer")
            flags = self._monster_flags(monster)
            allegiance = "tame" if int(monster.mtame) > 0 else "peaceful" if bool(flags["peaceful"]) else "hostile"
            terrain = self._level.locations[native_x][y]
            # These are raw source coordinates, deliberately not converted
            # into a public/player target.  ``mux/muy`` and ``mtrack`` are
            # internal decision inputs; exposing their native values lets a
            # probe establish completeness without treating them as a gold
            # pathing contract.
            path_state = {
                "apparent_hero_native": {"x": int(monster.mux), "y": int(monster.muy)},
                "mtrack_native": [
                    {"x": int(track.x), "y": int(track.y)}
                    for track in monster.mtrack
                ],
                "strategy": int(monster.mstrategy),
                "trap_seen_mask": int(monster.mtrapseen),
                "last_monster_move": int(monster.mlstmv),
                "status": {
                    "cancelled": bool(flags["cancelled"]),
                    "can_see": bool(flags["can_see"]),
                    "invisible": bool(flags["invisible"]),
                    "undetected": bool(flags["undetected"]),
                    "flee_timeout": int(flags["flee_timeout"]),
                    "blind_timeout": int(flags["blind_timeout"]),
                    "stunned": bool(flags["stunned"]),
                    "frozen_timeout": int(flags["frozen_timeout"]),
                    "confused": bool(flags["confused"]),
                    "trapped": bool(flags["trapped"]),
                    "leashed": bool(flags["leashed"]),
                    "is_minion": bool(flags["is_minion"]),
                    "eating_timeout": int(monster.meating),
                },
                "edog": self._edog_path_state(monster, flags),
            }
            entities.append(
                {
                    "entity_id": int(monster.m_id),
                    "species_id": int(monster.mnum),
                    "species_rules": _monster_species_rules(species, species_table_id),
                    "allegiance": allegiance,
                    "presentation": _monster_presentation(
                        species,
                        int(monster.mnum),
                        tame=int(monster.mtame) > 0,
                    ),
                    "x": native_x - 1,
                    "y": y,
                    "native_x": native_x,
                    "hp": int(monster.mhp),
                    "hp_max": int(monster.mhpmax),
                    "lifecycle": "dead_pending_cleanup" if int(monster.mhp) <= 0 else "alive",
                    "underlay": {
                        "terrain_type": int(terrain.typ),
                        "terrain_memory_glyph": int(terrain.glyph),
                        "object_stack": stacks.get((native_x, y), []),
                        "object_stack_complete": True,
                    },
                    "inventory": self._monster_inventory(monster),
                    "path_state": path_state,
                    "scheduler": {
                        "iteration_order": order,
                        "base_speed": int(species.mmove),
                        "movement_points": int(monster.movement),
                        "speed_state": int(flags["speed_state"]),
                        "can_move": bool(flags["can_move"]),
                        "sleeping": bool(flags["sleeping"]),
                        "fleeing": bool(flags["fleeing"]),
                        "strategy": int(monster.mstrategy),
                        "special_cooldown": int(monster.mspec_used),
                    },
                }
            )
            address = _address(monster.nmon)
        else:
            raise RuntimeError("source level.monlist exceeded bounded traversal limit")
        if len({entity["entity_id"] for entity in entities}) != len(entities):
            raise RuntimeError("source level.monlist contains duplicate stable monster IDs")
        grid_monsters = {_address(pointer) for pointer in self._level.monsters if _address(pointer)}
        if grid_monsters != listed:
            raise RuntimeError("level.monlist and level.monsters grid disagree")
        object_stacks = tuple(
            {"x": int(x), "y": int(y), "objects": list(objects)}
            for (native_x, y), objects in stacks.items()
            for x in (native_x - 1,)
        )
        return NativeEntitySnapshot(
            binary_sha256=self._binary_sha256,
            moves=int(self._moves.value),
            monstermoves=int(self._monstermoves.value),
            entities=tuple(entities),
            object_stacks=object_stacks,
        )

    def source_cell(self, x: int, y: int) -> dict[str, Any]:
        """Export one exact NLE-plane underlay cell after ABI validation."""

        if not (0 <= int(x) < COLNO - 1 and 0 <= int(y) < ROWNO):
            raise ValueError("NLE plane coordinate outside 21x79 map")
        for cell in self.source_cells():
            if cell["x"] == int(x) and cell["y"] == int(y):
                return cell
        raise RuntimeError("source-cell grid omitted an in-bounds coordinate")

    def source_cells(self) -> tuple[dict[str, Any], ...]:
        """Freeze the complete current source map surface in NLE coordinates.

        Scheduler probes call this *before* forwarding an input and again at
        the immediate post-input boundary.  Capturing the full grid means a
        later observed destination is looked up in an already committed
        pre-action source frame, rather than causing a coordinate-specific
        native read.  The result is oracle evidence only; it is never a gold
        engine input or a source of map hydration.
        """

        stacks = self._floor_object_index()
        cells: list[dict[str, Any]] = []
        claimed_monsters: set[int] = set()
        for public_x in range(COLNO - 1):
            native_x = public_x + 1
            for y in range(ROWNO):
                terrain = self._level.locations[native_x][y]
                monster_address = _address(self._level.monsters[native_x * ROWNO + y])
                if monster_address:
                    _aligned_nonzero(monster_address, what="source cell monster")
                    monster_id: int | None = int(NativeMonst.from_address(monster_address).m_id)
                    if monster_id <= 0 or monster_id in claimed_monsters:
                        raise RuntimeError("source-cell monster occupancy is invalid or duplicated")
                    claimed_monsters.add(monster_id)
                else:
                    monster_id = None
                cells.append(
                    {
                        "x": public_x,
                        "y": y,
                        "native_x": native_x,
                        "terrain_type": int(terrain.typ),
                        "terrain_memory_glyph": int(terrain.glyph),
                        "object_stack": stacks.get((native_x, y), []),
                        "object_stack_complete": True,
                        "monster_id": monster_id,
                    }
                )
        expected = (COLNO - 1) * ROWNO
        if len(cells) != expected:
            raise RuntimeError("source-cell grid has an incomplete NLE-plane surface")
        return tuple(cells)

def validate_native_presentation(snapshot: NativeEntitySnapshot, observation: dict[str, Any], nethack: Any) -> dict[str, int]:
    """Cross-check source identity/species/tameness against public mapglyphs.

    This is an ABI tripwire, not the exporter authority itself.  A rendered
    monster may be a mimic or be hidden, so the check is one-way: every public
    pet glyph/``MG_PET`` bit must name an on-level native tame entity at the
    same coordinate and with the same source species.  It never assigns a
    native identity based on a glyph.
    """

    glyphs = observation.get("glyphs")
    specials = observation.get("specials")
    if getattr(glyphs, "shape", None) != (ROWNO, COLNO - 1) or getattr(specials, "shape", None) != (ROWNO, COLNO - 1):
        raise ValueError("expected exact NLE glyphs/specials public plane shapes")
    # The native exporter already converts NetHack's level x to the exact
    # public NLE plane coordinate and preserves the original as ``native_x``.
    entities = {(int(entity["x"]), int(entity["y"])): entity for entity in snapshot.entities}
    verified_pets = 0
    for y in range(ROWNO):
        for x in range(COLNO - 1):
            glyph = int(glyphs[y, x])
            special = int(specials[y, x])
            pet_surface = bool(nethack.glyph_is_pet(glyph) or special & int(nethack.MG_PET))
            if not pet_surface:
                continue
            entity = entities.get((x, y))
            if entity is None or entity.get("allegiance") != "tame":
                raise RuntimeError("public pet surface has no matching native tame source entity")
            if int(nethack.glyph_to_mon(glyph)) != int(entity["species_id"]):
                raise RuntimeError("public pet glyph species disagrees with native source entity")
            verified_pets += 1
    return {"verified_public_pet_cells": verified_pets, "native_entities": len(snapshot.entities)}


def validate_native_entity_record(record: dict[str, Any]) -> list[str]:
    """Validate an exported entity sidecar before it is accepted as evidence.

    ``validate_native_presentation`` is deliberately a live one-way ABI
    cross-check.  A persisted pre-action sidecar needs a separate structural
    check: otherwise a caller who recomputes the outer digests could replace
    an entity list, its scheduler order, or an occupied-cell underlay with a
    malformed value and still pass the map/player/RNG validators.  This
    routine validates only data copied by :class:`PinnedNleEntityReader`; it
    does not infer a target, collision result, path, or actor schedule.

    The path-state extension remains backwards-compatible for old v1 records
    (``validate_native_path_state`` marks those as assertion-ineligible), but
    stable identity, queue order, scheduler fields, and complete underlays are
    mandatory for every non-legacy entity export.
    """

    failures: list[str] = []
    if not isinstance(record, dict) or record.get("schema") != "gamebench.nethack.native_entity_snapshot.v1":
        return ["native entity export schema mismatch"]

    source_turn = record.get("source_turn")
    if (
        not isinstance(source_turn, dict)
        or set(source_turn) != {"moves", "monstermoves"}
        or any(type(source_turn.get(name)) is not int or int(source_turn[name]) < 0 for name in ("moves", "monstermoves"))
    ):
        failures.append("native entity export has invalid source turn counters")

    entities = record.get("entities")
    turn_queue = record.get("turn_queue")
    if not isinstance(entities, list) or not isinstance(turn_queue, list):
        failures.append("native entity export requires explicit entities and turn_queue lists")
        return failures

    # Reuse the stricter ABI-backed path-state validator for identity,
    # coordinate conversion and source list order.  Its no-entity outcome is
    # structurally valid but intentionally provides no positive path evidence.
    from scripts.native_path_state_contract import validate_native_path_state

    path_contract = validate_native_path_state(record)
    if path_contract.get("status") != "pass":
        for issue in path_contract.get("issues", []):
            code = issue.get("code") if isinstance(issue, dict) else "unknown"
            failures.append(f"native path-state {code}")

    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            # The path-state validator already records the malformed entry;
            # avoid attempting unchecked nested access here.
            continue
        if type(entity.get("species_id")) is not int or not 0 <= int(entity["species_id"]) < 4096:
            failures.append(f"native entity {index} has invalid source species ID")
        species_rules = entity.get("species_rules")
        if species_rules is not None:
            legacy_rules = {
                "species_id", "name", "monster_class", "base_speed", "mflags1",
                "mflags2", "mflags3", "capabilities", "branch_profile", "provenance",
            }
            profile_rules = legacy_rules | {"combat"}
            profile_v2_rules = profile_rules | {
                "geno", "generation_frequency", "corpse_weight", "corpse_nutrition", "no_corpse",
            }
            # Sets are unhashable; use a tuple for the accepted key sets.
            # Legacy reset receipts remain structurally valid, while the new
            # profile form is required for any combat promotion.
            if not isinstance(species_rules, dict) or set(species_rules) not in (
                legacy_rules, profile_rules, profile_v2_rules,
            ):
                failures.append(f"native entity {index} has incomplete static species rules")
            else:
                capabilities = species_rules.get("capabilities")
                combat = species_rules.get("combat")
                profile_v1 = set(species_rules) == profile_rules
                profile_v2 = set(species_rules) == profile_v2_rules
                profile_combat = profile_v1 or profile_v2
                legacy_capabilities = {
                    "swim", "amorphous", "wallwalk", "tunnel", "conceal_underlay",
                    "hide", "cannot_pickup", "no_eyes", "no_hands", "teleport",
                    "domestic", "wander", "stalk", "likes_gold", "likes_gems",
                    "collects_objects", "likes_magic", "covetous",
                }
                size_capabilities = legacy_capabilities | {"very_small"}
                if (
                    type(species_rules.get("species_id")) is not int
                    or species_rules["species_id"] != entity.get("species_id")
                    or not isinstance(species_rules.get("name"), str)
                    or not species_rules["name"]
                    or type(species_rules.get("monster_class")) is not int
                    or not 1 <= species_rules["monster_class"] <= 60
                    or type(species_rules.get("base_speed")) is not int
                    or not 0 <= species_rules["base_speed"] <= 255
                    or any(type(species_rules.get(name)) is not int or species_rules[name] < 0 for name in ("mflags1", "mflags2", "mflags3"))
                    or not isinstance(capabilities, dict)
                    or set(capabilities) not in (legacy_capabilities, size_capabilities)
                    or any(type(value) is not bool for value in capabilities.values())
                    or species_rules.get("branch_profile") not in {
                        "dog_move_domestic", "covetous_special", "species_teleport_capability",
                        "terrain_or_underlay_special", "swimming_m_move_candidate", "object_interest_special",
                        "target_or_wander_special", "ordinary_m_move_candidate",
                    }
                    or species_rules.get("provenance")
                    not in {
                        "nle_reset_permonst_static_flags",
                        "nle_reset_permonst_static_profile_v1",
                        "nle_reset_permonst_static_profile_v2",
                    }
                    or (profile_v1 and species_rules.get("provenance") != "nle_reset_permonst_static_profile_v1")
                    or (profile_v2 and species_rules.get("provenance") != "nle_reset_permonst_static_profile_v2")
                    or (not profile_combat and species_rules.get("provenance") != "nle_reset_permonst_static_flags")
                    or (profile_combat and not isinstance(combat, dict))
                    or (profile_combat and set(combat) != {
                        "armor_class", "level", "magic_resistance", "resistances",
                        "attacks", "attack_bytes_hex", "provenance",
                    })
                    or (profile_combat and any(
                        type(combat.get(name)) is not int
                        or not -128 <= int(combat[name]) <= 127
                        for name in ("armor_class", "level", "magic_resistance")
                    ))
                    or (profile_combat and (type(combat.get("resistances")) is not int
                        or not 0 <= int(combat.get("resistances", -1)) <= 255))
                    or (profile_combat and not isinstance(combat.get("attacks"), list))
                    or (profile_combat and len(combat.get("attacks", [])) != NATTK)
                    or (profile_combat and combat.get("provenance") != "nle_reset_permonst_attack_profile_v1")
                    or (profile_combat and not isinstance(combat.get("attack_bytes_hex"), str))
                    or (profile_combat and len(combat.get("attack_bytes_hex", "")) != NATTK * ATTACK_STRUCT_SIZE * 2)
                    or (profile_combat and any(character not in "0123456789abcdef" for character in combat.get("attack_bytes_hex", "")))
                    or (profile_v2 and type(species_rules.get("geno")) is not int
                        or profile_v2 and not 0 <= species_rules.get("geno", -1) <= 0xFFFF)
                    or (profile_v2 and type(species_rules.get("generation_frequency")) is not int
                        or profile_v2 and not 0 <= species_rules.get("generation_frequency", -1) <= G_FREQ_MASK)
                    or (profile_v2 and species_rules.get("generation_frequency") != (species_rules.get("geno", 0) & G_FREQ_MASK))
                    or (profile_v2 and type(species_rules.get("corpse_weight")) is not int
                        or profile_v2 and not 0 <= species_rules.get("corpse_weight", -1) <= 0xFFFF)
                    or (profile_v2 and type(species_rules.get("corpse_nutrition")) is not int
                        or profile_v2 and not 0 <= species_rules.get("corpse_nutrition", -1) <= 0xFFFF)
                    or (profile_v2 and type(species_rules.get("no_corpse")) is not bool)
                    or (profile_v2 and species_rules.get("no_corpse") != bool(species_rules.get("geno", 0) & G_NOCORPSE))
                ):
                    failures.append(f"native entity {index} has invalid static species rules")
                elif profile_combat and any(
                    not isinstance(attack, dict)
                    or set(attack) != {"slot", "aatyp", "adtyp", "damn", "damd"}
                    or attack.get("slot") != attack_index
                    or any(type(attack.get(name)) is not int or not 0 <= int(attack[name]) <= 255 for name in ("aatyp", "adtyp", "damn", "damd"))
                    for attack_index, attack in enumerate(combat["attacks"])
                ):
                    failures.append(f"native entity {index} has invalid static attack matrix")
                elif profile_combat and bytes.fromhex(combat["attack_bytes_hex"]) != bytes(
                    value
                    for attack in combat["attacks"]
                    for value in (attack["aatyp"], attack["adtyp"], attack["damn"], attack["damd"])
                ):
                    failures.append(f"native entity {index} attack bytes disagree with attack matrix")
        if entity.get("allegiance") not in {"tame", "peaceful", "hostile"}:
            failures.append(f"native entity {index} has invalid source allegiance")
        presentation = entity.get("presentation")
        if presentation is not None:
            # This is the optional source ``mapglyph.c`` identity join.  It is
            # deliberately strict when present: a partial or glyph-derived
            # replacement must never be accepted as native actor evidence.
            expected_presentation = {"char", "glyph", "color", "monster_class", "provenance"}
            if not isinstance(presentation, dict) or set(presentation) != expected_presentation:
                failures.append(f"native entity {index} has incomplete presentation contract")
            else:
                char = presentation.get("char")
                glyph = presentation.get("glyph")
                color = presentation.get("color")
                monster_class = presentation.get("monster_class")
                species_id = entity.get("species_id")
                expected_glyph = (
                    381 + int(species_id)
                    if entity.get("allegiance") == "tame" and type(species_id) is int
                    else species_id
                )
                if (
                    not isinstance(char, str)
                    or len(char) != 1
                    or type(glyph) is not int
                    or type(expected_glyph) is not int
                    or int(glyph) != int(expected_glyph)
                    or type(color) is not int
                    or not 0 <= int(color) <= 15
                    or type(monster_class) is not int
                    or not 1 <= int(monster_class) <= 60
                    or MONSTER_CLASS_CHARS.get(int(monster_class)) != char
                    or presentation.get("provenance") != "nle_reset_monster_class_symbol"
                ):
                    failures.append(f"native entity {index} has invalid presentation identity")
        hp, hp_max = entity.get("hp"), entity.get("hp_max")
        if type(hp) is not int or type(hp_max) is not int or int(hp_max) <= 0 or int(hp) > int(hp_max):
            failures.append(f"native entity {index} has invalid source HP state")
        lifecycle = entity.get("lifecycle", "alive")
        if lifecycle not in {"alive", "dead_pending_cleanup"}:
            failures.append(f"native entity {index} has invalid lifecycle state")
        elif (lifecycle == "alive") != (type(hp) is int and int(hp) > 0):
            failures.append(f"native entity {index} lifecycle disagrees with source HP state")

        scheduler = entity.get("scheduler")
        scheduler_ints = ("iteration_order", "base_speed", "movement_points", "speed_state", "strategy", "special_cooldown")
        scheduler_bools = ("can_move", "sleeping", "fleeing")
        if not isinstance(scheduler, dict) or any(type(scheduler.get(name)) is not int for name in scheduler_ints) or any(
            type(scheduler.get(name)) is not bool for name in scheduler_bools
        ):
            failures.append(f"native entity {index} has incomplete scheduler state")

        underlay = entity.get("underlay")
        if not isinstance(underlay, dict):
            failures.append(f"native entity {index} lacks a source underlay")
            continue
        if type(underlay.get("terrain_type")) is not int or type(underlay.get("terrain_memory_glyph")) is not int:
            failures.append(f"native entity {index} has invalid source terrain underlay")
        if underlay.get("object_stack_complete") is not True or not isinstance(underlay.get("object_stack"), list):
            failures.append(f"native entity {index} lacks a complete source object stack")
            continue
        object_ids: set[int] = set()
        for object_index, source_object in enumerate(underlay["object_stack"]):
            if not isinstance(source_object, dict):
                failures.append(f"native entity {index} object stack entry {object_index} is malformed")
                continue
            object_id = source_object.get("object_id")
            if (
                type(object_id) is not int
                or int(object_id) <= 0
                or object_id in object_ids
                or type(source_object.get("object_type")) is not int
                or type(source_object.get("quantity")) is not int
                or int(source_object["quantity"]) <= 0
            ):
                failures.append(f"native entity {index} object stack entry {object_index} is invalid")
                continue
            object_ids.add(object_id)
            display_fields = ("display_mode", "display_object_type", "display_glyph", "display_class", "display_color")
            if any(field in source_object for field in display_fields):
                if set(display_fields) - set(source_object):
                    failures.append(f"native entity {index} object stack entry {object_index} has partial display contract")
                elif (
                    source_object.get("display_mode") not in {"normal", "unsupported_special_object"}
                    or type(source_object.get("display_object_type")) is not int
                    or not 0 <= int(source_object["display_object_type"]) < MAX_OBJECT_TYPES
                    or type(source_object.get("display_glyph")) is not int
                    or int(source_object["display_glyph"]) != GLYPH_OBJ_OFF + int(source_object["display_object_type"])
                    or type(source_object.get("display_class")) is not int
                    or type(source_object.get("display_color")) is not int
                    or not 0 <= int(source_object["display_color"]) <= 15
                ):
                    failures.append(f"native entity {index} object stack entry {object_index} has invalid display contract")
        if "inventory" in entity:
            inventory = entity.get("inventory")
            if not isinstance(inventory, list):
                failures.append(f"native entity {index} inventory is malformed")
            else:
                for object_index, source_object in enumerate(inventory):
                    if (
                        not isinstance(source_object, dict)
                        or type(source_object.get("object_id")) is not int
                        or int(source_object.get("object_id", 0)) <= 0
                        or type(source_object.get("object_type")) is not int
                        or type(source_object.get("quantity")) is not int
                        or int(source_object.get("quantity", 0)) <= 0
                    ):
                        failures.append(f"native entity {index} inventory entry {object_index} is invalid")

    return failures
