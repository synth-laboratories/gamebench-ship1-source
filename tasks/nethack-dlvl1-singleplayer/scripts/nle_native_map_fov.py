"""Verified read-only full terrain, FOV, and map-memory export from NLE 0.9.0.

The pinned macOS NLE wheel keeps local Mach-O symbols for NetHack's current
``level`` and ``viz_array`` globals.  This module resolves them relative to
the exported ``rn2`` function in the *live copied* libnethack instance.  It
never calls into game code or writes native memory.  Every read is rejected
unless the copied library has the exact pinned SHA-256, the Mach-O slide is
consistent, and the v0.9.0 C ABI/layout agrees with independent rendered-map
controls.

This is source-oracle instrumentation, not a gold-engine dependency.  It is
the first native authority for the map/FOV frontier: ``level.locations`` holds
real terrain and remembered glyphs; ``viz_array`` holds ``COULD_SEE`` /
``IN_SIGHT`` bits.  Dynamic objects and monsters remain outside this reader.
"""

from __future__ import annotations

import ctypes
import functools
import hashlib
import json
import os
import platform
import re
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.nle_native_entities import MAX_MONSTERS, MAX_OBJECTS, NativeMonst, NativeObj


PINNED_BINARY_SHA256 = "7ac1270dfd5fa0a5fb2f715ef6a7151058f06cda595e4b722ac6d070ce0f2057"
PINNED_SOURCE_COMMIT = "2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa"
COLNO = 80
ROWNO = 21
OBS_COLNO = COLNO - 1
RM_SIZE = 8
RM_GLYPH_OFFSET = 0
RM_TYP_OFFSET = 4
RM_SEENV_OFFSET = 5
RM_BITFIELDS_OFFSET = 6
RM_FLAGS_MASK = 0x1F
RM_HORIZONTAL_MASK = 0x20
RM_LIT_MASK = 0x40
RM_WASLIT_MASK = 0x80
# ``dlevel_t.flags`` is the final field in the pinned 40368-byte level
# object.  The independent header probe places the eight-byte
# ``struct levelflags`` at offset 40360: nfountains/nsinks occupy bytes 0/1,
# then the source bitfields occupy bytes 2/3.  This is read-only source state;
# it is exported so whole-turn ``dosounds`` gates can be accounted for rather
# than silently assuming an empty special-level surface.
DLEVEL_SIZE = 40368
LEVEL_FLAGS_OFFSET = 40360
LEVEL_FLAGS_SIZE = 8
DOOR_TERRAIN_TYPE = 22
D_NODOOR = 0
D_BROKEN = 1
D_ISOPEN = 2
D_CLOSED = 4
D_LOCKED = 8
D_TRAPPED = 16
IN_SIGHT = 0x2
COULD_SEE = 0x1
VALID_TERRAIN_TYPES = frozenset(range(36))
STATIC_TERRAIN_CHARS = frozenset(".#|-+<>_{}~")
# The pinned C compiler lays the first two ``unsigned`` bitfield storage bytes
# out as flags[0:5], horizontal[5], lit[6], waslit[7].  The probe below uses
# the exact rm.h declaration, compiled by the host's clang; these constants
# are the expected result, not an unchecked endian assumption.
EXPECTED_RM_BITFIELD_ABI = (8, 0, 4, 5, 31, 0, 32, 0)


@functools.lru_cache(maxsize=1)
def _pinned_source_root() -> Path:
    """Resolve a complete checkout for compiler-proved source ABIs.

    Older capture runs left only a six-header ABI subset at the historical
    ``/tmp/nle-pinned-source.*`` path.  That subset is useful as a receipt but
    cannot compile the structs used by the vision/trap/engraving probes.  Use
    an explicit override first, then accept the complete pinned checkout used
    by the instrumented source build.  Never fall back to an arbitrary source
    tree: the commit identity is checked before the path is admitted.
    """

    candidates = []
    override = os.environ.get("NLE_PINNED_SOURCE_ROOT", "").strip()
    if override:
        candidates.append(Path(override).expanduser())
    candidates.extend((
        Path("/tmp/nle-pinned-source.FU3ur6"),
        Path("/tmp/nle-netherite-src"),
    ))
    for root in candidates:
        include = root / "include"
        if not all((include / name).is_file() for name in ("config.h", "global.h", "hack.h")):
            continue
        try:
            commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
        if commit == PINNED_SOURCE_COMMIT:
            return root
    raise RuntimeError(
        "complete pinned NetHack source checkout is unavailable; set "
        "NLE_PINNED_SOURCE_ROOT to the clean pinned commit"
    )
# This probe compiles the pinned headers (rather than using Python's idea of
# bitfields) and also pins every raw offset read by the vision extension.
# It includes the two bytes produced by setting ``u.uswallow`` and
# ``u.uinwater`` on a zeroed ``struct you``; they prove the masks below.
EXPECTED_VISION_INPUT_ABI = (
    2392, 88, 1728, 1732, 32, 36, 1788, 1792, 1904, 24, 16, 3, 0,
    72, 48, 144, 48, 52, 24, 0, 8, 10, 12, 14, 16, 392, 58, 80,
)
EXPECTED_LEVEL_FLAGS_ABI = (8, 40368, 40360, 0, 1)
EXPECTED_ENGRAVING_ABI = (40, 0, 8, 16, 17, 20, 24, 32)
LEVEL_FLAGS_KEYS = frozenset({
    "nfountains", "nsinks", "has_shop", "has_vault", "has_zoo", "has_court",
    "has_morgue", "has_beehive", "has_barracks", "has_temple", "has_swamp",
    "noteleport", "hardfloor", "nommap", "hero_memory", "shortsighted",
    "graveyard", "sokoban_rules", "is_maze_lev", "is_cavernous_lev", "arboreal",
    "wizard_bones", "corrmaze",
})
YOU_SIZE = 2392
YOU_UPROPS_OFFSET = 88
YOU_NV_RANGE_OFFSET = 1728
YOU_XRAY_RANGE_OFFSET = 1732
YOU_UTRAP_OFFSET = 32
YOU_UTRAPTYPE_OFFSET = 36
YOU_UCREAMED_OFFSET = 1788
YOU_USWLDTIM_OFFSET = 1792
YOU_FLAGS_OFFSET = 1796
YOU_USWALLOW_MASK = 0x01
YOU_UINWATER_MASK = 0x02
YOU_ROLEPLAY_OFFSET = 1904
PROP_SIZE = 24
PROP_INTRINSIC_OFFSET = 16
BLINDED_PROP = 15
SEE_INVIS_PROP = 29
INFRAVISION_PROP = 36
TT_PIT = 1
M1_NOEYES = 0x00001000
PERMONST_MFLAGS1_OFFSET = 48
M_AP_NOTHING = 0
M_AP_FURNITURE = 1
M_AP_OBJECT = 2
M_AP_TYPMASK = 0x07
S_NDOOR = 12
S_VCDOOR = 15
S_HCDOOR = 16
S_TREE = 18
LS_OBJECT = 0
LS_MONSTER = 1
MAX_OBJECT_TYPES = 453
MAX_ARTIFACTS = 36
DUNGEON_TOPOLOGY_ROGUE_OFFSET = 4
DUNGEON_TOPOLOGY_WATER_OFFSET = 32
INSTANCE_FLAGS_VISION_INITED_OFFSET = 58
MAX_VISION_LIGHT_SOURCES = 8192
MAX_ENGRAVINGS = 8192
MAX_ENGRAVING_TEXT = 256
MAX_TRAPS = 4096
TRAP_SIZE = 24
TRAP_BITFIELDS_OFFSET = 14
TRAP_UNION_OFFSET = 16
TRAP_TYPES_MAX = 22
EXPECTED_TRAP_ABI = (24, 0, 8, 9, 10, 12, 14, 16)

VISION_EXTENSION_FIELDS = (
    "lighting",
    "vision_decision_inputs",
    "dynamic_vision_blockers",
    "vision_recalc_state",
    "semantic_vision_contract",
)


def _rows_are(value: Any, *, item_type: type) -> bool:
    return (
        isinstance(value, list)
        and len(value) == ROWNO
        and all(isinstance(row, list) and len(row) == OBS_COLNO and all(type(cell) is item_type for cell in row) for row in value)
    )


def validate_semantic_terrain_export(export: dict[str, Any]) -> list[str]:
    """Validate optional v1 terrain-state extension without rejecting history.

    The map/FOV snapshot schema deliberately remains v1 so existing sidecars
    remain replayable.  A historical export simply lacks both optional planes;
    a new export must carry both full planes, or it is malformed.  This is a
    source-record validation helper, never a gold input validator.
    """

    has_flags = "full_map_terrain_flags" in export
    has_horizontal = "full_map_terrain_horizontal" in export
    if not has_flags and not has_horizontal:
        return []
    errors: list[str] = []
    if not has_flags or not has_horizontal:
        return ["semantic terrain extension must include both flags and horizontal planes"]
    flags = export.get("full_map_terrain_flags")
    horizontal = export.get("full_map_terrain_horizontal")
    if not _rows_are(flags, item_type=int) or any(not 0 <= int(value) <= RM_FLAGS_MASK for row in flags for value in row):
        errors.append("semantic terrain flags must be a 21x79 plane of five-bit integers")
    if not _rows_are(horizontal, item_type=bool):
        errors.append("semantic terrain horizontal must be a 21x79 boolean plane")
    contract = export.get("semantic_terrain_contract")
    if not isinstance(contract, dict) or contract.get("source_only") is not True or contract.get("gold_implementation_eligible") is not False:
        errors.append("semantic terrain extension lacks explicit source-only eligibility contract")
    planes = export.get("plane_sha256")
    if not isinstance(planes, dict):
        errors.append("semantic terrain extension lacks plane digests")
    elif _rows_are(flags, item_type=int) and _rows_are(horizontal, item_type=bool):
        canonical = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if planes.get("full_map_terrain_flags") != canonical(flags):
            errors.append("semantic terrain flags plane digest mismatch")
        if planes.get("full_map_terrain_horizontal") != canonical(horizontal):
            errors.append("semantic terrain horizontal plane digest mismatch")
    return errors


