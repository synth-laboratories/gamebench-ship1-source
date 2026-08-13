"""Fail-closed contract for read-only native target/path-state evidence.

The matrix deliberately separates native fields now copied from the exact
pinned source process from the public NLE surface and from controls still
missing for a general scheduler.  An exported field is useful for auditing a
source transition; it is never a licence to reimplement ``dog_move`` or
``m_move`` in either gold lane.
"""

from __future__ import annotations

from typing import Any


SCHEMA = "gamebench.nethack.native_path_state_completeness.v1"

# Exact source locations are tied to SOURCE_COMMIT in nle_native_entities.py.
# ``public_nle_090`` names the public control that would be needed to make a
# field observable without this private oracle adapter; none exists for the
# decision state below.
COMPLETENESS_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "control": "stable instance/list order/movement budget",
        "source": ["include/monst.h:71-85", "src/mon.c:720-779"],
        "native_export": "entity_id, scheduler.iteration_order, scheduler.movement_points",
        "public_nle_090": "unavailable (glyph/species and MG_PET are not instance identity or queue order)",
        "status": "exported_for_source_assertion_only",
    },
    {
        "control": "apparent player target",
        "source": ["include/monst.h:82-85", "src/monmove.c:369-540", "src/monmove.c:820-879"],
        "native_export": "path_state.apparent_hero_native (mux,muy)",
        "public_nle_090": "unavailable (public hero coordinate does not expose each monster's remembered target)",
        "status": "exported_for_source_assertion_only",
    },
    {
        "control": "backtracking history",
        "source": ["include/monst.h:84-85", "src/dogmove.c:1072-1108", "src/dogmove.c:1203-1224"],
        "native_export": "path_state.mtrack_native",
        "public_nle_090": "unavailable (rendered cells do not expose per-monster tracks)",
        "status": "exported_for_source_assertion_only",
    },
    {
        "control": "strategy, trap knowledge, and action-blocking status",
        "source": ["include/monst.h:94-163", "src/monmove.c:369-470", "src/monmove.c:820-879"],
        "native_export": "path_state.strategy, trap_seen_mask, last_monster_move, status",
        "public_nle_090": "unavailable (chars/glyphs/specials do not expose bitfields or strategy)",
        "status": "exported_for_source_assertion_only",
    },
    {
        "control": "tame non-minion hunger/training/goal extension",
        "source": ["include/mextra.h:159-200", "src/dogmove.c:862-1005", "src/dogmove.c:1072-1224"],
        "native_export": "path_state.edog (hunger, apport, goal, whistle/drop/abuse/revival state)",
        "public_nle_090": "unavailable (MG_PET does not export struct edog)",
        "status": "exported_for_source_assertion_only",
    },
    {
        "control": "static species capability, branch-family, and attack identity",
        "source": ["include/permonst.h:21-57", "include/monattk.h:11-87", "include/monflag.h:70-160", "src/monmove.c:868-930", "src/mhitu.c:650-760"],
        "native_export": "species_rules (pinned mons entry name, mflags1/2/3, signed AC/level/MR, resistances, and exact six-slot mattk profile)",
        "public_nle_090": "unavailable (species glyph does not expose static movement/object/terrain flags, AC, resistances, or attack matrix)",
        "status": "exported_for_source_assertion_only",
    },
    {
        "control": "candidate positions, mfndpos flags, terrain/traps, player globals, combat, and draw ownership",
        "source": ["src/dogmove.c:926-1127", "src/monmove.c:820-1260"],
        "native_export": "not a complete decision/control export",
        "public_nle_090": "not a complete public control export",
        "status": "blocker_for_gold_destination_collision_or_pathing",
    },
)


def _issue(issues: list[dict[str, str]], code: str, detail: str) -> None:
    issues.append({"code": code, "detail": detail})


