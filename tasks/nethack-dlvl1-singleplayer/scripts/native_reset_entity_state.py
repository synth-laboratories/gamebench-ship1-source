"""Reset-only, fail-closed dynamic-entity source contract for NLE.

This is deliberately *not* another pre-action sidecar.  The state bytes are
copied exactly once, immediately after ``env.reset()`` and before action one.
They are later bound to the completed level dump and action tape by digests;
that late binding adds no native state.  A separately sanitized portable
projection is embedded in the level dump and is the *only* reset entity state
gold may consume.  The native receipt itself remains source evidence and is
forbidden as a gold/checkpoint, score, pre-action-sidecar, or future-frame
input.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from scripts.oracle_tape import oracle_identity, sha256_json


SIDECAR_FILE = "native_reset_entity_state.json"
SCHEMA = "gamebench.nethack.native_reset_entity_scheduler_state.v1"
PORTABLE_PROJECTION_SCHEMA = "gamebench.nethack.authoritative_reset_entities.v1"
RESET_BOUNDARY = {"kind": "reset", "action_step": 0, "before_action_step": 1}
USAGE_POLICY = {
    "classification": "read_only_authoritative_reset_source_evidence",
    "captured_at_reset_only": True,
    "forbidden_uses": [
        "future_observation_hydration",
        "pre_action_sidecar_hydration",
        "native_receipt_level_dump_hydration",
        "native_receipt_gold_runtime_input",
        "checkpoint_state_input",
        "conformance_denominator",
    ],
}
RNG_POLICY = {
    "status": "separate_portable_reset_contract",
    "reason": "A complete reset-only ISAAC64 projection is embedded separately in the level dump; this entity receipt never accepts later RNG sidecars.",
}


def _without_digest(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "record_sha256"}


def capture_reset_state(exporters: Any, observation: dict[str, Any]) -> dict[str, Any]:
    """Copy state at the sole permitted native boundary: reset, before input.

    ``NativePreActionExporters.export`` is used only as a read-only ABI and
    public-plane tripwire.  A complete reset map/FOV export is sanitized into
    a separate immutable map projection; all other map/FOV state is discarded.
    Its exact
    reset RNG snapshot is immediately transformed into a separately named,
    portable task projection; it is never retained as an oracle sidecar.
    """

    exports, controls = exporters.export(observation)
    entities = exports.get("entities")
    player = exports.get("player")
    if not isinstance(entities, dict) or not isinstance(player, dict):
        raise RuntimeError("native reset contract requires entity and player exports")
    from scripts.portable_reset_rng import portable_reset_rng_projection

    rng_snapshot = exports.get("rng")
    portable_rng = portable_reset_rng_projection(rng_snapshot)
    capture = {
        "capture_boundary": deepcopy(RESET_BOUNDARY),
        "captured_at_reset_only": True,
        "state": {"entities": deepcopy(entities), "player": deepcopy(player)},
        "controls": {"entities": deepcopy(controls.get("entities")), "player": deepcopy(controls.get("player"))},
        "rng": deepcopy(RNG_POLICY),
        "portable_reset_rng": portable_rng,
    }
    # The map reader is optional for historical/fake exporters.  Only a full
    # source-eligible reset snapshot can cross into the portable projection;
    # partial map/FOV receipts remain diagnostic evidence and are never
    # silently accepted as topology.
    map_fov = exports.get("map_fov")
    if isinstance(map_fov, dict) and all(
        key in map_fov for key in ("schema", "full_map_terrain", "full_map_terrain_flags", "full_map_terrain_horizontal")
    ):
        from scripts.portable_reset_map import portable_reset_map_projection

        capture["portable_reset_map"] = portable_reset_map_projection(map_fov)
    return capture


def portable_reset_projection(capture: dict[str, Any]) -> dict[str, Any]:
    """Derive the only reset entity data that may enter a task level dump.

    Values are JSON scalars/arrays copied from the pinned source export: no
    addresses, callbacks, native binary objects, RNG context, or future frame
    is represented.  This projection is intentionally complete enough for
    deterministic scheduler work (instance identity, underlay, movement,
    ordered queue, path/target/status) while the native receipt remains merely
    an attestation artifact.
    """

    if not isinstance(capture, dict) or capture.get("capture_boundary") != RESET_BOUNDARY or capture.get("captured_at_reset_only") is not True:
        raise ValueError("portable reset projection requires a reset-before-action-one capture")
    state = capture.get("state")
    if not isinstance(state, dict) or set(state) != {"entities", "player"}:
        raise ValueError("portable reset projection requires entity and player source state")
    entities = state.get("entities")
    player = state.get("player")
    if not isinstance(entities, dict) or not isinstance(player, dict):
        raise ValueError("portable reset projection requires object exports")
    entity_list = entities.get("entities")
    turn_queue = entities.get("turn_queue")
    object_stacks = entities.get("object_stacks", [])
    source_turn = entities.get("source_turn")
    player_state = player.get("player")
    equipment = player_state.get("equipment") if isinstance(player_state, dict) else None
    player_inventory = equipment.get("inventory") if isinstance(equipment, dict) else None
    player_turn = player.get("source_turn")
    coordinates = player_state.get("coordinates") if isinstance(player_state, dict) else None
    if not isinstance(entity_list, list) or not isinstance(turn_queue, list) or not isinstance(object_stacks, list) or not isinstance(source_turn, dict) or not isinstance(coordinates, dict):
        raise ValueError("portable reset projection requires complete entity queue and player coordinates")
    x, y = coordinates.get("nle_x"), coordinates.get("nle_y")
    if type(x) is not int or type(y) is not int or type(player_turn) is not int:
        raise ValueError("portable reset projection has invalid player reset coordinates or turn")
    projection = {
        "schema": PORTABLE_PROJECTION_SCHEMA,
        "capture_boundary": deepcopy(RESET_BOUNDARY),
        "source_state_sha256": sha256_json(state),
        "source_turn": deepcopy(source_turn),
        "turn_queue": deepcopy(turn_queue),
        "entities": deepcopy(entity_list),
        "player": {"x": x, "y": y, "source_turn": player_turn},
    }
    if "object_stacks" in entities:
        projection["object_stacks"] = deepcopy(object_stacks)
    # ``dog_goal`` performs a source-ordered hero-inventory ``dogfood`` scan
    # while deciding whether a tame pet should follow the player.  This is a
    # reset-owned object surface only: later pickup/drop/equipment mutations
    # remain outside the portable scheduler contract.
    if isinstance(player_inventory, list):
        projection["player_inventory"] = deepcopy(player_inventory)
    projection["projection_sha256"] = sha256_json({key: value for key, value in projection.items() if key != "projection_sha256"})
    return projection


def portable_reset_rng_projection_from_capture(capture: dict[str, Any]) -> dict[str, Any]:
    """Return the sealed reset RNG task input captured beside entity state."""

    value = capture.get("portable_reset_rng") if isinstance(capture, dict) else None
    from scripts.portable_reset_rng import validate_portable_reset_rng_projection

    failures = validate_portable_reset_rng_projection(value)
    if failures:
        raise ValueError("reset capture has invalid portable reset RNG: " + "; ".join(failures))
    return deepcopy(value)


def validate_portable_reset_projection(projection: Any, *, reset_projection: dict[str, Any]) -> list[str]:
    """Validate level-dump task data without touching a native receipt."""

    if not isinstance(projection, dict):
        return ["authoritative reset entities must be an object"]
    expected_keys = {"schema", "capture_boundary", "source_state_sha256", "source_turn", "turn_queue", "entities", "player", "projection_sha256"}
    optional_keys = {"object_stacks", "player_inventory"}
    failures: list[str] = []
    forbidden_nested = {"native_pre_action_evidence", "pre_action_records", "future_observation", "future_frames", "hydrated_from_step", "record_sha256", "native_binary_sha256"}

    def find_forbidden(value: Any, path: str = "$") -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, nested in value.items():
                child = f"{path}.{key}"
                if key in forbidden_nested:
                    found.append(child)
                found.extend(find_forbidden(nested, child))
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                found.extend(find_forbidden(nested, f"{path}[{index}]"))
        return found

    future_paths = find_forbidden(projection)
    if future_paths:
        failures.append("authoritative reset entities contains prohibited receipt/pre-action/future fields: " + ", ".join(future_paths))
    if not (expected_keys <= set(projection) <= expected_keys | optional_keys) or projection.get("schema") != PORTABLE_PROJECTION_SCHEMA:
        failures.append("authoritative reset entities schema/field contract mismatch")
    if "object_stacks" in projection:
        stacks = projection.get("object_stacks")
        if not isinstance(stacks, list):
            failures.append("authoritative reset entities object_stacks must be a list")
        else:
            for index, stack in enumerate(stacks):
                if not isinstance(stack, dict) or type(stack.get("x")) is not int or type(stack.get("y")) is not int or not isinstance(stack.get("objects"), list):
                    failures.append(f"authoritative reset entities object_stacks[{index}] is malformed")
                    continue
                for object_index, item in enumerate(stack["objects"]):
                    if not isinstance(item, dict):
                        failures.append(f"authoritative reset entities object_stacks[{index}].objects[{object_index}] is malformed")
                        continue
                    display_keys = {
                        "display_mode", "display_object_type", "display_glyph", "display_class", "display_color",
                    }
                    present = display_keys & set(item)
                    if not present:
                        continue
                    if present != display_keys:
                        failures.append(f"authoritative reset entities object_stacks[{index}].objects[{object_index}] has partial display contract")
                        continue
                    if item.get("display_mode") not in {"normal", "unsupported_special_object"}:
                        failures.append(f"authoritative reset entities object_stacks[{index}].objects[{object_index}] has invalid display mode")
                    display_type = item.get("display_object_type")
                    display_glyph = item.get("display_glyph")
                    display_class = item.get("display_class")
                    display_color = item.get("display_color")
                    if type(display_type) is not int or not 0 <= display_type < 453:
                        failures.append(f"authoritative reset entities object_stacks[{index}].objects[{object_index}] has invalid display object type")
                    if type(display_glyph) is not int or (
                        type(display_type) is int and display_glyph != 1906 + display_type
                    ) or type(display_type) is not int:
                        failures.append(f"authoritative reset entities object_stacks[{index}].objects[{object_index}] has invalid display glyph")
                    if type(display_class) is not int or not 0 <= display_class <= 17:
                        failures.append(f"authoritative reset entities object_stacks[{index}].objects[{object_index}] has invalid display class")
                    if type(display_color) is not int or not 0 <= display_color <= 15:
                        failures.append(f"authoritative reset entities object_stacks[{index}].objects[{object_index}] has invalid display color")
    if "player_inventory" in projection:
        inventory = projection.get("player_inventory")
        if not isinstance(inventory, list):
            failures.append("authoritative reset entities player_inventory must be a list")
        else:
            seen_ids: set[int] = set()
            seen_letters: set[str] = set()
            required = ("object_id", "object_type", "object_class", "inventory_letter", "quantity", "spe", "artifact", "worn_mask")
            for index, item in enumerate(inventory):
                if not isinstance(item, dict) or any(type(item.get(key)) is not int for key in required if key != "inventory_letter"):
                    failures.append(f"authoritative reset entities player_inventory[{index}] is malformed")
                    continue
                if not isinstance(item.get("inventory_letter"), str) or len(item["inventory_letter"]) != 1:
                    failures.append(f"authoritative reset entities player_inventory[{index}] has invalid inventory letter")
                if int(item.get("object_id", 0)) <= 0 or int(item.get("quantity", 0)) <= 0:
                    failures.append(f"authoritative reset entities player_inventory[{index}] has invalid identity or quantity")
                if int(item.get("object_id", 0)) in seen_ids or item.get("inventory_letter") in seen_letters:
                    failures.append(f"authoritative reset entities player_inventory[{index}] is not unique")
                seen_ids.add(int(item.get("object_id", 0)))
                seen_letters.add(str(item.get("inventory_letter", "")))
    if projection.get("capture_boundary") != RESET_BOUNDARY:
        failures.append("authoritative reset entities is not reset-bound")
    payload = {key: value for key, value in projection.items() if key != "projection_sha256"}
    if not isinstance(projection.get("source_state_sha256"), str) or not projection.get("source_state_sha256"):
        failures.append("authoritative reset entities lacks source-state provenance digest")
    if projection.get("projection_sha256") != sha256_json(payload):
        failures.append("authoritative reset entities projection digest mismatch")
    source_turn = projection.get("source_turn")
    queue, entities = projection.get("turn_queue"), projection.get("entities")
    if not isinstance(source_turn, dict) or not isinstance(queue, list) or not isinstance(entities, list):
        failures.append("authoritative reset entities requires source turn, queue, and entity list")
    else:
        # Reuse the source ABI structural validator with a deliberately local
        # wrapper.  It validates every stable ID, exact underlay stack,
        # scheduler field, target/path/status shape, and queue relation.
        from scripts.nle_native_entities import validate_native_entity_record

        wrapped = {
            "schema": "gamebench.nethack.native_entity_snapshot.v1",
            "source_turn": source_turn,
            "turn_queue": queue,
            "entities": entities,
        }
        failures.extend(f"authoritative reset entities: {failure}" for failure in validate_native_entity_record(wrapped))
    player = projection.get("player")
    blstats = reset_projection.get("blstats") if isinstance(reset_projection, dict) else None
    if not isinstance(player, dict) or set(player) != {"x", "y", "source_turn"} or any(type(player.get(key)) is not int for key in ("x", "y", "source_turn")):
        failures.append("authoritative reset entities player contract mismatch")
    elif not isinstance(blstats, list) or len(blstats) <= 20 or any(type(blstats[index]) is not int for index in (0, 1, 20)):
        failures.append("authoritative reset entities cannot bind public reset player/time")
    elif (player["x"], player["y"], player["source_turn"]) != (blstats[0], blstats[1], blstats[20]):
        failures.append("authoritative reset entities player/time differs from reset projection")
    if isinstance(source_turn, dict) and isinstance(player, dict) and type(source_turn.get("moves")) is int and type(player.get("source_turn")) is int and source_turn["moves"] != player["source_turn"]:
        failures.append("authoritative reset entities entity/player turn mismatch")
    return failures


def record_from_reset_capture(
    capture: dict[str, Any],
    *,
    fixture_id: str,
    runtime: dict[str, Any],
    level_dump: dict[str, Any],
    actions: list[dict[str, Any]],
    reset_projection: dict[str, Any],
) -> dict[str, Any]:
    """Bind a prior reset capture to immutable tape inputs without reading NLE.

    The caller may invoke this only after serialising the action list and
    level dump.  It never accepts an observation or exporter, which makes a
    later pre-action/native frame structurally incapable of replacing reset
    state during finalization.
    """

    if not isinstance(capture, dict) or capture.get("capture_boundary") != RESET_BOUNDARY or capture.get("captured_at_reset_only") is not True:
        raise ValueError("reset entity state must originate at reset before action 1")
    state = capture.get("state")
    if not isinstance(state, dict) or set(state) != {"entities", "player"}:
        raise ValueError("reset entity state has an invalid source payload")
    entities = state.get("entities")
    player = state.get("player")
    if not isinstance(entities, dict) or not isinstance(player, dict):
        raise ValueError("reset entity state requires native entity and player exports")
    binary_sha256 = entities.get("binary_sha256")
    if not isinstance(binary_sha256, str) or not binary_sha256 or player.get("binary_sha256") != binary_sha256:
        raise ValueError("reset entity/player exports disagree on native binary identity")
    portable = level_dump.get("authoritative_reset_entities") if isinstance(level_dump, dict) else None
    expected_portable = portable_reset_projection(capture)
    if portable != expected_portable:
        raise ValueError("level dump authoritative reset entity projection does not exactly match the reset capture")
    from scripts.portable_reset_rng import validate_portable_reset_rng_projection
    portable_rng = level_dump.get("authoritative_reset_rng") if isinstance(level_dump, dict) else None
    captured_rng = capture.get("portable_reset_rng")
    # Historical entity-only receipts remain judgeable.  New live captures
    # always have both values and are bound byte-for-byte below.
    if captured_rng is not None or portable_rng is not None:
        rng_failures = validate_portable_reset_rng_projection(captured_rng)
        if rng_failures or portable_rng != captured_rng:
            raise ValueError("level dump authoritative reset RNG projection does not exactly match the reset capture")
    captured_map = capture.get("portable_reset_map")
    portable_map = level_dump.get("authoritative_reset_map") if isinstance(level_dump, dict) else None
    if captured_map is not None or portable_map is not None:
        from scripts.portable_reset_map import validate_portable_reset_map_projection

        map_failures = validate_portable_reset_map_projection(captured_map)
        if map_failures or portable_map != captured_map:
            raise ValueError("level dump authoritative reset map projection does not exactly match the reset capture")
    record = {
        "schema": SCHEMA,
        "fixture_id": fixture_id,
        "capture_boundary": deepcopy(RESET_BOUNDARY),
        "captured_at_reset_only": True,
        "state": deepcopy(state),
        "controls": deepcopy(capture.get("controls")),
        "rng": deepcopy(RNG_POLICY),
        "bindings": {
            "oracle_identity_sha256": sha256_json(oracle_identity()),
            "capture_runtime_sha256": sha256_json(runtime),
            "native_binary_sha256": binary_sha256,
            "level_dump_sha256": sha256_json(level_dump),
            "reset_projection_sha256": sha256_json(reset_projection),
            "actions_sha256": sha256_json(actions),
            "portable_projection_sha256": expected_portable["projection_sha256"],
        },
        "usage_policy": deepcopy(USAGE_POLICY),
    }
    if portable_rng is not None:
        record["bindings"]["portable_reset_rng_sha256"] = portable_rng["projection_sha256"]
    if captured_map is not None:
        record["bindings"]["portable_reset_map_sha256"] = captured_map["projection_sha256"]
    record["reset_source_state_sha256"] = sha256_json(record["state"])
    record["record_sha256"] = sha256_json(_without_digest(record))
    return record


def validate_reset_entity_state(
    record: dict[str, Any] | None,
    *,
    fixture_id: str,
    runtime: dict[str, Any] | None,
    level_dump: dict[str, Any],
    actions: list[dict[str, Any]],
    reset_projection: dict[str, Any],
    require_native: bool,
) -> list[str]:
    """Validate provenance and reset-only semantics; fail closed on all drift."""

    if record is None:
        return ["native reset entity state is required for this v2 capture"] if require_native else []
    failures: list[str] = []
    if not isinstance(record, dict):
        return ["native reset entity state must be a JSON object"]
    if record.get("schema") != SCHEMA:
        failures.append("native reset entity state schema mismatch")
    if record.get("fixture_id") != fixture_id:
        failures.append("native reset entity state fixture identity mismatch")
    if record.get("capture_boundary") != RESET_BOUNDARY or record.get("captured_at_reset_only") is not True:
        failures.append("native reset entity state is not captured exclusively at reset before action 1")
    if record.get("usage_policy") != USAGE_POLICY:
        failures.append("native reset entity state has prohibited hydration/runtime/score usage policy")
    if record.get("rng") != RNG_POLICY:
        failures.append("native reset entity state RNG policy mismatch")
    # A reset receipt must never depend on a per-turn sidecar reference.  This
    # catches both explicit future payloads and tempting digest indirections.
    forbidden = {"native_pre_action_evidence", "pre_action_records", "future_observation", "future_frames", "hydrated_from_step"}
    present = sorted(forbidden & set(record))
    if present:
        failures.append("native reset entity state references prohibited future/pre-action data: " + ", ".join(present))

    bindings = record.get("bindings")
    expected_bindings = {
        "oracle_identity_sha256": sha256_json(oracle_identity()),
        "capture_runtime_sha256": sha256_json(runtime) if isinstance(runtime, dict) else None,
        "level_dump_sha256": sha256_json(level_dump),
        "reset_projection_sha256": sha256_json(reset_projection),
        "actions_sha256": sha256_json(actions),
    }
    if not isinstance(bindings, dict):
        failures.append("native reset entity state lacks identity/action/level bindings")
    else:
        for name, expected in expected_bindings.items():
            if expected is None or bindings.get(name) != expected:
                failures.append(f"native reset entity state {name} mismatch")

    portable = level_dump.get("authoritative_reset_entities") if isinstance(level_dump, dict) else None
    failures.extend(validate_portable_reset_projection(portable, reset_projection=reset_projection))
    if isinstance(bindings, dict) and isinstance(portable, dict) and bindings.get("portable_projection_sha256") != portable.get("projection_sha256"):
        failures.append("native reset entity state portable projection binding mismatch")
    from scripts.portable_reset_rng import validate_portable_reset_rng_projection
    portable_rng = level_dump.get("authoritative_reset_rng") if isinstance(level_dump, dict) else None
    has_rng_binding = isinstance(bindings, dict) and "portable_reset_rng_sha256" in bindings
    if portable_rng is not None or has_rng_binding:
        failures.extend(f"authoritative reset RNG: {failure}" for failure in validate_portable_reset_rng_projection(portable_rng))
        if isinstance(bindings, dict) and isinstance(portable_rng, dict) and bindings.get("portable_reset_rng_sha256") != portable_rng.get("projection_sha256"):
            failures.append("native reset entity state portable reset RNG binding mismatch")
    portable_map = level_dump.get("authoritative_reset_map") if isinstance(level_dump, dict) else None
    has_map_binding = isinstance(bindings, dict) and "portable_reset_map_sha256" in bindings
    if portable_map is not None or has_map_binding:
        from scripts.portable_reset_map import validate_portable_reset_map_projection

        failures.extend(f"authoritative reset map: {failure}" for failure in validate_portable_reset_map_projection(portable_map))
        if isinstance(bindings, dict) and isinstance(portable_map, dict) and bindings.get("portable_reset_map_sha256") != portable_map.get("projection_sha256"):
            failures.append("native reset entity state portable reset map binding mismatch")
    state = record.get("state")
    if not isinstance(state, dict) or set(state) != {"entities", "player"}:
        failures.append("native reset entity state payload must contain only entity and player source exports")
        state = {}
    entities = state.get("entities")
    player = state.get("player")
    if isinstance(entities, dict):
        from scripts.nle_native_entities import validate_native_entity_record

        failures.extend(f"native reset entity state: {failure}" for failure in validate_native_entity_record(entities))
    else:
        failures.append("native reset entity state has no entity export")
    if isinstance(player, dict):
        from scripts.nle_native_player import validate_player_record

        failures.extend(f"native reset entity state: {failure}" for failure in validate_player_record(player))
    else:
        failures.append("native reset entity state has no player export")

    if isinstance(entities, dict) and isinstance(player, dict) and isinstance(bindings, dict):
        binary = bindings.get("native_binary_sha256")
        if not isinstance(binary, str) or not binary or entities.get("binary_sha256") != binary or player.get("binary_sha256") != binary:
            failures.append("native reset entity state binary identity mismatch")
        entity_turn = entities.get("source_turn")
        player_turn = player.get("source_turn")
        blstats = reset_projection.get("blstats") if isinstance(reset_projection, dict) else None
        reset_moves = blstats[20] if isinstance(blstats, list) and len(blstats) > 20 and type(blstats[20]) is int else None
        if not isinstance(entity_turn, dict) or type(entity_turn.get("moves")) is not int or type(player_turn) is not int or reset_moves is None:
            failures.append("native reset entity state lacks comparable reset turn counters")
        elif int(entity_turn["moves"]) != player_turn or player_turn != reset_moves:
            failures.append("native reset entity state source turn does not bind the public reset boundary")
    if record.get("reset_source_state_sha256") != sha256_json(state):
        failures.append("native reset entity state source payload digest mismatch")
    if record.get("record_sha256") != sha256_json(_without_digest(record)):
        failures.append("native reset entity state record digest mismatch")
    return failures


def manifest_provenance(record: dict[str, Any] | None) -> dict[str, Any]:
    if record is None:
        return {
            "status": "legacy_no_native_reset_entity_state",
            "scheduler_source_eligible": False,
            "conformance_denominator_included": False,
            "usage_policy": USAGE_POLICY,
            "limitation": "This v1 tape predates a reset-only native entity/scheduler source receipt.",
        }
    return {
        "status": "present_reset_only_source_evidence",
        "scheduler_source_eligible": True,
        "conformance_denominator_included": False,
        "record_sha256": record.get("record_sha256"),
        "usage_policy": USAGE_POLICY,
    }