def validate_level_flags_export(export: dict[str, Any]) -> list[str]:
    """Validate the optional reset ``dlevel_t.flags`` source extension.

    This check is deliberately independent of the enclosing tape digest.  A
    caller that rewrites a sidecar hash must not be able to turn an incomplete
    or ABI-incompatible ``dosounds`` input into an apparently valid scheduler
    receipt.  Historical map exports without the extension remain valid.
    """

    has_flags = "level_flags" in export
    has_contract = "semantic_level_flags" in export
    if not has_flags and not has_contract:
        return []
    if has_flags != has_contract:
        return ["level-flags extension must include both level_flags and semantic_level_flags"]
    flags = export.get("level_flags")
    contract = export.get("semantic_level_flags")
    errors: list[str] = []
    if not isinstance(flags, dict) or set(flags) != LEVEL_FLAGS_KEYS:
        errors.append("level_flags field set is incomplete or contains unknown fields")
    elif (
        type(flags.get("nfountains")) is not int
        or not 0 <= flags["nfountains"] <= 255
        or type(flags.get("nsinks")) is not int
        or not 0 <= flags["nsinks"] <= 255
        or any(type(flags.get(name)) is not bool for name in LEVEL_FLAGS_KEYS - {"nfountains", "nsinks"})
    ):
        errors.append("level_flags counters or bitfields are malformed")
    if not isinstance(contract, dict) or contract.get("source_only") is not True or contract.get("gold_implementation_eligible") is not False:
        errors.append("level_flags lacks explicit source-only eligibility contract")
    elif (
        not isinstance(contract.get("abi"), dict)
        or set(contract["abi"]) != {"sizeof_levelflags", "sizeof_dlevel_t", "flags_offset", "nfountains_offset", "nsinks_offset"}
        or tuple(contract["abi"].get(name) for name in ("sizeof_levelflags", "sizeof_dlevel_t", "flags_offset", "nfountains_offset", "nsinks_offset")) != EXPECTED_LEVEL_FLAGS_ABI
    ):
        errors.append("level_flags ABI contract does not match the pinned source layout")
    return errors


def validate_engraving_export(export: dict[str, Any]) -> list[str]:
    """Validate the reset-only ``head_engr`` source extension.

    Engravings are not terrain glyphs: ``wipe_engr_at`` reads a private linked
    list before monster movement.  The extension therefore carries only
    reset-bound coordinates, type, text, and the compiler-proved struct ABI;
    it is never inferred from a rendered character.
    """

    if "engravings" not in export and "semantic_engraving_contract" not in export:
        return []
    if "engravings" not in export or "semantic_engraving_contract" not in export:
        return ["engraving extension must include both engravings and semantic_engraving_contract"]
    contract = export.get("semantic_engraving_contract")
    if (
        not isinstance(contract, dict)
        or contract.get("source_only") is not True
        or contract.get("gold_implementation_eligible") is not False
        or contract.get("source") != "engrave.c::head_engr/struct engr; monmove.c::wipe_engr_at"
        or tuple(contract.get("abi", {}).get(name) for name in ("sizeof", "next", "text", "x", "y", "length", "time", "type")) != EXPECTED_ENGRAVING_ABI
    ):
        return ["engraving extension lacks the pinned source-only ABI contract"]
    records = export.get("engravings")
    if not isinstance(records, list) or len(records) > MAX_ENGRAVINGS:
        return ["engravings must be a bounded list"]
    seen: set[tuple[int, int]] = set()
    errors: list[str] = []
    for record in records:
        if not isinstance(record, dict) or set(record) != {"native_x", "y", "engr_type", "engr_time", "engr_lth", "text"}:
            errors.append("engraving record has an incomplete field set")
            continue
        x, y, kind = record["native_x"], record["y"], record["engr_type"]
        if type(x) is not int or not 1 <= x < COLNO or type(y) is not int or not 0 <= y < ROWNO or type(kind) is not int or not 1 <= kind <= 6:
            errors.append("engraving coordinate or type is outside the pinned source range")
        if (x, y) in seen:
            errors.append("engraving coordinates are not unique")
        seen.add((x, y))
        if type(record["engr_time"]) is not int or type(record["engr_lth"]) is not int or not 1 <= record["engr_lth"] <= MAX_ENGRAVING_TEXT:
            errors.append("engraving time/length is malformed")
        text = record["text"]
        if not isinstance(text, str) or len(text.encode("utf-8")) + 1 != record["engr_lth"]:
            errors.append("engraving text does not match its source length")
    return errors


def validate_search_surface_export(export: dict[str, Any]) -> list[str]:
    """Validate the reset-only trap input required by ``dosearch0`` replay."""

    if "traps" not in export and "semantic_search_contract" not in export:
        return []
    if "traps" not in export or "semantic_search_contract" not in export:
        return ["search-surface extension must include both traps and semantic_search_contract"]
    contract = export.get("semantic_search_contract")
    if (
        not isinstance(contract, dict)
        or contract.get("source_only") is not True
        or contract.get("gold_implementation_eligible") is not False
        or contract.get("source") != "detect.c::dosearch0; trap.h::struct trap/ftrap"
        or tuple(contract.get("abi", {}).get(name) for name in ("sizeof", "ntrap", "tx", "ty", "dst", "launch", "bitfields", "union")) != EXPECTED_TRAP_ABI
    ):
        return ["search-surface extension lacks the pinned source-only ABI contract"]
    records = export.get("traps")
    if not isinstance(records, list) or len(records) > MAX_TRAPS:
        return ["traps must be a bounded list"]
    seen: set[tuple[int, int]] = set()
    errors: list[str] = []
    for record in records:
        required = {"native_x", "x", "y", "trap_type", "tseen", "once", "madeby_u"}
        if not isinstance(record, dict) or set(record) != required:
            errors.append("trap record has an incomplete field set")
            continue
        native_x, x, y, trap_type = (record[name] for name in ("native_x", "x", "y", "trap_type"))
        if (
            type(native_x) is not int or not 1 <= native_x < COLNO
            or type(x) is not int or x != native_x - 1
            or type(y) is not int or not 0 <= y < ROWNO
            or type(trap_type) is not int or not 1 <= trap_type <= TRAP_TYPES_MAX
        ):
            errors.append("trap coordinate or type is outside the pinned source range")
        key = (native_x, y)
        if key in seen:
            errors.append("trap coordinates are not unique")
        seen.add(key)
        if any(type(record[name]) is not bool for name in ("tseen", "once", "madeby_u")):
            errors.append("trap flags are malformed")
    return errors


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _vision_bool_plane(value: Any) -> bool:
    return _rows_are(value, item_type=bool)


def validate_semantic_vision_export(export: dict[str, Any]) -> list[str]:
    """Validate the optional source-only vision decision-input extension.

    The extension deliberately remains attached to the v1 map snapshot.  Old
    recorded sidecars do not carry *any* of these fields and remain
    judgeable; a newly written record must carry every linked input and its
    independent plane digests.  This validates evidence after an attacker
    has recomputed outer sidecar hashes, so it cannot rely on those hashes.
    """

    present = tuple(key in export for key in VISION_EXTENSION_FIELDS)
    if not any(present):
        return []
    if not all(present):
        missing = [key for key in VISION_EXTENSION_FIELDS if key not in export]
        return [f"semantic vision extension is partial; missing {', '.join(missing)}"]

    errors: list[str] = []
    lighting = export.get("lighting")
    inputs = export.get("vision_decision_inputs")
    blockers = export.get("dynamic_vision_blockers")
    recalc = export.get("vision_recalc_state")
    contract = export.get("semantic_vision_contract")
    planes = export.get("plane_sha256")
    if not isinstance(lighting, dict):
        errors.append("semantic vision lighting payload missing")
    if not isinstance(inputs, dict):
        errors.append("semantic vision decision-input payload missing")
    if not isinstance(blockers, dict):
        errors.append("semantic vision blocker payload missing")
    if not isinstance(recalc, dict):
        errors.append("semantic vision recalc-state payload missing")
    if not isinstance(contract, dict) or contract.get("source_only") is not True or contract.get("gold_implementation_eligible") is not False:
        errors.append("semantic vision extension lacks explicit source-only eligibility contract")
    elif not isinstance(contract.get("completeness_matrix"), dict) or set(contract["completeness_matrix"]) != {
        "static_los_topology", "static_lighting", "mobile_lighting", "hero_branches",
        "dynamic_blockers", "recalc_state", "map_memory", "presentation",
    }:
        errors.append("semantic vision completeness matrix is missing or incomplete")
    if not isinstance(planes, dict):
        errors.append("semantic vision extension lacks plane digests")

    if isinstance(lighting, dict):
        for name in ("static_lit", "remembered_lit", "temporary_lit"):
            if not _vision_bool_plane(lighting.get(name)):
                errors.append(f"semantic vision lighting {name} must be a 21x79 boolean plane")
            elif isinstance(planes, dict) and planes.get(f"lighting_{name}") != _canonical_digest(lighting[name]):
                errors.append(f"semantic vision lighting {name} plane digest mismatch")
        sources = lighting.get("active_light_sources")
        if not isinstance(sources, list):
            errors.append("semantic vision active light-source list missing")
        else:
            seen: set[tuple[str, int]] = set()
            for source in sources:
                if not isinstance(source, dict):
                    errors.append("semantic vision light source malformed")
                    break
                kind, owner_id = source.get("owner_kind"), source.get("owner_id")
                if kind not in ("object", "monster", "hero") or type(owner_id) is not int or owner_id < 0:
                    errors.append("semantic vision light source owner malformed")
                    break
                if (kind, owner_id) in seen:
                    errors.append("semantic vision light-source owner is not unique")
                    break
                seen.add((kind, owner_id))
                if not all(type(source.get(name)) is int for name in ("native_x", "y", "range", "source_type")) or not (0 <= source["native_x"] < COLNO and 0 <= source["y"] < ROWNO and 1 <= source["range"] <= 15 and source["source_type"] in (LS_OBJECT, LS_MONSTER)):
                    errors.append("semantic vision light-source coordinates or range malformed")
                    break

    if isinstance(inputs, dict):
        hero = inputs.get("hero")
        level = inputs.get("level")
        blindness = inputs.get("blindness")
        senses = inputs.get("senses")
        if not isinstance(hero, dict) or not isinstance(level, dict) or not isinstance(blindness, dict) or not isinstance(senses, dict):
            errors.append("semantic vision input sections missing")
        else:
            required_hero = ("native_x", "native_y", "night_vision_range", "xray_range", "swallowed", "underwater", "pit_trapped")
            if not all(type(hero.get(name)) is int for name in ("native_x", "native_y", "night_vision_range", "xray_range")) or not all(type(hero.get(name)) is bool for name in ("swallowed", "underwater", "pit_trapped")) or not (1 <= hero.get("native_x", 0) < COLNO and 0 <= hero.get("native_y", -1) < ROWNO and -1 <= hero.get("night_vision_range", -2) <= 15 and -1 <= hero.get("xray_range", -2) <= 15) or any(name not in hero for name in required_hero):
                errors.append("semantic vision hero input malformed")
            if not all(type(level.get(name)) is bool for name in ("rogue_level", "water_level", "underwater_branch_active")) or level.get("underwater_branch_active") is not (hero.get("underwater") and not level.get("water_level")):
                errors.append("semantic vision level predicate mismatch")
            blind_fields = ("roleplay_blind", "blindfolded", "has_eyes", "eyes_of_overworld_override", "blind")
            if not all(type(blindness.get(name)) is bool for name in blind_fields) or type(blindness.get("blinded_intrinsic")) is not int:
                errors.append("semantic vision blindness input malformed")
            else:
                expected_blind = bool(blindness["roleplay_blind"] or blindness["blinded_intrinsic"] or blindness["blindfolded"] or not blindness["has_eyes"]) and not blindness["eyes_of_overworld_override"]
                if blindness["blind"] is not expected_blind:
                    errors.append("semantic vision blindness macro mismatch")
            for name in ("see_invisible", "infravision"):
                value = senses.get(name)
                if not isinstance(value, dict) or type(value.get("intrinsic")) is not int or type(value.get("extrinsic")) is not int or type(value.get("effective")) is not bool or value["effective"] is not bool(value["intrinsic"] or value["extrinsic"]):
                    errors.append(f"semantic vision {name} input malformed")
            if senses.get("infravision", {}).get("vision_recalc_input") is not False:
                errors.append("semantic vision infravision must remain presentation-only")

    if isinstance(blockers, dict):
        for name in ("boulder", "visible_mimic", "effective"):
            if not _vision_bool_plane(blockers.get(name)):
                errors.append(f"semantic vision blocker {name} must be a 21x79 boolean plane")
            elif isinstance(planes, dict) and planes.get(f"dynamic_blocker_{name}") != _canonical_digest(blockers[name]):
                errors.append(f"semantic vision blocker {name} plane digest mismatch")
        if all(_vision_bool_plane(blockers.get(name)) for name in ("boulder", "visible_mimic", "effective")):
            for y in range(ROWNO):
                for x in range(OBS_COLNO):
                    if blockers["effective"][y][x] is not bool(blockers["boulder"][y][x] or blockers["visible_mimic"][y][x]):
                        errors.append("semantic vision effective blocker union mismatch")
                        break
                if errors and errors[-1] == "semantic vision effective blocker union mismatch":
                    break
        records = blockers.get("records")
        if not isinstance(records, list):
            errors.append("semantic vision blocker record list missing")
        else:
            for record in records:
                if not isinstance(record, dict) or record.get("kind") not in ("boulder", "mimic") or not all(type(record.get(name)) is int for name in ("x", "y", "native_x")) or not (0 <= record["x"] < OBS_COLNO and 0 <= record["y"] < ROWNO and record["native_x"] == record["x"] + 1):
                    errors.append("semantic vision blocker record malformed")
                    break

    if isinstance(recalc, dict) and not all(type(recalc.get(name)) is bool for name in ("full_recalc_pending", "vision_initialized", "in_level_generation")):
        errors.append("semantic vision recalc state malformed")
    return errors


