"""Portable reset-only static map substrate for NetHack dlvl-1.

The native map/FOV reader exposes the complete level at reset, while the
public observation exposes only the currently rendered/remembered cells.  A
gold implementation needs the hidden static topology for actor pathing and
later visibility, but must not use a future frame or native pointer.  This
module serializes the immutable reset terrain type, door flags, and door
orientation plus explicitly validated optional lighting and reset blocker
inputs into a pointer-free task projection. Rendering still starts from the
causal public level dump; consumers opt into the hidden substrate for
internal simulation only.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from scripts.nle_native_entities import EXPECTED_BINARY_SHA256, SOURCE_COMMIT
from scripts.oracle_tape import sha256_json


SCHEMA = "gamebench.nethack.authoritative_reset_map.v1"
RESET_BOUNDARY = {"kind": "reset", "action_step": 0, "before_action_step": 1}
VIEW_HEIGHT = 21
VIEW_WIDTH = 79
MAX_TERRAIN_TYPE = 35
MAX_TERRAIN_FLAGS = 31
NLE_GLYPH_CMAP_OFF = 2359
D_ISOPEN = 2
D_CLOSED = 4
D_LOCKED = 8
D_TRAPPED = 16
LA_DOWN = 2

# NetHack 3.6.6 rm.h terrain enum -> the static cmap family used by
# back_to_glyph().  This is a rendering aid for cells whose map substrate is
# already source-owned; it does not identify entities or object stacks.
NATIVE_TERRAIN_CHARS = {
    0: " ", 1: "|", 2: "-", 3: "-", 4: "-", 5: "-", 6: "-", 7: "-", 8: "-", 9: "-",
    10: "|", 11: "|", 12: "#", 13: "#", 14: " ", 15: " ", 16: "}", 17: "}",
    18: "}", 19: "#", 20: "}", 21: "#", 22: "+", 23: "#", 24: ".", 25: ".",
    26: ".", 27: "{", 28: "\\", 29: "#", 30: "|", 31: "_", 32: ".", 33: ".",
    34: " ", 35: "#",
}
NATIVE_CMAP_BY_TERRAIN = {
    0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9,
    10: 10, 11: 11, 12: 7, 13: 18, 14: 12, 15: 21, 16: 32, 17: 32,
    18: 41, 19: 35, 20: 34, 21: 17, 23: 21, 24: 19, 25: 19, 26: 25,
    27: 31, 28: 29, 29: 30, 30: 28, 31: 27, 32: 33, 33: 35, 34: 39,
    35: 40,
}

_EXPECTED_KEYS = {
    "schema",
    "capture_boundary",
    "source_commit",
    "native_binary_sha256",
    "coordinate_contract",
    "terrain_type",
    "terrain_flags",
    "terrain_horizontal",
    "projection_sha256",
}
_OPTIONAL_KEYS = {"terrain_lit", "terrain_waslit", "night_vision_range", "dynamic_vision_blockers", "level_flags", "semantic_level_flags"}
_OPTIONAL_KEYS |= {"engravings", "semantic_engraving_contract", "traps", "semantic_search_contract"}
_LEVEL_FLAGS_KEYS = frozenset({
    "nfountains", "nsinks", "has_shop", "has_vault", "has_zoo", "has_court",
    "has_morgue", "has_beehive", "has_barracks", "has_temple", "has_swamp",
    "noteleport", "hardfloor", "nommap", "hero_memory", "shortsighted",
    "graveyard", "sokoban_rules", "is_maze_lev", "is_cavernous_lev", "arboreal",
    "wizard_bones", "corrmaze",
})
_LEVEL_FLAGS_ABI = (8, 40368, 40360, 0, 1)
_TRAP_ABI = (24, 0, 8, 9, 10, 12, 14, 16)
_FORBIDDEN_KEYS = {
    "native_map_fov_state",
    "native_pre_action_evidence",
    "pre_action_records",
    "future_observation",
    "future_frames",
    "hydrated_from_step",
    "record_sha256",
    "native_binary_sha256_bytes",
}


def _rows(value: Any, *, item_type: type, name: str) -> list[list[Any]]:
    if not isinstance(value, list) or len(value) != VIEW_HEIGHT:
        raise ValueError(f"reset map {name} must be a 21-row array")
    result: list[list[Any]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != VIEW_WIDTH or any(type(cell) is not item_type for cell in row):
            raise ValueError(f"reset map {name} must be a 21x79 {item_type.__name__} plane")
        result.append(deepcopy(row))
    return result


def _find_forbidden(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        found: list[str] = []
        for key, nested in value.items():
            if key in _FORBIDDEN_KEYS:
                found.append(f"{path}.{key}")
            found.extend(_find_forbidden(nested, f"{path}.{key}"))
        return found
    if isinstance(value, list):
        return [bad for index, nested in enumerate(value) for bad in _find_forbidden(nested, f"{path}[{index}]")]
    return []


def _portable_dynamic_blockers(source: Any) -> dict[str, Any]:
    """Copy only the reset-bound ``vision.c::does_block`` inputs.

    The native reader has already proved the complete boulder/mimic planes
    and their source identities.  Keeping this as a separate optional map
    extension prevents a rendered glyph or a later sidecar frame from
    becoming a blocker by inference.
    """

    if not isinstance(source, dict):
        raise ValueError("reset map dynamic_vision_blockers must be an object")
    planes: dict[str, list[list[bool]]] = {}
    for name in ("boulder", "visible_mimic", "effective"):
        planes[name] = _rows(source.get(name), item_type=bool, name=f"dynamic_vision_blockers.{name}")
    if any(
        planes["effective"][y][x] is not bool(planes["boulder"][y][x] or planes["visible_mimic"][y][x])
        for y in range(VIEW_HEIGHT)
        for x in range(VIEW_WIDTH)
    ):
        raise ValueError("reset map dynamic blocker effective plane is not the boulder/mimic union")
    records = source.get("records")
    if not isinstance(records, list):
        raise ValueError("reset map dynamic_vision_blockers.records must be a list")
    copied: list[dict[str, Any]] = []
    claimed: set[tuple[str, int, int]] = set()
    for record in records:
        if not isinstance(record, dict) or record.get("kind") not in {"boulder", "mimic"}:
            raise ValueError("reset map dynamic blocker record kind is invalid")
        kind, x, y, native_x = record.get("kind"), record.get("x"), record.get("y"), record.get("native_x")
        if any(type(value) is not int for value in (x, y, native_x)) or not (0 <= x < VIEW_WIDTH and 0 <= y < VIEW_HEIGHT and native_x == x + 1):
            raise ValueError("reset map dynamic blocker record coordinate is invalid")
        key = (str(kind), x, y)
        if key in claimed:
            raise ValueError("reset map dynamic blocker record repeats a cell")
        claimed.add(key)
        if kind == "boulder":
            required = ("object_id", "object_type")
        else:
            required = ("monster_id", "appearance_type", "mappearance", "invisible", "see_invisible")
        if any(name not in record for name in required):
            raise ValueError(f"reset map dynamic {kind} blocker record is incomplete")
        if kind == "boulder":
            if any(type(record.get(name)) is not int or record[name] <= 0 for name in required):
                raise ValueError("reset map boulder identity is invalid")
        elif (
            type(record.get("monster_id")) is not int or record["monster_id"] <= 0
            or any(type(record.get(name)) is not int or record[name] < 0 for name in ("appearance_type", "mappearance"))
            or any(type(record.get(name)) is not bool for name in ("invisible", "see_invisible"))
        ):
            raise ValueError("reset map mimic identity is invalid")
        copied.append({key: deepcopy(record[key]) for key in ("kind", "x", "y", "native_x", *required)})
    for kind, plane_name in (("boulder", "boulder"), ("mimic", "visible_mimic")):
        plane_cells = {(x, y) for y in range(VIEW_HEIGHT) for x in range(VIEW_WIDTH) if planes[plane_name][y][x]}
        record_cells = {(record["x"], record["y"]) for record in copied if record["kind"] == kind}
        if plane_cells != record_cells:
            raise ValueError(f"reset map dynamic {kind} records do not cover their plane")
    return {**planes, "records": copied}


def portable_reset_map_projection(source: dict[str, Any]) -> dict[str, Any]:
    """Sanitize one exact source map export captured at reset."""

    if not isinstance(source, dict) or source.get("schema") != "gamebench.nethack.native_map_fov_snapshot.v1":
        raise ValueError("portable reset map requires an exact native map/FOV snapshot")
    if source.get("binary_sha256") != EXPECTED_BINARY_SHA256:
        raise ValueError("portable reset map requires the pinned native binary")
    if source.get("source_export_eligible") is not True or source.get("gold_implementation_eligible") is not False:
        raise ValueError("portable reset map requires the source-only map contract")
    projection = {
        "schema": SCHEMA,
        "capture_boundary": deepcopy(RESET_BOUNDARY),
        "source_commit": SOURCE_COMMIT,
        "native_binary_sha256": EXPECTED_BINARY_SHA256,
        "coordinate_contract": "screen [y][x] maps to native level.locations[x+1][y]; native x=0 is excluded",
        "terrain_type": _rows(source.get("full_map_terrain"), item_type=int, name="terrain_type"),
        "terrain_flags": _rows(source.get("full_map_terrain_flags"), item_type=int, name="terrain_flags"),
        "terrain_horizontal": _rows(source.get("full_map_terrain_horizontal"), item_type=bool, name="terrain_horizontal"),
    }
    lighting = source.get("lighting")
    vision_inputs = source.get("vision_decision_inputs")
    hero_inputs = vision_inputs.get("hero") if isinstance(vision_inputs, dict) else None
    if isinstance(lighting, dict) and isinstance(hero_inputs, dict):
        # Static rm.lit/waslit and the reset hero's night-vision radius are
        # immutable reset inputs.  Mobile light sources, temporary lighting,
        # x-ray, blindness, and dynamic blockers remain intentionally absent.
        projection["terrain_lit"] = _rows(lighting.get("static_lit"), item_type=bool, name="terrain_lit")
        projection["terrain_waslit"] = _rows(lighting.get("remembered_lit"), item_type=bool, name="terrain_waslit")
        night_vision_range = hero_inputs.get("night_vision_range")
        if type(night_vision_range) is not int or not -1 <= night_vision_range <= 15:
            raise ValueError("portable reset map night vision range is outside the pinned source range")
        projection["night_vision_range"] = int(night_vision_range)
    if "dynamic_vision_blockers" in source:
        projection["dynamic_vision_blockers"] = _portable_dynamic_blockers(source["dynamic_vision_blockers"])
    has_engravings = "engravings" in source
    has_engraving_contract = "semantic_engraving_contract" in source
    if has_engravings != has_engraving_contract:
        raise ValueError("portable reset map engraving extension must include both fields")
    if has_engravings:
        # The source reader has already proved the linked-list ABI.  Keep a
        # pointer-free copy in the reset substrate and revalidate its scalar
        # shape below so a rewritten map cannot smuggle native addresses.
        projection["engravings"] = deepcopy(source["engravings"])
        projection["semantic_engraving_contract"] = deepcopy(source["semantic_engraving_contract"])
    has_traps = "traps" in source
    has_search_contract = "semantic_search_contract" in source
    if has_traps != has_search_contract:
        raise ValueError("portable reset map search-surface extension must include both traps and semantic_search_contract")
    if has_traps:
        records = source.get("traps")
        contract = source.get("semantic_search_contract")
        if not isinstance(records, list) or len(records) > 4096:
            raise ValueError("portable reset map traps are not a bounded list")
        if (
            not isinstance(contract, dict)
            or contract.get("source_only") is not True
            or contract.get("gold_implementation_eligible") is not False
            or contract.get("source") != "detect.c::dosearch0; trap.h::struct trap/ftrap"
            or tuple(contract.get("abi", {}).get(name) for name in ("sizeof", "ntrap", "tx", "ty", "dst", "launch", "bitfields", "union")) != _TRAP_ABI
        ):
            raise ValueError("portable reset map search-surface contract is not source-pinned")
        copied: list[dict[str, Any]] = []
        seen: set[tuple[int, int]] = set()
        for record in records:
            required = {"native_x", "x", "y", "trap_type", "tseen", "once", "madeby_u"}
            if not isinstance(record, dict) or set(record) != required:
                raise ValueError("portable reset map trap record is incomplete")
            native_x, x, y, trap_type = (record[name] for name in ("native_x", "x", "y", "trap_type"))
            if (
                type(native_x) is not int or not 1 <= native_x < 80
                or type(x) is not int or x != native_x - 1
                or type(y) is not int or not 0 <= y < 21
                or type(trap_type) is not int or not 1 <= trap_type <= 22
                or any(type(record[name]) is not bool for name in ("tseen", "once", "madeby_u"))
            ):
                raise ValueError("portable reset map trap record is malformed")
            key = (native_x, y)
            if key in seen:
                raise ValueError("portable reset map trap coordinates are not unique")
            seen.add(key)
            copied.append(deepcopy(record))
        projection["traps"] = copied
        projection["semantic_search_contract"] = deepcopy(contract)
    has_level_flags = "level_flags" in source
    has_level_flags_contract = "semantic_level_flags" in source
    if has_level_flags != has_level_flags_contract:
        raise ValueError("portable reset map level_flags extension must include both fields")
    if has_level_flags:
        flags = source.get("level_flags")
        contract = source.get("semantic_level_flags")
        required = _LEVEL_FLAGS_KEYS
        if not isinstance(flags, dict) or set(flags) != required:
            raise ValueError("portable reset map level_flags are incomplete")
        if type(flags["nfountains"]) is not int or not 0 <= flags["nfountains"] <= 255 or type(flags["nsinks"]) is not int or not 0 <= flags["nsinks"] <= 255:
            raise ValueError("portable reset map level_flags counters are malformed")
        if any(type(flags[name]) is not bool for name in required - {"nfountains", "nsinks"}):
            raise ValueError("portable reset map level_flags bitfields are malformed")
        abi = contract.get("abi") if isinstance(contract, dict) else None
        if (
            not isinstance(contract, dict)
            or contract.get("source_only") is not True
            or contract.get("gold_implementation_eligible") is not False
            or not isinstance(abi, dict)
            or set(abi) != {"sizeof_levelflags", "sizeof_dlevel_t", "flags_offset", "nfountains_offset", "nsinks_offset"}
            or tuple(abi.get(name) for name in ("sizeof_levelflags", "sizeof_dlevel_t", "flags_offset", "nfountains_offset", "nsinks_offset")) != _LEVEL_FLAGS_ABI
        ):
            raise ValueError("portable reset map level_flags lack source-only contract")
        projection["level_flags"] = deepcopy(flags)
        projection["semantic_level_flags"] = deepcopy(contract)
    if any(not 0 <= cell <= MAX_TERRAIN_TYPE for row in projection["terrain_type"] for cell in row):
        raise ValueError("portable reset map terrain type is outside the pinned enum")
    if any(not 0 <= cell <= MAX_TERRAIN_FLAGS for row in projection["terrain_flags"] for cell in row):
        raise ValueError("portable reset map terrain flags are outside the pinned five-bit range")
    projection["projection_sha256"] = sha256_json(projection)
    return projection


def validate_portable_reset_map_projection(projection: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(projection, dict):
        return ["authoritative reset map must be an object"]
    forbidden = _find_forbidden(projection)
    if forbidden:
        failures.append("authoritative reset map contains prohibited receipt/pre-action/future fields: " + ", ".join(forbidden))
    actual_keys = set(projection)
    if not (_EXPECTED_KEYS <= actual_keys <= (_EXPECTED_KEYS | _OPTIONAL_KEYS)) or projection.get("schema") != SCHEMA:
        failures.append("authoritative reset map schema/field contract mismatch")
    elif ({"terrain_lit", "terrain_waslit", "night_vision_range"} & actual_keys) and ({"terrain_lit", "terrain_waslit", "night_vision_range"} & actual_keys) != {"terrain_lit", "terrain_waslit", "night_vision_range"}:
        failures.append("authoritative reset map lighting extension must be complete")
    if projection.get("capture_boundary") != RESET_BOUNDARY:
        failures.append("authoritative reset map is not reset-bound")
    if projection.get("source_commit") != SOURCE_COMMIT or projection.get("native_binary_sha256") != EXPECTED_BINARY_SHA256:
        failures.append("authoritative reset map source/binary identity mismatch")
    if projection.get("coordinate_contract") != "screen [y][x] maps to native level.locations[x+1][y]; native x=0 is excluded":
        failures.append("authoritative reset map coordinate contract mismatch")
    try:
        terrain = _rows(projection.get("terrain_type"), item_type=int, name="terrain_type")
        flags = _rows(projection.get("terrain_flags"), item_type=int, name="terrain_flags")
        horizontal = _rows(projection.get("terrain_horizontal"), item_type=bool, name="terrain_horizontal")
        for name in ("terrain_lit", "terrain_waslit"):
            if name in projection:
                _rows(projection.get(name), item_type=bool, name=name)
        if "night_vision_range" in projection and (type(projection["night_vision_range"]) is not int or not -1 <= projection["night_vision_range"] <= 15):
            failures.append("authoritative reset map night vision range is outside the pinned source range")
        if "dynamic_vision_blockers" in projection:
            try:
                _portable_dynamic_blockers(projection["dynamic_vision_blockers"])
            except ValueError as error:
                failures.append(str(error))
        has_engravings = "engravings" in projection
        has_engraving_contract = "semantic_engraving_contract" in projection
        if has_engravings != has_engraving_contract:
            failures.append("authoritative reset map engraving extension must include both fields")
        if has_engravings:
            contract = projection.get("semantic_engraving_contract")
            expected_abi = {"sizeof": 40, "next": 0, "text": 8, "x": 16, "y": 17, "length": 20, "time": 24, "type": 32}
            if (
                not isinstance(contract, dict)
                or contract.get("source") != "engrave.c::head_engr/struct engr; monmove.c::wipe_engr_at"
                or contract.get("source_only") is not True
                or contract.get("gold_implementation_eligible") is not False
                or contract.get("abi") != expected_abi
            ):
                failures.append("authoritative reset map engraving source-only ABI contract is missing")
            records = projection.get("engravings")
            if not isinstance(records, list) or len(records) > 8192:
                failures.append("authoritative reset map engravings must be a bounded list")
            else:
                seen: set[tuple[int, int]] = set()
                for record in records:
                    if not isinstance(record, dict) or set(record) != {"native_x", "y", "engr_type", "engr_time", "engr_lth", "text"}:
                        failures.append("authoritative reset map engraving record is malformed")
                        continue
                    x, y, kind = record.get("native_x"), record.get("y"), record.get("engr_type")
                    length, text = record.get("engr_lth"), record.get("text")
                    if type(x) is not int or not 1 <= x < 80 or type(y) is not int or not 0 <= y < 21 or type(kind) is not int or not 1 <= kind <= 6:
                        failures.append("authoritative reset map engraving coordinate/type is malformed")
                    if (x, y) in seen:
                        failures.append("authoritative reset map engraving coordinates are not unique")
                    seen.add((x, y))
                    if type(record.get("engr_time")) is not int or type(length) is not int or not 1 <= length <= 256 or not isinstance(text, str) or len(text.encode("utf-8")) + 1 != length:
                        failures.append("authoritative reset map engraving text/length is malformed")
        has_traps = "traps" in projection
        has_search_contract = "semantic_search_contract" in projection
        if has_traps != has_search_contract:
            failures.append("authoritative reset map search-surface extension must include both fields")
        if has_traps:
            contract = projection.get("semantic_search_contract")
            expected_abi = {"sizeof": 24, "ntrap": 0, "tx": 8, "ty": 9, "dst": 10, "launch": 12, "bitfields": 14, "union": 16}
            if (
                not isinstance(contract, dict)
                or contract.get("source") != "detect.c::dosearch0; trap.h::struct trap/ftrap"
                or contract.get("source_only") is not True
                or contract.get("gold_implementation_eligible") is not False
                or contract.get("abi") != expected_abi
            ):
                failures.append("authoritative reset map search-surface source-only ABI contract is missing")
            records = projection.get("traps")
            if not isinstance(records, list) or len(records) > 4096:
                failures.append("authoritative reset map traps must be a bounded list")
            else:
                seen: set[tuple[int, int]] = set()
                for record in records:
                    required = {"native_x", "x", "y", "trap_type", "tseen", "once", "madeby_u"}
                    if not isinstance(record, dict) or set(record) != required:
                        failures.append("authoritative reset map trap record is malformed")
                        continue
                    native_x, x, y, trap_type = (record.get(name) for name in ("native_x", "x", "y", "trap_type"))
                    if (
                        type(native_x) is not int or not 1 <= native_x < 80
                        or type(x) is not int or x != native_x - 1
                        or type(y) is not int or not 0 <= y < 21
                        or type(trap_type) is not int or not 1 <= trap_type <= 22
                        or any(type(record.get(name)) is not bool for name in ("tseen", "once", "madeby_u"))
                    ):
                        failures.append("authoritative reset map trap coordinate/type/flags are malformed")
                    if (native_x, y) in seen:
                        failures.append("authoritative reset map trap coordinates are not unique")
                    seen.add((native_x, y))
        has_level_flags = "level_flags" in projection
        has_level_flags_contract = "semantic_level_flags" in projection
        if has_level_flags != has_level_flags_contract:
            failures.append("authoritative reset map level_flags extension must include both fields")
        if has_level_flags:
            level_flags = projection.get("level_flags")
            required = _LEVEL_FLAGS_KEYS
            if not isinstance(level_flags, dict) or set(level_flags) != required:
                failures.append("authoritative reset map level_flags are incomplete")
            elif (
                type(level_flags.get("nfountains")) is not int or not 0 <= level_flags["nfountains"] <= 255
                or type(level_flags.get("nsinks")) is not int or not 0 <= level_flags["nsinks"] <= 255
                or any(type(level_flags.get(name)) is not bool for name in required - {"nfountains", "nsinks"})
            ):
                failures.append("authoritative reset map level_flags values are malformed")
            contract = projection.get("semantic_level_flags")
            abi = contract.get("abi") if isinstance(contract, dict) else None
            if (
                not isinstance(contract, dict)
                or contract.get("source_only") is not True
                or contract.get("gold_implementation_eligible") is not False
                or not isinstance(abi, dict)
                or set(abi) != {"sizeof_levelflags", "sizeof_dlevel_t", "flags_offset", "nfountains_offset", "nsinks_offset"}
                or tuple(abi.get(name) for name in ("sizeof_levelflags", "sizeof_dlevel_t", "flags_offset", "nfountains_offset", "nsinks_offset")) != _LEVEL_FLAGS_ABI
            ):
                failures.append("authoritative reset map level_flags source-only contract is missing")
        if any(not 0 <= cell <= MAX_TERRAIN_TYPE for row in terrain for cell in row):
            failures.append("authoritative reset map terrain type is outside the pinned enum")
        if any(not 0 <= cell <= MAX_TERRAIN_FLAGS for row in flags for cell in row):
            failures.append("authoritative reset map terrain flags are outside the pinned five-bit range")
        del horizontal
    except ValueError as error:
        failures.append(str(error))
    payload = {key: value for key, value in projection.items() if key != "projection_sha256"}
    if projection.get("projection_sha256") != sha256_json(payload):
        failures.append("authoritative reset map projection digest mismatch")
    return failures


def reset_map_cell(projection: dict[str, Any], x: int, y: int) -> tuple[int, int, bool]:
    """Return the immutable source type/flags/orientation for one cell."""

    failures = validate_portable_reset_map_projection(projection)
    if failures:
        raise ValueError("invalid authoritative reset map: " + "; ".join(failures))
    if type(x) is not int or type(y) is not int or not (0 <= x < VIEW_WIDTH and 0 <= y < VIEW_HEIGHT):
        raise ValueError("reset map cell is outside the screen crop")
    return (
        int(projection["terrain_type"][y][x]),
        int(projection["terrain_flags"][y][x]),
        bool(projection["terrain_horizontal"][y][x]),
    )


def reset_map_surface(projection: dict[str, Any], x: int, y: int) -> tuple[str, int]:
    """Return the source cmap character/glyph for one static reset cell.

    The result is intentionally limited to terrain presentation.  It never
    carries lighting, memory, entity, object, or future-frame state.
    """

    failures = validate_portable_reset_map_projection(projection)
    if failures:
        raise ValueError("invalid authoritative reset map: " + "; ".join(failures))
    if type(x) is not int or type(y) is not int or not (0 <= x < VIEW_WIDTH and 0 <= y < VIEW_HEIGHT):
        raise ValueError("reset map cell is outside the screen crop")
    return _reset_map_surface_unchecked(projection, x, y)


def _reset_map_surface_unchecked(projection: dict[str, Any], x: int, y: int) -> tuple[str, int]:
    """Fast cell lookup for a projection already validated at reset/checkpoint."""

    terrain_type, flags, horizontal = (
        int(projection["terrain_type"][y][x]),
        int(projection["terrain_flags"][y][x]),
        bool(projection["terrain_horizontal"][y][x]),
    )
    if terrain_type == 25:  # STAIRS; rm.flags aliases ladder and LA_DOWN selects '>'
        cmap = 24 if flags & LA_DOWN else 23
        return (">" if flags & LA_DOWN else "<"), NLE_GLYPH_CMAP_OFF + cmap
    if terrain_type == 26:  # LADDER; same direction bit, distinct cmap family
        cmap = 26 if flags & LA_DOWN else 25
        return (">" if flags & LA_DOWN else "<"), NLE_GLYPH_CMAP_OFF + cmap
    if terrain_type != 22:  # DOOR
        cmap = NATIVE_CMAP_BY_TERRAIN.get(terrain_type, 0)
        return NATIVE_TERRAIN_CHARS.get(terrain_type, " "), NLE_GLYPH_CMAP_OFF + cmap
    if flags & (D_CLOSED | D_LOCKED | D_TRAPPED):
        return "+", NLE_GLYPH_CMAP_OFF + (15 if horizontal else 16)
    if flags & D_ISOPEN:
        # NetHack's names are view-oriented: S_hodoor renders ``|`` and
        # S_vodoor renders ``-`` (display.c::back_to_glyph).
        return ("|" if horizontal else "-"), NLE_GLYPH_CMAP_OFF + (14 if horizontal else 13)
    return ".", NLE_GLYPH_CMAP_OFF + 12