def validate_native_path_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Validate only the ABI-backed extension of one native snapshot.

    A zero-entity record has no positive source comparison.  It therefore
    fails closed even though it is structurally well-formed: the report cannot
    claim scheduler/path-state coverage merely from an empty level.
    """

    issues: list[dict[str, str]] = []
    if not isinstance(snapshot, dict) or snapshot.get("schema") != "gamebench.nethack.native_entity_snapshot.v1":
        return {
            "schema": SCHEMA,
            "status": "rejected",
            "comparison_count": 0,
            "source_assertion_eligible": False,
            "gold_scheduler_pathing_eligible": False,
            "issues": [{"code": "invalid_snapshot_schema", "detail": "requires native_entity_snapshot.v1"}],
            "completeness_matrix": list(COMPLETENESS_MATRIX),
        }
    entities = snapshot.get("entities")
    if not isinstance(entities, list):
        entities = []
        _issue(issues, "invalid_entities", "native snapshot must carry an explicit entity list")
    extension_marks = [isinstance(entity, dict) and "path_state" in entity for entity in entities]
    if any(extension_marks) and not all(extension_marks):
        _issue(issues, "partial_path_extension", "path_state must be present for every entity or absent for every legacy entity")
    queue = snapshot.get("turn_queue")
    # Older v1 test/fixture sidecars can omit this optional extension only
    # when there are no entities. A non-empty native entity snapshot must
    # always bind the stable list order explicitly.
    if entities and not isinstance(queue, list):
        _issue(issues, "missing_turn_queue", "non-empty entity sidecar lacks the source list order")
        queue = []
    ids: list[int] = []
    positions: set[tuple[int, int]] = set()
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            _issue(issues, "malformed_entity", f"entity {index} is not an object")
            continue
        entity_id = entity.get("entity_id")
        if type(entity_id) is not int or entity_id <= 0 or entity_id in ids:
            _issue(issues, "invalid_stable_entity_id", f"entity {index} lacks a unique positive native m_id")
        else:
            ids.append(entity_id)
        x, y, native_x = entity.get("x"), entity.get("y"), entity.get("native_x")
        if not (type(x) is int and type(y) is int and type(native_x) is int and native_x == x + 1 and 0 <= x < 79 and 0 <= y < 21):
            _issue(issues, "invalid_entity_coordinate", f"entity {index} lacks a valid native/public coordinate relation")
        elif (x, y) in positions:
            _issue(issues, "duplicate_entity_occupancy", f"entity {index} shares an occupied source coordinate")
        else:
            positions.add((x, y))
        scheduler = entity.get("scheduler")
        if not isinstance(scheduler, dict) or scheduler.get("iteration_order") != index:
            _issue(issues, "invalid_iteration_order", f"entity {index} lacks its exact source list order")
        if not extension_marks or not all(extension_marks):
            continue
        path = entity.get("path_state")
        if not isinstance(path, dict):
            _issue(issues, "missing_path_state", f"entity {index} has no ABI-backed path state")
            continue
        target = path.get("apparent_hero_native")
        if not isinstance(target, dict) or any(type(target.get(key)) is not int for key in ("x", "y")):
            _issue(issues, "invalid_apparent_target", f"entity {index} lacks raw mux/muy")
        track = path.get("mtrack_native")
        if not isinstance(track, list) or len(track) != 4 or any(
            not isinstance(point, dict) or any(type(point.get(key)) is not int for key in ("x", "y"))
            for point in track
        ):
            _issue(issues, "invalid_mtrack", f"entity {index} lacks four raw source track coordinates")
        if any(type(path.get(key)) is not int for key in ("strategy", "trap_seen_mask", "last_monster_move")):
            _issue(issues, "invalid_path_counters", f"entity {index} lacks raw strategy/trap/last-move state")
        status = path.get("status")
        bools = ("cancelled", "can_see", "invisible", "undetected", "stunned", "confused", "trapped", "leashed", "is_minion")
        counters = ("flee_timeout", "blind_timeout", "frozen_timeout", "eating_timeout")
        if not isinstance(status, dict) or any(type(status.get(key)) is not bool for key in bools) or any(
            type(status.get(key)) is not int for key in counters
        ):
            _issue(issues, "invalid_path_status", f"entity {index} lacks ABI-backed movement/path status")
            continue
        is_tame_nonminion = entity.get("allegiance") == "tame" and status["is_minion"] is False
        edog = path.get("edog")
        if is_tame_nonminion:
            edog_ints = ("droptime", "dropdist", "apport", "whistletime", "hungrytime", "abuse", "revivals", "mhpmax_penalty")
            goal = edog.get("ogoal_native") if isinstance(edog, dict) else None
            if not isinstance(edog, dict) or any(type(edog.get(key)) is not int for key in edog_ints) or not isinstance(goal, dict) or any(
                type(goal.get(key)) is not int for key in ("x", "y")
            ) or type(edog.get("killed_by_u")) is not bool:
                _issue(issues, "missing_tame_edog", f"tame non-minion entity {index} lacks complete struct edog state")
        elif edog is not None:
            _issue(issues, "unexpected_edog", f"non-edog entity {index} must not reinterpret a different mextra extension")

    if entities and isinstance(queue, list) and queue != ids:
        _issue(issues, "turn_queue_mismatch", "turn_queue must exactly preserve the stable native entity list order")
    extension_present = bool(entities) and bool(extension_marks) and all(extension_marks)
    if not entities:
        extension_status = "legacy_extension_absent_zero_entities"
    elif extension_present:
        extension_status = "complete_extension_present"
    else:
        extension_status = "legacy_extension_absent_nonempty_entities"
    return {
        "schema": SCHEMA,
        "status": "pass" if not issues else "rejected",
        "extension_status": extension_status,
        "comparison_count": len(entities) if extension_present else 0,
        "source_assertion_eligible": extension_present and not issues,
        "gold_scheduler_pathing_eligible": False,
        "issues": issues,
        "completeness_matrix": list(COMPLETENESS_MATRIX),
        "blocker": (
            "Native target/path fields are read-only source evidence. Candidate sets, mfndpos flags, player/global controls, "
            "combat outcomes, and RNG draw ownership remain incomplete, so no destination/collision/pathing implementation is eligible."
        ),
    }