class Rm(ctypes.Structure):
    """Exact arm64 layout of NetHack 3.6.6 ``struct rm`` on NLE v0.9.0."""

    _fields_ = [
        ("glyph", ctypes.c_int),
        ("typ", ctypes.c_int8),
        ("seenv", ctypes.c_uint8),
        ("_bitfields", ctypes.c_uint16),
    ]


class LightSource(ctypes.Structure):
    """Pinned Darwin arm64 ``light_source`` layout from ``include/lev.h``."""

    _fields_ = [
        ("next", ctypes.c_void_p),
        ("x", ctypes.c_int8),
        ("y", ctypes.c_int8),
        ("range", ctypes.c_int16),
        ("flags", ctypes.c_int16),
        ("type", ctypes.c_int16),
        ("id", ctypes.c_void_p),
    ]


class ObjDescr(ctypes.Structure):
    """Pinned prefix of ``struct objdescr`` used only to find source IDs."""

    _fields_ = [("name", ctypes.c_void_p), ("description", ctypes.c_void_p)]


class Engr(ctypes.Structure):
    """Pinned arm64 prefix/layout of NetHack's private ``struct engr``."""

    _fields_ = [
        ("nxt_engr", ctypes.c_void_p),
        ("engr_txt", ctypes.c_void_p),
        ("engr_x", ctypes.c_uint8),
        ("engr_y", ctypes.c_uint8),
        ("_padding", ctypes.c_uint16),
        ("engr_lth", ctypes.c_uint),
        ("engr_time", ctypes.c_long),
        ("engr_type", ctypes.c_uint8),
        ("_tail_padding", ctypes.c_uint8 * 7),
    ]


class Trap(ctypes.Structure):
    """Pinned arm64 prefix/layout of NetHack's private ``struct trap``."""

    _fields_ = [
        ("ntrap", ctypes.c_void_p),
        ("tx", ctypes.c_uint8),
        ("ty", ctypes.c_uint8),
        ("dst", ctypes.c_uint8 * 2),
        ("launch", ctypes.c_uint8 * 2),
        ("_bitfields", ctypes.c_uint8),
        ("_bitfields_padding", ctypes.c_uint8),
        ("vl", ctypes.c_uint8 * 8),
    ]


@functools.lru_cache(maxsize=1)
def _compiler_bitfield_layout() -> tuple[int, ...]:
    """Prove the raw bitfield mask with the pinned host C compiler.

    ``ctypes`` cannot declare C bitfield positions portably.  We therefore
    compile the exact relevant ``include/rm.h`` declaration (where
    ``Bitfield(x,n)`` is ``unsigned x:n``) with clang and inspect its bytes.
    This fails closed if compiler ABI, offsets, or bit order drift.
    """

    source = r"""
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <string.h>
struct rm_probe {
    int glyph;
    signed char typ;
    unsigned char seenv;
    unsigned flags : 5;
    unsigned horizontal : 1;
    unsigned lit : 1;
    unsigned waslit : 1;
    unsigned roomno : 6;
    unsigned edge : 1;
    unsigned candig : 1;
};
int main(void) {
    struct rm_probe value;
    unsigned char *raw = (unsigned char *) &value;
    memset(&value, 0, sizeof value);
    value.flags = 31U;
    printf("%zu,%zu,%zu,%zu,%u,%u,", sizeof value, offsetof(struct rm_probe, glyph), offsetof(struct rm_probe, typ), offsetof(struct rm_probe, seenv), (unsigned) raw[6], (unsigned) raw[7]);
    memset(&value, 0, sizeof value);
    value.horizontal = 1U;
    printf("%u,%u\n", (unsigned) raw[6], (unsigned) raw[7]);
    return 0;
}
"""
    with tempfile.TemporaryDirectory(prefix="nle-rm-bitfield-") as directory:
        binary = Path(directory) / "probe"
        try:
            compiled = subprocess.run(
                ["clang", "-x", "c", "-", "-o", str(binary)],
                input=source,
                text=True,
                capture_output=True,
                check=True,
            )
            del compiled
            executed = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            raise RuntimeError("clang could not prove the pinned struct rm bitfield ABI") from error
    try:
        layout = tuple(int(part) for part in executed.stdout.strip().split(","))
    except ValueError as error:
        raise RuntimeError("clang struct rm bitfield probe returned malformed output") from error
    if layout != EXPECTED_RM_BITFIELD_ABI:
        raise RuntimeError(f"clang struct rm bitfield ABI drifted: {layout!r} != {EXPECTED_RM_BITFIELD_ABI!r}")
    return layout


@functools.lru_cache(maxsize=1)
def _compiler_vision_input_layout() -> tuple[int, ...]:
    """Prove all non-``rm`` raw offsets used by the vision export.

    This is intentionally a compiler probe, not an inferred ctypes layout.
    The include ordering is the pinned header dependency ordering, with the
    generated ``pm.h`` deliberately unnecessary: the selected declarations
    never use its values.  ``MAXOCLASSES`` is the exact pinned enum value
    needed by ``flag.h``'s fixed arrays.
    """

    source = r'''
#include "config.h"
#include "global.h"
#include "wintype.h"
#include "dungeon.h"
#include "permonst.h"
#include "monst.h"
#include "you.h"
#include "flag.h"
#include "lev.h"
#include "artifact.h"
#include <stddef.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    struct you value;
    unsigned char *raw = (unsigned char *) &value;
    memset(&value, 0, sizeof value);
    value.uswallow = 1;
    value.uinwater = 1;
    printf("%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%u,%u,",
        sizeof(struct you), offsetof(struct you, uprops),
        offsetof(struct you, nv_range), offsetof(struct you, xray_range),
        offsetof(struct you, utrap), offsetof(struct you, utraptype),
        offsetof(struct you, ucreamed), offsetof(struct you, uswldtim),
        offsetof(struct you, uroleplay), sizeof(struct prop),
        offsetof(struct prop, intrinsic), (unsigned) raw[1796],
        (unsigned) raw[1797]);
    printf("%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu\n",
        sizeof(struct permonst), offsetof(struct permonst, mflags1),
        sizeof(struct monst), offsetof(struct monst, mappearance),
        offsetof(struct monst, m_ap_type), sizeof(light_source),
        offsetof(light_source, next), offsetof(light_source, x),
        offsetof(light_source, range), offsetof(light_source, flags),
        offsetof(light_source, type), offsetof(light_source, id),
        sizeof(struct instance_flags),
        offsetof(struct instance_flags, vision_inited), sizeof(struct artifact));
    return 0;
}
'''
    source_root = _pinned_source_root()
    include = source_root / "include"
    if not include.is_dir():
        raise RuntimeError("pinned NetHack source headers are unavailable for the vision ABI proof")
    with tempfile.TemporaryDirectory(prefix="nle-vision-input-abi-") as directory:
        binary = Path(directory) / "probe"
        try:
            subprocess.run(
                ["clang", "-DMAXOCLASSES=18", "-I", str(include), "-x", "c", "-", "-o", str(binary)],
                input=source,
                text=True,
                capture_output=True,
                check=True,
            )
            executed = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            raise RuntimeError("clang could not prove the pinned vision decision-input ABI") from error
    try:
        layout = tuple(int(part) for part in executed.stdout.strip().split(","))
    except ValueError as error:
        raise RuntimeError("clang vision decision-input ABI probe returned malformed output") from error
    if layout != EXPECTED_VISION_INPUT_ABI:
        raise RuntimeError(f"clang vision decision-input ABI drifted: {layout!r} != {EXPECTED_VISION_INPUT_ABI!r}")
    return layout


@functools.lru_cache(maxsize=1)
def _compiler_level_flags_layout() -> tuple[int, ...]:
    """Prove the raw ``dlevel_t.flags`` offsets used by ``dosounds``.

    The Python reader only interprets bytes after this independent compiler
    check agrees with the pinned headers.  In particular, it must not assume
    that a host compiler packs the 23 source bitfields like arm64 clang.
    """

    source = r'''
#define WARNCOUNT 0
#include "config.h"
#include "global.h"
#include "rm.h"
#include <stddef.h>
#include <stdio.h>
int main(void) {
    printf("%zu,%zu,%zu,%zu,%zu\n",
        sizeof(struct levelflags), sizeof(dlevel_t), offsetof(dlevel_t, flags),
        offsetof(struct levelflags, nfountains), offsetof(struct levelflags, nsinks));
    return 0;
}
'''
    source_root = _pinned_source_root()
    include = source_root / "include"
    if not include.is_dir():
        raise RuntimeError("pinned NetHack source headers are unavailable for the level-flags ABI proof")
    with tempfile.TemporaryDirectory(prefix="nle-level-flags-abi-") as directory:
        binary = Path(directory) / "probe"
        try:
            subprocess.run(
                ["clang", "-I", str(include), "-x", "c", "-", "-o", str(binary)],
                input=source,
                text=True,
                capture_output=True,
                check=True,
            )
            executed = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            raise RuntimeError("clang could not prove the pinned level-flags ABI") from error
    try:
        layout = tuple(int(part) for part in executed.stdout.strip().split(","))
    except ValueError as error:
        raise RuntimeError("clang level-flags ABI probe returned malformed output") from error
    if layout != EXPECTED_LEVEL_FLAGS_ABI:
        raise RuntimeError(f"clang level-flags ABI drifted: {layout!r} != {EXPECTED_LEVEL_FLAGS_ABI!r}")
    return layout


@functools.lru_cache(maxsize=1)
def _compiler_engraving_layout() -> tuple[int, ...]:
    """Prove the private ``struct engr`` offsets before reading ``head_engr``."""

    source = r'''
#include "config.h"
#include "global.h"
#include "engrave.h"
#include <stddef.h>
#include <stdio.h>
int main(void) {
    printf("%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu\n",
        sizeof(struct engr), offsetof(struct engr, nxt_engr),
        offsetof(struct engr, engr_txt), offsetof(struct engr, engr_x),
        offsetof(struct engr, engr_y), offsetof(struct engr, engr_lth),
        offsetof(struct engr, engr_time), offsetof(struct engr, engr_type));
    return 0;
}
'''
    include = _pinned_source_root() / "include"
    if not include.is_dir():
        raise RuntimeError("pinned NetHack source headers are unavailable for the engraving ABI proof")
    with tempfile.TemporaryDirectory(prefix="nle-engraving-abi-") as directory:
        binary = Path(directory) / "probe"
        try:
            subprocess.run(["clang", "-I", str(include), "-x", "c", "-", "-o", str(binary)], input=source, text=True, capture_output=True, check=True)
            executed = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            raise RuntimeError("clang could not prove the pinned engraving ABI") from error
    try:
        layout = tuple(int(part) for part in executed.stdout.strip().split(","))
    except ValueError as error:
        raise RuntimeError("clang engraving ABI probe returned malformed output") from error
    if layout != EXPECTED_ENGRAVING_ABI:
        raise RuntimeError(f"clang engraving ABI drifted: {layout!r} != {EXPECTED_ENGRAVING_ABI!r}")
    return layout


@functools.lru_cache(maxsize=1)
def _compiler_trap_layout() -> tuple[int, ...]:
    """Prove the private ``struct trap`` layout before reading ``ftrap``."""

    source = r'''
#include "config.h"
#include "global.h"
#include "dungeon.h"
#include "trap.h"
#include <stddef.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    struct trap value;
    unsigned char *raw = (unsigned char *) &value;
    memset(&value, 0, sizeof value);
    value.ttyp = 31;
    value.tseen = 1;
    value.once = 1;
    value.madeby_u = 1;
    size_t bitfields = sizeof(value);
    for (size_t index = 0; index < sizeof(value); ++index) {
        if (raw[index] == 0xff) {
            bitfields = index;
            break;
        }
    }
    if (bitfields == sizeof(value)) {
        return 2;
    }
    printf("%zu,%zu,%zu,%zu,%zu,%zu,%zu,%zu\n",
        sizeof(struct trap), offsetof(struct trap, ntrap),
        offsetof(struct trap, tx), offsetof(struct trap, ty),
        offsetof(struct trap, dst), offsetof(struct trap, launch),
        bitfields,
        offsetof(struct trap, vl));
    return 0;
}
'''
    include = _pinned_source_root() / "include"
    if not include.is_dir():
        raise RuntimeError("pinned NetHack source headers are unavailable for the trap ABI proof")
    with tempfile.TemporaryDirectory(prefix="nle-trap-abi-") as directory:
        binary = Path(directory) / "probe"
        try:
            subprocess.run(
                ["clang", "-I", str(include), "-x", "c", "-", "-o", str(binary)],
                input=source,
                text=True,
                capture_output=True,
                check=True,
            )
            executed = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            raise RuntimeError("clang could not prove the pinned trap ABI") from error
    try:
        layout = tuple(int(part) for part in executed.stdout.strip().split(","))
    except ValueError as error:
        raise RuntimeError("clang trap ABI probe returned malformed output") from error
    if layout != EXPECTED_TRAP_ABI:
        raise RuntimeError(f"clang trap ABI drifted: {layout!r} != {EXPECTED_TRAP_ABI!r}")
    return layout


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _symbol_offsets(path: Path) -> dict[str, int]:
    if sys.platform != "darwin":
        raise RuntimeError("native map/FOV oracle reader supports only the pinned macOS NLE wheel")
    completed = subprocess.run(["nm", "-a", str(path)], check=True, text=True, capture_output=True)
    wanted = {
        "level", "viz_array", "rn2", "u", "youmonst", "ublindf",
        "vision_full_recalc", "iflags", "in_mklev", "dungeon_topology",
        "light_base", "obj_descr", "artilist", "head_engr",
        "ftrap",
    }
    offsets: dict[str, int] = {}
    pattern = re.compile(r"^([0-9A-Fa-f]+)\s+\w\s+_(" + "|".join(sorted(wanted)) + r")$")
    for line in completed.stdout.splitlines():
        match = pattern.match(line)
        if match:
            offsets[match.group(2)] = int(match.group(1), 16)
    if set(offsets) != wanted:
        raise RuntimeError(f"pinned NLE binary lacks unambiguous map/FOV symbols: {sorted(offsets)}")
    return offsets


@dataclass(frozen=True)
class NativeMapFovSnapshot:
    """A NLE-screen-aligned, native pre-action source snapshot."""

    terrain_type: tuple[tuple[int, ...], ...]
    terrain_flags: tuple[tuple[int, ...], ...]
    terrain_horizontal: tuple[tuple[bool, ...], ...]
    map_memory_glyph: tuple[tuple[int, ...], ...]
    map_memory_seenv: tuple[tuple[int, ...], ...]
    visibility_bits: tuple[tuple[int, ...], ...]
    binary_sha256: str
    compiler_bitfield_abi: tuple[int, ...] = EXPECTED_RM_BITFIELD_ABI
    terrain_lit: tuple[tuple[bool, ...], ...] | None = None
    terrain_was_lit: tuple[tuple[bool, ...], ...] | None = None
    vision_inputs: dict[str, Any] | None = None
    dynamic_blockers: dict[str, Any] | None = None
    light_sources: tuple[dict[str, Any], ...] | None = None
    recalc_state: dict[str, bool] | None = None
    compiler_vision_abi: tuple[int, ...] | None = None
    compiler_level_flags_abi: tuple[int, ...] = EXPECTED_LEVEL_FLAGS_ABI
    level_flags: dict[str, Any] | None = None
    engravings: tuple[dict[str, Any], ...] | None = None
    compiler_engraving_abi: tuple[int, ...] = EXPECTED_ENGRAVING_ABI
    traps: tuple[dict[str, Any], ...] | None = None
    compiler_trap_abi: tuple[int, ...] = EXPECTED_TRAP_ABI

    def _rows(self, value: tuple[tuple[int, ...], ...]) -> list[list[int]]:
        return [list(row) for row in value]

    def public_record(self) -> dict[str, Any]:
        if self.compiler_bitfield_abi != EXPECTED_RM_BITFIELD_ABI:
            raise RuntimeError("native map/FOV snapshot lacks the pinned compiler bitfield ABI proof")
        if self.compiler_level_flags_abi != EXPECTED_LEVEL_FLAGS_ABI:
            raise RuntimeError("native map/FOV snapshot lacks the pinned level-flags ABI proof")
        if self.compiler_engraving_abi != EXPECTED_ENGRAVING_ABI:
            raise RuntimeError("native map/FOV snapshot lacks the pinned engraving ABI proof")
        if self.compiler_trap_abi != EXPECTED_TRAP_ABI:
            raise RuntimeError("native map/FOV snapshot lacks the pinned trap ABI proof")
        terrain = self._rows(self.terrain_type)
        flags = self._rows(self.terrain_flags)
        horizontal = self._rows(self.terrain_horizontal)
        glyphs = self._rows(self.map_memory_glyph)
        seen = self._rows(self.map_memory_seenv)
        visibility = self._rows(self.visibility_bits)
        canonical = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        record = {
            "schema": "gamebench.nethack.native_map_fov_snapshot.v1",
            "provenance": "read_only_hash_verified_live_nle_v0_9_0_macho_level_and_viz_array",
            # A direct source export is useful for source assertions, but it
            # is not a license to hydrate the own engines or silently change
            # their FOV/memory behavior.  Keep the two decisions explicit in
            # every native record so an ``eligible`` status cannot be read as
            # gold implementation approval.
            "source_export_eligible": True,
            "gold_implementation_eligible": False,
            "binary_sha256": self.binary_sha256,
            "portability": "pinned macOS arm64 wheel only; reject another OS, architecture, NLE build, or libnethack SHA-256",
            "abi_layout": {
                "upstream_commit": PINNED_SOURCE_COMMIT,
                "source_definitions": "include/rm.h::struct rm; include/rm.h::dlevel_t.locations; include/vision.h::IN_SIGHT/COULD_SEE",
                "independent_clang_layout_check": "sizeof(struct rm)=8; offsetof(glyph,typ,seenv)=(0,4,5); sizeof(dlevel_t)=40368; locations row=168; COLNO=80; ROWNO=21",
                "independent_clang_bitfield_check": {
                    "source": "include/rm.h::Bitfield(flags,5), horizontal, lit, waslit with include/global.h::Bitfield(x,n)=unsigned x:n",
                    "probe": "sizeof, offsetof(glyph,typ,seenv), raw bytes for flags=31 and horizontal=1",
                    "result": list(self.compiler_bitfield_abi),
                    "expected": list(EXPECTED_RM_BITFIELD_ABI),
                },
            },
            "coordinate_contract": "NLE screen [y][x] maps to native level.locations[x+1][y]; native boundary x=0 is excluded",
            "full_map_terrain": terrain,
            "full_map_terrain_flags": flags,
            "full_map_terrain_horizontal": horizontal,
            "semantic_terrain_contract": {
                "raw_type": "full_map_terrain is struct rm.typ, not a rendered character",
                "raw_flags": "full_map_terrain_flags is struct rm.flags (five bits)",
                "horizontal": "full_map_terrain_horizontal is struct rm.horizontal",
                "door_mask": "for raw_type == 22 (DOOR), doormask aliases raw_flags exactly; D_NODOOR=0,D_BROKEN=1,D_ISOPEN=2,D_CLOSED=4,D_LOCKED=8,D_TRAPPED=16",
                "source_only": True,
                "gold_implementation_eligible": False,
            },
            "fov_visibility_mask": [[bool(bits & IN_SIGHT) for bits in row] for row in visibility],
            "fov_could_see_mask": [[bool(bits & COULD_SEE) for bits in row] for row in visibility],
            "map_memory": {"glyph": glyphs, "seenv": seen},
            "plane_sha256": {
                "full_map_terrain": canonical(terrain),
                "full_map_terrain_flags": canonical(flags),
                "full_map_terrain_horizontal": canonical(horizontal),
                "fov_visibility_bits": canonical(visibility),
                "map_memory_glyph": canonical(glyphs),
                "map_memory_seenv": canonical(seen),
            },
        }
        if self.level_flags is not None:
            record["level_flags"] = dict(self.level_flags)
            record["semantic_level_flags"] = {
                "source": "include/rm.h::struct levelflags; allmain.c::dosounds",
                "scope": "reset-bound level special-surface predicates for source RNG accounting",
                "source_only": True,
                "gold_implementation_eligible": False,
                "abi": {
                    "sizeof_dlevel_t": DLEVEL_SIZE,
                    "flags_offset": LEVEL_FLAGS_OFFSET,
                    "sizeof_levelflags": LEVEL_FLAGS_SIZE,
                    "nfountains_offset": 0,
                    "nsinks_offset": 1,
                },
            }
            record["abi_layout"]["independent_clang_level_flags_check"] = {
                "source": "include/rm.h::struct levelflags; dlevel_t.flags",
                "probe": "sizeof(struct levelflags), sizeof(dlevel_t), offsetof(dlevel_t, flags), counter offsets",
                "result": list(self.compiler_level_flags_abi),
                "expected": list(EXPECTED_LEVEL_FLAGS_ABI),
            }
        if self.engravings is not None:
            record["engravings"] = [dict(item) for item in self.engravings]
            record["semantic_engraving_contract"] = {
                "source": "engrave.c::head_engr/struct engr; monmove.c::wipe_engr_at",
                "scope": "reset-bound private floor engraving state used before actor movement",
                "source_only": True,
                "gold_implementation_eligible": False,
                "abi": {
                    "sizeof": EXPECTED_ENGRAVING_ABI[0],
                    "next": EXPECTED_ENGRAVING_ABI[1],
                    "text": EXPECTED_ENGRAVING_ABI[2],
                    "x": EXPECTED_ENGRAVING_ABI[3],
                    "y": EXPECTED_ENGRAVING_ABI[4],
                    "length": EXPECTED_ENGRAVING_ABI[5],
                    "time": EXPECTED_ENGRAVING_ABI[6],
                    "type": EXPECTED_ENGRAVING_ABI[7],
                },
            }
            record["abi_layout"]["independent_clang_engraving_check"] = {
                "source": "include/engrave.h::struct engr",
                "probe": "sizeof and offsetof of linked-list/text/coordinate/type fields",
                "result": list(self.compiler_engraving_abi),
                "expected": list(EXPECTED_ENGRAVING_ABI),
            }
        if self.traps is not None:
            record["traps"] = [dict(item) for item in self.traps]
            record["semantic_search_contract"] = {
                "source": "detect.c::dosearch0; trap.h::struct trap/ftrap",
                "scope": "reset-bound complete trap presence/type/tseen inputs for explicit SEARCH RNG replay",
                "source_only": True,
                "gold_implementation_eligible": False,
                "abi": {
                    "sizeof": EXPECTED_TRAP_ABI[0],
                    "ntrap": EXPECTED_TRAP_ABI[1],
                    "tx": EXPECTED_TRAP_ABI[2],
                    "ty": EXPECTED_TRAP_ABI[3],
                    "dst": EXPECTED_TRAP_ABI[4],
                    "launch": EXPECTED_TRAP_ABI[5],
                    "bitfields": EXPECTED_TRAP_ABI[6],
                    "union": EXPECTED_TRAP_ABI[7],
                },
            }
            record["abi_layout"]["independent_clang_trap_check"] = {
                "source": "include/trap.h::struct trap",
                "probe": "sizeof and offsetof of linked-list/coordinate/union fields; pinned bitfield storage byte",
                "result": list(self.compiler_trap_abi),
                "expected": list(EXPECTED_TRAP_ABI),
            }
        extension_values = (
            self.terrain_lit,
            self.terrain_was_lit,
            self.vision_inputs,
            self.dynamic_blockers,
            self.light_sources,
            self.recalc_state,
            self.compiler_vision_abi,
        )
        if all(value is not None for value in extension_values):
            assert self.terrain_lit is not None
            assert self.terrain_was_lit is not None
            assert self.vision_inputs is not None
            assert self.dynamic_blockers is not None
            assert self.light_sources is not None
            assert self.recalc_state is not None
            assert self.compiler_vision_abi is not None
            static_lit = self._rows(self.terrain_lit)
            remembered_lit = self._rows(self.terrain_was_lit)
            temporary_lit = [[bool(bits & 0x4) for bits in row] for row in visibility]
            boulder = self.dynamic_blockers["boulder"]
            mimic = self.dynamic_blockers["visible_mimic"]
            effective = self.dynamic_blockers["effective"]
            record["abi_layout"]["independent_clang_vision_input_check"] = {
                "source": "include/you.h, prop.h, monst.h, permonst.h, lev.h, flag.h, artifact.h",
                "probe": "sizeof/offsetof of all raw vision decision inputs; raw struct-you byte masks for uswallow and uinwater",
                "result": list(self.compiler_vision_abi),
                "expected": list(EXPECTED_VISION_INPUT_ABI),
            }
            record.update({
                "lighting": {
                    "static_lit": static_lit,
                    "remembered_lit": remembered_lit,
                    "temporary_lit": temporary_lit,
                    "active_light_sources": list(self.light_sources),
                },
                "vision_decision_inputs": self.vision_inputs,
                "dynamic_vision_blockers": {
                    "boulder": boulder,
                    "visible_mimic": mimic,
                    "effective": effective,
                    "records": self.dynamic_blockers["records"],
                },
                "vision_recalc_state": self.recalc_state,
                "semantic_vision_contract": {
                    "scope": "source-only complete pre-action decision inputs for src/vision.c::vision_recalc; never a gold FOV, lighting, memory, or presentation implementation input",
                    "visibility": "fov_visibility_mask/fov_could_see_mask are native result bits; temporary_lit is preserved separately from static level lighting",
                    "lighting": "static_lit is rm.lit, remembered_lit is rm.waslit, and active_light_sources is the read-only src/light.c light_base list",
                    "dynamic_blockers": "boulder and visible_mimic separate src/vision.c::does_block contributors from static rm terrain; source records carry no native pointers",
                    "presentation": "See_invisible is used only to activate an otherwise invisible mimic blocker; Infravision is exported as presentation-only and is not a vision_recalc input",
                    "recalc_trigger_limit": "vision_full_recalc retains only whether a recalc is pending; NetHack does not retain which earlier caller dirtied it, so no synthetic reason is exported",
                    "completeness_matrix": {
                        "static_los_topology": {"source": "rm.typ/rm.flags/rm.horizontal", "export": "full_map_terrain*", "complete_for_vision_recalc": True},
                        "static_lighting": {"source": "rm.lit/rm.waslit", "export": "lighting.static_lit/remembered_lit", "complete_for_vision_recalc": True},
                        "mobile_lighting": {"source": "light.c::light_base and TEMP_LIT", "export": "lighting.active_light_sources/temporary_lit", "complete_for_vision_recalc": True},
                        "hero_branches": {"source": "u, uprops, youmonst, ublindf, dungeon_topology", "export": "vision_decision_inputs", "complete_for_vision_recalc": True},
                        "dynamic_blockers": {"source": "level.objects/level.monsters and does_block predicate", "export": "dynamic_vision_blockers", "complete_for_vision_recalc": True},
                        "recalc_state": {"source": "vision_full_recalc/iflags.vision_inited/in_mklev", "export": "vision_recalc_state", "complete_for_current_state": True, "retained_caller_reason": False},
                        "map_memory": {"source": "rm.glyph/rm.seenv", "export": "map_memory", "complete_for_memory": True, "not_a_vision_input": True},
                        "presentation": {"source": "newsym/mapglyph and public observation", "export": "public controls only", "complete_for_vision_recalc": False},
                    },
                    "source_only": True,
                    "gold_implementation_eligible": False,
                },
            })
            record["plane_sha256"].update({
                "lighting_static_lit": canonical(static_lit),
                "lighting_remembered_lit": canonical(remembered_lit),
                "lighting_temporary_lit": canonical(temporary_lit),
                "dynamic_blocker_boulder": canonical(boulder),
                "dynamic_blocker_visible_mimic": canonical(mimic),
                "dynamic_blocker_effective": canonical(effective),
            })
        elif any(value is not None for value in extension_values):
            raise RuntimeError("native map/FOV snapshot has a partial semantic vision extension")
        return record


class PinnedNleMapFovReader:
    """A fail-closed, strictly read-only view of one live NLE instance."""

    def __init__(self, nethack_instance: Any):
        if platform.machine() != "arm64":
            raise RuntimeError("native map/FOV reader supports only the pinned macOS arm64 NLE wheel")
        path = Path(str(getattr(nethack_instance, "dlpath", ""))).resolve()
        if not path.is_file():
            raise RuntimeError("live NLE instance does not expose its copied libnethack path")
        try:
            from nle.nethack.nethack import DLPATH
        except ImportError as error:
            raise RuntimeError("pinned NLE runtime identity is unavailable") from error
        live_sha = _sha256(path)
        installed_sha = _sha256(Path(DLPATH).resolve())
        if live_sha != PINNED_BINARY_SHA256 or installed_sha != PINNED_BINARY_SHA256 or live_sha != installed_sha:
            raise RuntimeError("live copied libnethack is not the exact pinned NLE 0.9.0 oracle binary")
        if (
            ctypes.sizeof(Rm) != RM_SIZE
            or Rm.glyph.offset != RM_GLYPH_OFFSET
            or Rm.typ.offset != RM_TYP_OFFSET
            or Rm.seenv.offset != RM_SEENV_OFFSET
            or Rm._bitfields.offset != RM_BITFIELDS_OFFSET
        ):
            raise RuntimeError("host ctypes struct rm layout does not match the pinned NLE 0.9.0 ABI")
        if (
            ctypes.sizeof(LightSource) != 24
            or LightSource.next.offset != 0
            or LightSource.x.offset != 8
            or LightSource.range.offset != 10
            or LightSource.flags.offset != 12
            or LightSource.type.offset != 14
            or LightSource.id.offset != 16
            or ctypes.sizeof(ObjDescr) != 16
        ):
            raise RuntimeError("host ctypes light-source/object-description layout does not match the pinned NLE ABI")
        if (
            ctypes.sizeof(Engr) != EXPECTED_ENGRAVING_ABI[0]
            or Engr.nxt_engr.offset != EXPECTED_ENGRAVING_ABI[1]
            or Engr.engr_txt.offset != EXPECTED_ENGRAVING_ABI[2]
            or Engr.engr_x.offset != EXPECTED_ENGRAVING_ABI[3]
            or Engr.engr_y.offset != EXPECTED_ENGRAVING_ABI[4]
            or Engr.engr_lth.offset != EXPECTED_ENGRAVING_ABI[5]
            or Engr.engr_time.offset != EXPECTED_ENGRAVING_ABI[6]
            or Engr.engr_type.offset != EXPECTED_ENGRAVING_ABI[7]
        ):
            raise RuntimeError("host ctypes engraving layout does not match the pinned NLE ABI")
        self._compiler_bitfield_abi = _compiler_bitfield_layout()
        self._compiler_vision_abi = _compiler_vision_input_layout()
        self._compiler_level_flags_abi = _compiler_level_flags_layout()
        self._compiler_engraving_abi = _compiler_engraving_layout()
        self._compiler_trap_abi = _compiler_trap_layout()
        offsets = _symbol_offsets(path)
        library = ctypes.CDLL(str(path))
        rn2_address = int(ctypes.cast(getattr(library, "rn2"), ctypes.c_void_p).value or 0)
        base = rn2_address - offsets["rn2"]
        if base <= 0:
            raise RuntimeError("NLE Mach-O slide is invalid")
        self._level_address = base + offsets["level"]
        self._viz_pointer_address = base + offsets["viz_array"]
        self._u_address = base + offsets["u"]
        self._youmonst_address = base + offsets["youmonst"]
        self._ublindf_pointer_address = base + offsets["ublindf"]
        self._vision_full_recalc_address = base + offsets["vision_full_recalc"]
        self._iflags_address = base + offsets["iflags"]
        self._in_mklev_address = base + offsets["in_mklev"]
        self._dungeon_topology_address = base + offsets["dungeon_topology"]
        self._light_base_pointer_address = base + offsets["light_base"]
        self._obj_descr_address = base + offsets["obj_descr"]
        self._artilist_address = base + offsets["artilist"]
        self._head_engr_pointer_address = base + offsets["head_engr"]
        self._ftrap_pointer_address = base + offsets["ftrap"]
        if any(address <= 0 for address in (
            self._level_address, self._u_address, self._youmonst_address,
            self._ublindf_pointer_address, self._vision_full_recalc_address,
            self._iflags_address, self._in_mklev_address,
            self._dungeon_topology_address, self._light_base_pointer_address,
            self._obj_descr_address, self._artilist_address,
            self._head_engr_pointer_address,
            self._ftrap_pointer_address,
        )):
            raise RuntimeError("pinned NLE vision symbols resolved to an invalid address")
        self._lens_object_type = self._source_name_index(self._obj_descr_address, MAX_OBJECT_TYPES, "lenses", item_size=ctypes.sizeof(ObjDescr), name_offset=0)
        self._boulder_object_type = self._source_name_index(self._obj_descr_address, MAX_OBJECT_TYPES, "boulder", item_size=ctypes.sizeof(ObjDescr), name_offset=0)
        self._eyes_artifact_id = self._source_name_index(self._artilist_address, MAX_ARTIFACTS, "The Eyes of the Overworld", item_size=80, name_offset=8)
        self._library = library  # Retain the loaded image while its memory is read.
        self._binary_sha256 = live_sha

    @staticmethod
    def _source_name_index(address: int, count: int, wanted: str, *, item_size: int, name_offset: int) -> int:
        """Find a generated source enum through its immutable name table.

        NetHack's generated ``onames.h`` is not distributed beside the pinned
        source checkout.  The live binary does carry its fixed ``obj_descr``
        and ``artilist`` tables, so resolve the two enum IDs through those
        source tables and fail closed on a duplicate, missing, or malformed
        name.  The resulting record stores only integers, never addresses.
        """

        matches: list[int] = []
        for index in range(count):
            pointer = int(ctypes.c_void_p.from_address(address + index * item_size + name_offset).value or 0)
            if not pointer:
                continue
            try:
                name = ctypes.string_at(pointer, 128).split(b"\0", 1)[0].decode("utf-8")
            except (UnicodeDecodeError, ValueError) as error:
                raise RuntimeError("pinned NLE source name table is malformed") from error
            if name == wanted:
                matches.append(index)
        if len(matches) != 1:
            raise RuntimeError(f"pinned NLE source name table has {len(matches)} entries for {wanted!r}")
        return matches[0]

    def _level_cells(self) -> Any:
        return (Rm * (COLNO * ROWNO)).from_address(self._level_address)

    def _viz_rows(self) -> Any:
        pointer = int(ctypes.c_void_p.from_address(self._viz_pointer_address).value or 0)
        if pointer <= 0:
            raise RuntimeError("NLE viz_array is null before source snapshot")
        rows = (ctypes.c_void_p * ROWNO).from_address(pointer)
        addresses = [int(row or 0) for row in rows]
        if any(address <= 0 for address in addresses):
            raise RuntimeError("NLE viz_array contains a null row pointer")
        if any(addresses[index + 1] - addresses[index] != COLNO for index in range(ROWNO - 1)):
            raise RuntimeError("NLE viz_array row stride no longer matches the pinned char[ROWNO][COLNO] layout")
        return rows

    @staticmethod
    def _i32(raw: bytes, offset: int) -> int:
        return struct.unpack_from("i", raw, offset)[0]

    @staticmethod
    def _i64(raw: bytes, offset: int) -> int:
        return struct.unpack_from("q", raw, offset)[0]

    @staticmethod
    def _i8(raw: bytes, offset: int) -> int:
        return struct.unpack_from("b", raw, offset)[0]

    @staticmethod
    def _level_matches(raw: bytes, offset: int, topology_address: int) -> bool:
        dnum, dlevel = PinnedNleMapFovReader._i8(raw, 10), PinnedNleMapFovReader._i8(raw, 11)
        expected_dnum = int(ctypes.c_int8.from_address(topology_address + offset).value)
        expected_dlevel = int(ctypes.c_int8.from_address(topology_address + offset + 1).value)
        return bool(expected_dnum or expected_dlevel) and (dnum, dlevel) == (expected_dnum, expected_dlevel)

    def _property(self, raw: bytes, index: int) -> tuple[int, int]:
        start = YOU_UPROPS_OFFSET + index * PROP_SIZE
        return self._i64(raw, start), self._i64(raw, start + PROP_INTRINSIC_OFFSET)

    def _vision_inputs(self) -> dict[str, Any]:
        raw = ctypes.string_at(self._u_address, YOU_SIZE)
        if len(raw) != YOU_SIZE:
            raise RuntimeError("short native struct you read for vision decision inputs")
        native_x, native_y = self._i8(raw, 0), self._i8(raw, 1)
        if not (1 <= native_x < COLNO and 0 <= native_y < ROWNO):
            raise RuntimeError("native vision player coordinate is outside the NLE map plane")
        blindfold_address = int(ctypes.c_void_p.from_address(self._ublindf_pointer_address).value or 0)
        blindfolded = False
        eyes_override = False
        if blindfold_address:
            if blindfold_address % ctypes.alignment(ctypes.c_void_p):
                raise RuntimeError("native vision blindfold pointer is unaligned")
            blindfold = NativeObj.from_address(blindfold_address)
            if not (0 <= int(blindfold.otyp) < MAX_OBJECT_TYPES):
                raise RuntimeError("native vision blindfold object type is invalid")
            blindfolded = int(blindfold.otyp) != self._lens_object_type
            eyes_override = int(blindfold.oartifact) == self._eyes_artifact_id
        youmonst = NativeMonst.from_address(self._youmonst_address)
        species_address = int(youmonst.data or 0)
        if species_address <= 0 or species_address % ctypes.alignment(ctypes.c_void_p):
            raise RuntimeError("native vision player species pointer is invalid")
        has_eyes = not bool(ctypes.c_ulong.from_address(species_address + PERMONST_MFLAGS1_OFFSET).value & M1_NOEYES)
        see_invisible_extrinsic, see_invisible_intrinsic = self._property(raw, SEE_INVIS_PROP)
        infravision_extrinsic, infravision_intrinsic = self._property(raw, INFRAVISION_PROP)
        _unused_blinded_extrinsic, blinded_intrinsic = self._property(raw, BLINDED_PROP)
        roleplay_blind = bool(raw[YOU_ROLEPLAY_OFFSET])
        blind = bool(roleplay_blind or blinded_intrinsic or blindfolded or not has_eyes) and not eyes_override
        underwater = bool(raw[YOU_FLAGS_OFFSET] & YOU_UINWATER_MASK)
        return {
            "hero": {
                "native_x": native_x,
                "native_y": native_y,
                "night_vision_range": self._i32(raw, YOU_NV_RANGE_OFFSET),
                "xray_range": self._i32(raw, YOU_XRAY_RANGE_OFFSET),
                "swallowed": bool(raw[YOU_FLAGS_OFFSET] & YOU_USWALLOW_MASK),
                "underwater": underwater,
                "pit_trapped": bool(self._i32(raw, YOU_UTRAP_OFFSET) and self._i32(raw, YOU_UTRAPTYPE_OFFSET) == TT_PIT),
            },
            "level": {
                "rogue_level": self._level_matches(raw, DUNGEON_TOPOLOGY_ROGUE_OFFSET, self._dungeon_topology_address),
                "water_level": self._level_matches(raw, DUNGEON_TOPOLOGY_WATER_OFFSET, self._dungeon_topology_address),
                "underwater_branch_active": underwater and not self._level_matches(raw, DUNGEON_TOPOLOGY_WATER_OFFSET, self._dungeon_topology_address),
            },
            "blindness": {
                "roleplay_blind": roleplay_blind,
                "blinded_intrinsic": blinded_intrinsic,
                "blindfolded": blindfolded,
                "has_eyes": has_eyes,
                "eyes_of_overworld_override": eyes_override,
                "cream_timeout": self._i32(raw, YOU_UCREAMED_OFFSET),
                "blind": blind,
            },
            "senses": {
                "see_invisible": {
                    "intrinsic": see_invisible_intrinsic,
                    "extrinsic": see_invisible_extrinsic,
                    "effective": bool(see_invisible_intrinsic or see_invisible_extrinsic),
                },
                "infravision": {
                    "intrinsic": infravision_intrinsic,
                    "extrinsic": infravision_extrinsic,
                    "effective": bool(infravision_intrinsic or infravision_extrinsic),
                    "vision_recalc_input": False,
                },
            },
        }

    def _dynamic_blockers(self, *, see_invisible: bool) -> dict[str, Any]:
        """Copy the non-``rm`` ``does_block`` inputs without calling C code."""

        object_grid = self._level_address + COLNO * ROWNO * RM_SIZE
        monster_grid = object_grid + COLNO * ROWNO * ctypes.sizeof(ctypes.c_void_p)
        boulder = [[False for _ in range(OBS_COLNO)] for _ in range(ROWNO)]
        mimic = [[False for _ in range(OBS_COLNO)] for _ in range(ROWNO)]
        records: list[dict[str, Any]] = []
        for y in range(ROWNO):
            for screen_x in range(OBS_COLNO):
                native_x = screen_x + 1
                address = int(ctypes.c_void_p.from_address(object_grid + (native_x * ROWNO + y) * ctypes.sizeof(ctypes.c_void_p)).value or 0)
                local_seen: set[int] = set()
                for _ in range(MAX_OBJECTS):
                    if not address:
                        break
                    if address in local_seen or address % ctypes.alignment(ctypes.c_void_p):
                        raise RuntimeError("native vision floor-object stack is cyclic or unaligned")
                    local_seen.add(address)
                    obj = NativeObj.from_address(address)
                    if (int(obj.ox), int(obj.oy)) != (native_x, y) or not (0 <= int(obj.otyp) < MAX_OBJECT_TYPES):
                        raise RuntimeError("native vision floor-object stack disagrees with its source coordinate")
                    if int(obj.otyp) == self._boulder_object_type:
                        boulder[y][screen_x] = True
                        records.append({"kind": "boulder", "x": screen_x, "y": y, "native_x": native_x, "object_id": int(obj.o_id), "object_type": int(obj.otyp)})
                    address = int(obj.nexthere or 0)
                else:
                    raise RuntimeError("native vision floor-object stack exceeded its bounded traversal")

                monster_address = int(ctypes.c_void_p.from_address(monster_grid + (native_x * ROWNO + y) * ctypes.sizeof(ctypes.c_void_p)).value or 0)
                if not monster_address:
                    continue
                if monster_address % ctypes.alignment(ctypes.c_void_p):
                    raise RuntimeError("native vision monster grid pointer is unaligned")
                monster = NativeMonst.from_address(monster_address)
                if (int(monster.mx), int(monster.my)) != (native_x, y) or int(monster.m_id) <= 0:
                    raise RuntimeError("native vision monster grid disagrees with source monster position")
                appearance_type = int(monster.m_ap_type) & M_AP_TYPMASK
                appearance = int(monster.mappearance)
                invisible = bool(monster._bits[0] & 0x02)
                mimics_boulder = appearance_type == M_AP_OBJECT and appearance == self._boulder_object_type
                mimics_feature = appearance_type == M_AP_FURNITURE and (appearance in (S_VCDOOR, S_HCDOOR, S_TREE) or appearance < S_NDOOR)
                blocks = (not invisible or see_invisible) and (mimics_boulder or mimics_feature)
                if blocks:
                    mimic[y][screen_x] = True
                    records.append({
                        "kind": "mimic", "x": screen_x, "y": y, "native_x": native_x,
                        "monster_id": int(monster.m_id), "appearance_type": appearance_type,
                        "mappearance": appearance, "invisible": invisible,
                        "see_invisible": see_invisible,
                    })
        effective = [[bool(boulder[y][x] or mimic[y][x]) for x in range(OBS_COLNO)] for y in range(ROWNO)]
        return {"boulder": boulder, "visible_mimic": mimic, "effective": effective, "records": records}

    def _light_sources(self) -> tuple[dict[str, Any], ...]:
        address = int(ctypes.c_void_p.from_address(self._light_base_pointer_address).value or 0)
        sources: list[dict[str, Any]] = []
        listed: set[int] = set()
        for _ in range(MAX_VISION_LIGHT_SOURCES):
            if not address:
                break
            if address in listed or address % ctypes.alignment(ctypes.c_void_p):
                raise RuntimeError("native vision light-source list is cyclic or unaligned")
            listed.add(address)
            source = LightSource.from_address(address)
            source_type = int(source.type)
            owner_address = int(source.id or 0)
            if source_type not in (LS_OBJECT, LS_MONSTER) or owner_address <= 0 or not (0 <= int(source.x) < COLNO and 0 <= int(source.y) < ROWNO and 1 <= int(source.range) <= 15):
                raise RuntimeError("native vision light-source record is invalid")
            if source_type == LS_OBJECT:
                owner = NativeObj.from_address(owner_address)
                if int(owner.o_id) <= 0:
                    raise RuntimeError("native vision light-source object owner is invalid")
                owner_kind, owner_id = "object", int(owner.o_id)
            elif owner_address == self._youmonst_address:
                owner_kind, owner_id = "hero", 0
            else:
                owner = NativeMonst.from_address(owner_address)
                if int(owner.m_id) <= 0:
                    raise RuntimeError("native vision light-source monster owner is invalid")
                owner_kind, owner_id = "monster", int(owner.m_id)
            sources.append({
                "owner_kind": owner_kind,
                "owner_id": owner_id,
                "native_x": int(source.x),
                "y": int(source.y),
                "range": int(source.range),
                "source_type": source_type,
                "showing": bool(int(source.flags) & 0x01),
            })
            address = int(source.next or 0)
        else:
            raise RuntimeError("native vision light-source list exceeded its bounded traversal")
        if len({(source["owner_kind"], source["owner_id"]) for source in sources}) != len(sources):
            raise RuntimeError("native vision light-source list has duplicate source owners")
        return tuple(sources)

    def _engravings(self) -> tuple[dict[str, Any], ...]:
        """Copy the private reset engraving list without calling native code."""

        address = int(ctypes.c_void_p.from_address(self._head_engr_pointer_address).value or 0)
        records: list[dict[str, Any]] = []
        listed: set[int] = set()
        for _ in range(MAX_ENGRAVINGS):
            if not address:
                break
            if address in listed or address % ctypes.alignment(ctypes.c_void_p):
                raise RuntimeError("native engraving list is cyclic or unaligned")
            listed.add(address)
            engraving = Engr.from_address(address)
            x, y = int(engraving.engr_x), int(engraving.engr_y)
            kind, length = int(engraving.engr_type), int(engraving.engr_lth)
            text_address = int(engraving.engr_txt or 0)
            if not (1 <= x < COLNO and 0 <= y < ROWNO and 1 <= kind <= 6 and 1 <= length <= MAX_ENGRAVING_TEXT and text_address > 0):
                raise RuntimeError("native engraving record is outside the pinned source range")
            raw = ctypes.string_at(text_address, length)
            if len(raw) != length or not raw.endswith(b"\0"):
                raise RuntimeError("native engraving text is not NUL-terminated at its source length")
            try:
                text = raw[:-1].decode("utf-8")
            except UnicodeDecodeError as error:
                raise RuntimeError("native engraving text is not valid UTF-8") from error
            records.append({
                "native_x": x,
                "y": y,
                "engr_type": kind,
                "engr_time": int(engraving.engr_time),
                "engr_lth": length,
                "text": text,
            })
            address = int(engraving.nxt_engr or 0)
        else:
            raise RuntimeError("native engraving list exceeded its bounded traversal")
        if len({(record["native_x"], record["y"]) for record in records}) != len(records):
            raise RuntimeError("native engraving list has duplicate coordinates")
        return tuple(records)

    def _traps(self) -> tuple[dict[str, Any], ...]:
        """Copy the complete reset ``ftrap`` list without calling native code."""

        address = int(ctypes.c_void_p.from_address(self._ftrap_pointer_address).value or 0)
        records: list[dict[str, Any]] = []
        listed: set[int] = set()
        for _ in range(MAX_TRAPS):
            if not address:
                break
            if address in listed or address % ctypes.alignment(ctypes.c_void_p):
                raise RuntimeError("native trap list is cyclic or unaligned")
            listed.add(address)
            trap = Trap.from_address(address)
            native_x, y = int(trap.tx), int(trap.ty)
            bits = int(trap._bitfields)
            trap_type = bits & 0x1F
            if not (1 <= native_x < COLNO and 0 <= y < ROWNO and 0 <= trap_type <= TRAP_TYPES_MAX):
                raise RuntimeError("native trap record is outside the pinned source range")
            records.append({
                "native_x": native_x,
                "x": native_x - 1,
                "y": y,
                "trap_type": trap_type,
                "tseen": bool(bits & 0x20),
                "once": bool(bits & 0x40),
                "madeby_u": bool(bits & 0x80),
            })
            address = int(trap.ntrap or 0)
        else:
            raise RuntimeError("native trap list exceeded its bounded traversal")
        if len({(record["native_x"], record["y"]) for record in records}) != len(records):
            raise RuntimeError("native trap list has duplicate coordinates")
        return tuple(records)

    def _recalc_state(self) -> dict[str, bool]:
        return {
            "full_recalc_pending": bool(ctypes.c_uint8.from_address(self._vision_full_recalc_address).value),
            "vision_initialized": bool(ctypes.c_uint8.from_address(self._iflags_address + INSTANCE_FLAGS_VISION_INITED_OFFSET).value),
            "in_level_generation": bool(ctypes.c_uint8.from_address(self._in_mklev_address).value),
        }

    def snapshot(self) -> NativeMapFovSnapshot:
        cells = self._level_cells()
        rows = self._viz_rows()
        terrain: list[tuple[int, ...]] = []
        terrain_flags: list[tuple[int, ...]] = []
        terrain_horizontal: list[tuple[bool, ...]] = []
        terrain_lit: list[tuple[bool, ...]] = []
        terrain_was_lit: list[tuple[bool, ...]] = []
        glyphs: list[tuple[int, ...]] = []
        seenv: list[tuple[int, ...]] = []
        visibility: list[tuple[int, ...]] = []
        for y in range(ROWNO):
            terrain_row: list[int] = []
            terrain_flags_row: list[int] = []
            terrain_horizontal_row: list[bool] = []
            terrain_lit_row: list[bool] = []
            terrain_was_lit_row: list[bool] = []
            glyph_row: list[int] = []
            seen_row: list[int] = []
            visibility_row: list[int] = []
            for screen_x in range(OBS_COLNO):
                # NLE maps native x=1..79 to screen x=0..78.
                cell = cells[(screen_x + 1) * ROWNO + y]
                terrain_type = int(cell.typ)
                if terrain_type not in VALID_TERRAIN_TYPES:
                    raise RuntimeError(f"native level terrain type is outside the pinned v0.9.0 enum: {terrain_type}")
                bits = int(ctypes.c_ubyte.from_address(int(rows[y]) + screen_x + 1).value)
                if bits & ~0x7:
                    raise RuntimeError(f"native viz_array contains unknown vision bits: {bits}")
                terrain_row.append(terrain_type)
                raw_bitfields = int(cell._bitfields)
                flags = raw_bitfields & RM_FLAGS_MASK
                horizontal = bool(raw_bitfields & RM_HORIZONTAL_MASK)
                if not 0 <= flags <= RM_FLAGS_MASK:
                    raise RuntimeError(f"native struct rm flags are outside the pinned five-bit range: {flags}")
                terrain_flags_row.append(flags)
                terrain_horizontal_row.append(horizontal)
                terrain_lit_row.append(bool(raw_bitfields & RM_LIT_MASK))
                terrain_was_lit_row.append(bool(raw_bitfields & RM_WASLIT_MASK))
                glyph_row.append(int(cell.glyph))
                seen_row.append(int(cell.seenv))
                visibility_row.append(bits)
            terrain.append(tuple(terrain_row))
            terrain_flags.append(tuple(terrain_flags_row))
            terrain_horizontal.append(tuple(terrain_horizontal_row))
            terrain_lit.append(tuple(terrain_lit_row))
            terrain_was_lit.append(tuple(terrain_was_lit_row))
            glyphs.append(tuple(glyph_row))
            seenv.append(tuple(seen_row))
            visibility.append(tuple(visibility_row))
        vision_inputs = self._vision_inputs()
        return NativeMapFovSnapshot(
            terrain_type=tuple(terrain),
            terrain_flags=tuple(terrain_flags),
            terrain_horizontal=tuple(terrain_horizontal),
            map_memory_glyph=tuple(glyphs),
            map_memory_seenv=tuple(seenv),
            visibility_bits=tuple(visibility),
            binary_sha256=self._binary_sha256,
            compiler_bitfield_abi=self._compiler_bitfield_abi,
            terrain_lit=tuple(terrain_lit),
            terrain_was_lit=tuple(terrain_was_lit),
            vision_inputs=vision_inputs,
            dynamic_blockers=self._dynamic_blockers(see_invisible=vision_inputs["senses"]["see_invisible"]["effective"]),
            light_sources=self._light_sources(),
            recalc_state=self._recalc_state(),
            compiler_vision_abi=self._compiler_vision_abi,
            compiler_level_flags_abi=self._compiler_level_flags_abi,
            level_flags=self._level_flags(),
            engravings=self._engravings(),
            compiler_engraving_abi=self._compiler_engraving_abi,
            traps=self._traps(),
            compiler_trap_abi=self._compiler_trap_abi,
        )

    def _level_flags(self) -> dict[str, Any]:
        """Copy reset/current ``struct levelflags`` without native pointers."""

        raw = ctypes.string_at(self._level_address + LEVEL_FLAGS_OFFSET, LEVEL_FLAGS_SIZE)
        if len(raw) != LEVEL_FLAGS_SIZE:
            raise RuntimeError("short native level-flags read")
        # Bitfield ordering is pinned by the same clang ABI used for rm.h:
        # first byte after the counters contains has_shop..has_temple, and
        # the next contains has_swamp..corrmaze.
        first, second = raw[2], raw[3]
        names_first = ("has_shop", "has_vault", "has_zoo", "has_court", "has_morgue", "has_beehive", "has_barracks", "has_temple")
        names_second = ("has_swamp", "noteleport", "hardfloor", "nommap", "hero_memory", "shortsighted", "graveyard", "sokoban_rules")
        flags = {"nfountains": int(raw[0]), "nsinks": int(raw[1])}
        flags.update({name: bool(first & (1 << index)) for index, name in enumerate(names_first)})
        flags.update({name: bool(second & (1 << index)) for index, name in enumerate(names_second)})
        # The final byte contains the five maze/arboreal flags; preserve the
        # bits even though dlvl-1 source draw accounting currently uses only
        # the special-room predicates above.
        last = raw[4]
        for index, name in enumerate(("is_maze_lev", "is_cavernous_lev", "arboreal", "wizard_bones", "corrmaze")):
            flags[name] = bool(last & (1 << index))
        return flags

    def validate_against_public_pre_action(self, snapshot: NativeMapFovSnapshot, observation: dict[str, Any], nethack: Any) -> dict[str, int]:
        """Prove layout and coordinate transform with independently rendered cells.

        Only direct static cmap pixels are compared: hero/entity overlays and
        blank cmap background do not establish a terrain identity.
        """

        glyphs = observation.get("glyphs")
        chars = observation.get("chars")
        blstats = observation.get("blstats")
        if glyphs is None or chars is None or blstats is None:
            raise RuntimeError("public NLE pre-action controls are absent")
        checked = 0
        wrong_coordinate_mismatches = 0
        closed_door_controls = 0
        open_door_controls = 0
        for y in range(ROWNO):
            for x in range(OBS_COLNO):
                glyph = int(glyphs[y][x])
                char = chr(int(chars[y][x]))
                if not (bool(nethack.glyph_is_cmap(glyph)) and char in STATIC_TERRAIN_CHARS):
                    continue
                if glyph != snapshot.map_memory_glyph[y][x]:
                    raise RuntimeError("native level glyph disagrees with direct static public NLE map cell")
                if snapshot.terrain_type[y][x] == DOOR_TERRAIN_TYPE:
                    doormask = snapshot.terrain_flags[y][x]
                    if char == "+":
                        if not doormask & (D_CLOSED | D_LOCKED):
                            raise RuntimeError("public closed-door glyph disagrees with native struct rm.doormask")
                        closed_door_controls += 1
                    elif char in "|-":
                        if not (doormask & D_ISOPEN) or doormask & (D_CLOSED | D_LOCKED | D_TRAPPED):
                            raise RuntimeError("public open-door glyph disagrees with native struct rm.doormask")
                        # display.c chooses S_hodoor when ``horizontal`` is
                        # true; drawing.c renders S_hodoor as '|', while
                        # S_vodoor renders as '-'.  This is display-symbol
                        # orientation, so do not invert it from glyph shape.
                        if snapshot.terrain_horizontal[y][x] != (char == "|"):
                            raise RuntimeError(f"public open-door orientation disagrees with native struct rm.horizontal at {(x, y)}: char={char!r}, horizontal={snapshot.terrain_horizontal[y][x]!r}")
                        open_door_controls += 1
                # The only competing contiguous-array interpretation would
                # map screen x to native x, rather than source x=x+1.  It
                # must be disproved by this *same pre-action* direct-pixel
                # control before coordinates can enter the oracle contract.
                wrong_cell = self._level_cells()[x * ROWNO + y]
                if glyph != int(wrong_cell.glyph):
                    wrong_coordinate_mismatches += 1
                checked += 1
        hero_x, hero_y = int(blstats[0]), int(blstats[1])
        if not (0 <= hero_x < OBS_COLNO and 0 <= hero_y < ROWNO):
            raise RuntimeError("public hero coordinate falls outside the NLE map plane")
        if not (snapshot.visibility_bits[hero_y][hero_x] & IN_SIGHT):
            raise RuntimeError("native FOV lacks IN_SIGHT at the public hero position")
        blindness_controls = 0
        if snapshot.vision_inputs is not None:
            if len(blstats) <= 25:
                raise RuntimeError("public NLE pre-action controls lack condition bits for native blindness validation")
            blind_mask = getattr(nethack, "BL_MASK_BLIND", None)
            if type(blind_mask) is not int or blind_mask <= 0:
                raise RuntimeError("public NLE binding lacks the pinned blindness condition mask")
            native_blind = snapshot.vision_inputs["blindness"]["blind"]
            public_blind = bool(int(blstats[25]) & int(blind_mask))
            if native_blind is not public_blind:
                raise RuntimeError("native Blind macro disagrees with public NLE condition bit")
            blindness_controls = 1
        if checked == 0:
            raise RuntimeError("no direct static public map cells were available to validate native coordinate mapping")
        if wrong_coordinate_mismatches == 0:
            raise RuntimeError("direct public controls did not disambiguate native x=screen_x+1 from x=screen_x")
        return {
            "direct_static_glyph_controls": checked,
            "wrong_x_coordinate_mismatches": wrong_coordinate_mismatches,
            "hero_in_sight_controls": 1,
            "blindness_condition_controls": blindness_controls,
            "closed_door_glyph_controls": closed_door_controls,
            "open_door_glyph_controls": open_door_controls,
        }
