"""Source-causal scheduler assertions for native NLE entity exports.

These assertions deliberately classify what the pinned source did.  They do
not predict a destination, encode a seed/coordinate schedule, or implement
NetHack AI.  The only general scheduling implication admitted here is the
one visible directly in ``src/mon.c:movemon``: a retained monster that moved
had at least ``NORMAL_SPEED`` source movement points at the ``movemon`` pass
 boundary. An action frame may precede ``mcalcmove`` replenishment, so a lower
 value is recorded as boundary ambiguity, never as an oracle contradiction.
"""

from __future__ import annotations

from typing import Any, Iterable


NORMAL_SPEED = 12
NLE_PLANE_WIDTH = 79
NLE_PLANE_HEIGHT = 21
NLE_PLANE_COORDINATES = frozenset(
    (x, y) for y in range(NLE_PLANE_HEIGHT) for x in range(NLE_PLANE_WIDTH)
)


def _entity_map(frame: dict[str, Any], *, require_turn_queue: bool = False) -> tuple[list[Any], dict[Any, dict[str, Any]]]:
    """Validate the source-owned identity and list-order boundary."""

    entities = frame.get("entities") if isinstance(frame, dict) else None
    queue = frame.get("turn_queue") if isinstance(frame, dict) else None
    if not isinstance(entities, list) or (require_turn_queue and not isinstance(queue, list)):
        raise ValueError("native entity frame needs explicit entities and turn_queue lists")
    ids: list[Any] = []
    mapped: dict[Any, dict[str, Any]] = {}
    for order, entity in enumerate(entities):
        if not isinstance(entity, dict):
            raise ValueError("native entity frame contains a non-object entity")
        entity_id = entity.get("entity_id")
        if type(entity_id) is not int or entity_id <= 0 or entity_id in mapped:
            raise ValueError("native entity frame lacks unique positive stable source IDs")
        x, y = entity.get("x"), entity.get("y")
        scheduler = entity.get("scheduler")
        if type(x) is not int or type(y) is not int or not isinstance(scheduler, dict):
            raise ValueError("native entity frame lacks source position or scheduler state")
        if scheduler.get("iteration_order") != order:
            raise ValueError("native entity list order and scheduler iteration_order disagree")
        ids.append(entity_id)
        mapped[entity_id] = entity
    if queue is not None and queue != ids:
        raise ValueError("native entity frame turn_queue does not exactly preserve source list order")
    return ids, mapped


def _source_turn_boundary(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Preserve, but do not interpret, source time at an action boundary.

    ``moves`` and ``monstermoves`` are separate NetHack source counters.  In
    particular, the held-out native trace contains actor movement at a
    boundary whose counters did not advance.  A verifier must therefore bind
    both raw values to the transition, rather than silently treating either
    counter as a proxy for whether every actor received a turn.
    """

    boundaries: dict[str, dict[str, int]] = {}
    for phase, frame in (("before", before), ("after", after)):
        source_turn = frame.get("source_turn") if isinstance(frame, dict) else None
        if not isinstance(source_turn, dict):
            raise ValueError(f"native causal transition lacks {phase} source_turn")
        values: dict[str, int] = {}
        for name in ("moves", "monstermoves"):
            value = source_turn.get(name)
            if type(value) is not int or value < 0:
                raise ValueError(f"native causal transition has invalid {phase} source_turn.{name}")
            values[name] = value
        boundaries[phase] = values
    return {
        "before": boundaries["before"],
        "after": boundaries["after"],
        "delta": {
            name: boundaries["after"][name] - boundaries["before"][name]
            for name in ("moves", "monstermoves")
        },
        "contract": (
            "Raw source counters are action-bound chronology evidence only. "
            "Their delta does not classify hero turn consumption or imply that "
            "a stationary/moving entity did or did not receive a scheduler pass."
        ),
    }


def occupancy_map(frame: dict[str, Any]) -> dict[str, Any]:
    """Export a lossless source-frame entity occupancy map.

    This validates exact stable IDs, the native linked-list order, and the
    one-monster-per-square invariant.  It makes no claim about player or trap
    occupancy, which are outside this dynamic-entity reader's authority.
    """

    ids, entities = _entity_map(frame, require_turn_queue=True)
    occupied: dict[tuple[int, int], int] = {}
    for entity_id in ids:
        entity = entities[entity_id]
        coordinate = (int(entity["x"]), int(entity["y"]))
        if coordinate in occupied:
            raise ValueError("native entity frame has two entities on one source cell")
        occupied[coordinate] = entity_id
    return {
        "schema": "gamebench.nethack.native_entity_occupancy.v1",
        "turn_queue": ids,
        "list_order": [{"entity_id": entity_id, "iteration_order": index} for index, entity_id in enumerate(ids)],
        "occupied_cells": [
            {"x": x, "y": y, "entity_id": entity_id}
            for (x, y), entity_id in sorted(occupied.items(), key=lambda record: (record[0][1], record[0][0], record[1]))
        ],
        "scope": "Exact native monster occupancy only; no player, trap, pathing, or destination inference.",
    }


def _cell_index(
    cells: Iterable[dict[str, Any]],
    *,
    require_complete_nle_plane: bool = False,
) -> dict[tuple[int, int], dict[str, Any]]:
    indexed: dict[tuple[int, int], dict[str, Any]] = {}
    for cell in cells:
        if not isinstance(cell, dict) or type(cell.get("x")) is not int or type(cell.get("y")) is not int:
            raise ValueError("native source-cell frame has an invalid coordinate")
        coordinate = (int(cell["x"]), int(cell["y"]))
        if coordinate in indexed:
            raise ValueError("native source-cell frame repeats a coordinate")
        if cell.get("object_stack_complete") is not True or not isinstance(cell.get("object_stack"), list):
            raise ValueError("native source-cell frame lacks a complete object stack")
        if type(cell.get("terrain_type")) is not int or type(cell.get("terrain_memory_glyph")) is not int:
            raise ValueError("native source-cell frame lacks exact terrain underlay")
        monster_id = cell.get("monster_id")
        if monster_id is not None and (type(monster_id) is not int or monster_id <= 0):
            raise ValueError("native source-cell frame has an invalid monster occupancy ID")
        indexed[coordinate] = cell
    if not indexed:
        raise ValueError("native source-cell frame is empty")
    if require_complete_nle_plane and frozenset(indexed) != NLE_PLANE_COORDINATES:
        raise ValueError("native causal transition requires the complete 79x21 pre/post NLE source grid")
    return indexed


def scheduler_transition(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Match only stable native IDs and classify an observed source transition."""

    before_ids, before_map = _entity_map(before)
    after_ids, after_map = _entity_map(after)
    events: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    ambiguities: list[dict[str, Any]] = []
    for entity_id in before_ids:
        entity = before_map[entity_id]
        scheduler = entity.get("scheduler") if isinstance(entity.get("scheduler"), dict) else {}
        ready = type(scheduler.get("movement_points")) is int and int(scheduler["movement_points"]) >= NORMAL_SPEED
        if entity_id not in after_map:
            events.append({"entity_id": entity_id, "kind": "removed", "ready_before": ready})
            continue
        successor = after_map[entity_id]
        source = (entity.get("x"), entity.get("y"))
        target = (successor.get("x"), successor.get("y"))
        kind = "stationary" if source == target else "moved"
        successor_scheduler = successor.get("scheduler") if isinstance(successor.get("scheduler"), dict) else {}
        before_movement = scheduler.get("movement_points")
        after_movement = successor_scheduler.get("movement_points")
        if type(before_movement) is not int or type(after_movement) is not int:
            raise ValueError("native entity frame lacks exact before/after movement points")
        event = {
            "entity_id": entity_id,
            "kind": kind,
            "from": {"x": source[0], "y": source[1]},
            "to": {"x": target[0], "y": target[1]},
            "ready_before": ready,
            "iteration_order_before": scheduler.get("iteration_order"),
            "iteration_order_after": successor_scheduler.get("iteration_order"),
            "movement_points_before": before_movement,
            "movement_points_after": after_movement,
            "movement_points_delta": after_movement - before_movement,
        }
        events.append(event)
        if kind == "moved" and not ready:
            ambiguities.append({"entity_id": entity_id, "code": "movement_budget_replenished_after_pre_action_boundary", "detail": "action-boundary movement is below NORMAL_SPEED, but source allocation may occur before movemon"})
    for entity_id in after_ids:
        if entity_id not in before_map:
            events.append({"entity_id": entity_id, "kind": "created"})
    return {
        "schema": "gamebench.nethack.native_scheduler_transition.v1",
        "status": "pass" if not violations else "errors_found",
        "events": events,
        "violations": violations,
        "ambiguities": ambiguities,
        "contract": "Stable source IDs classify observed results. ready_before is action-boundary evidence only; movemon eligibility may be established after mcalcmove allocation.",
    }


def causal_transition_evidence(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    before_cells: Iterable[dict[str, Any]],
    after_cells: Iterable[dict[str, Any]],
    source_case: str,
    action: dict[str, Any],
) -> dict[str, Any]:
    """Join a fixed pre/post native boundary without predicting an AI choice.

    ``before_cells`` must be a complete grid frozen before input, not a
    destination-specific query made after observing the result.  The function
    only classifies the source outcome.  In particular, an empty monster cell
    is not called an empty NetHack square: the player and several relevant
    collision states remain out of scope.
    """

    if not isinstance(source_case, str) or not source_case:
        raise ValueError("causal transition needs a named held-out source case")
    if not isinstance(action, dict) or type(action.get("action_id")) is not int or not isinstance(action.get("action_name"), str):
        raise ValueError("causal transition needs an exact action ID and action name")
    before_index = _cell_index(before_cells, require_complete_nle_plane=True)
    after_index = _cell_index(after_cells, require_complete_nle_plane=True)
    source_turn = _source_turn_boundary(before, after)
    transition = scheduler_transition(before, after)
    _, before_entities = _entity_map(before, require_turn_queue=True)
    _, after_entities = _entity_map(after, require_turn_queue=True)
    for phase, entities, index in (("before", before_entities, before_index), ("after", after_entities, after_index)):
        for entity_id, entity in entities.items():
            coordinate = (entity["x"], entity["y"])
            if coordinate not in index or index[coordinate].get("monster_id") != entity_id:
                raise ValueError(f"{phase} source-cell grid and entity list disagree for stable ID {entity_id}")
    before_occupancy = occupancy_map(before)
    after_occupancy = occupancy_map(after)
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for event in transition["events"]:
        if event.get("kind") not in {"moved", "stationary"}:
            continue
        entity_id = event["entity_id"]
        source = event["from"]
        target = event["to"]
        source_coordinate = (source["x"], source["y"])
        target_coordinate = (target["x"], target["y"])
        try:
            source_before = before_index[source_coordinate]
            target_before = before_index[target_coordinate]
            source_after = after_index[source_coordinate]
            target_after = after_index[target_coordinate]
        except KeyError as error:
            raise ValueError(f"complete source-cell frame omitted transition coordinate {error.args[0]}") from error
        destination_pre_monster_id = target_before.get("monster_id")
        if destination_pre_monster_id is None:
            destination_pre_occupant_boundary_status = "none"
            destination_pre_occupant_post_position = None
            destination_pre_occupant_iteration_order_before = None
            destination_pre_occupant_iteration_order_after = None
        elif destination_pre_monster_id == entity_id:
            destination_pre_occupant_boundary_status = "self"
            destination_pre_occupant_post_position = {"x": target_coordinate[0], "y": target_coordinate[1]}
            destination_pre_occupant_iteration_order_before = event.get("iteration_order_before")
            destination_pre_occupant_iteration_order_after = event.get("iteration_order_after")
        else:
            destination_predecessor = before_entities.get(destination_pre_monster_id)
            if destination_predecessor is None:
                raise ValueError("source-cell grid names an entity absent from the pre-action list")
            destination_predecessor_after = after_entities.get(destination_pre_monster_id)
            destination_pre_occupant_iteration_order_before = destination_predecessor["scheduler"].get("iteration_order")
            if destination_predecessor_after is None:
                destination_pre_occupant_boundary_status = "removed"
                destination_pre_occupant_post_position = None
                destination_pre_occupant_iteration_order_after = None
            else:
                destination_pre_occupant_post_position = {
                    "x": destination_predecessor_after["x"],
                    "y": destination_predecessor_after["y"],
                }
                destination_pre_occupant_iteration_order_after = destination_predecessor_after["scheduler"].get("iteration_order")
                destination_pre_occupant_boundary_status = (
                    "retained_at_destination"
                    if destination_pre_occupant_post_position == {"x": target_coordinate[0], "y": target_coordinate[1]}
                    else "retained_elsewhere"
                )
        record = {
            "entity_id": entity_id,
            "kind": event["kind"],
            "ready_before": event["ready_before"],
            "scheduler_movement_points_before": event["movement_points_before"],
            "scheduler_movement_points_after": event["movement_points_after"],
            "scheduler_movement_points_delta": event["movement_points_delta"],
            "iteration_order_before": event.get("iteration_order_before"),
            "iteration_order_after": event.get("iteration_order_after"),
            "from": source,
            "to": target,
            "source_cell_before": source_before,
            "destination_cell_before": target_before,
            "source_cell_after": source_after,
            "destination_cell_after": target_after,
            "destination_pre_monster_occupancy": (
                "none" if destination_pre_monster_id is None else
                "self" if destination_pre_monster_id == entity_id else "other_entity"
            ),
            "destination_pre_monster_id": destination_pre_monster_id,
            "destination_pre_occupant_iteration_order_before": destination_pre_occupant_iteration_order_before,
            "destination_pre_occupant_iteration_order_after": destination_pre_occupant_iteration_order_after,
            "destination_pre_occupant_post_position": destination_pre_occupant_post_position,
            "destination_pre_occupant_boundary_status": destination_pre_occupant_boundary_status,
        }
        if source_before.get("monster_id") != entity_id:
            errors.append({"entity_id": entity_id, "code": "pre_source_occupancy_mismatch"})
        if event["kind"] == "moved":
            if target_after.get("monster_id") != entity_id:
                errors.append({"entity_id": entity_id, "code": "post_destination_occupancy_mismatch"})
            if source_after.get("monster_id") == entity_id:
                errors.append({"entity_id": entity_id, "code": "post_source_not_vacated"})
        records.append(record)
    errors.extend(transition["violations"])
    return {
        "schema": "gamebench.nethack.native_causal_entity_transition.v1",
        "status": "pass" if not errors else "errors_found",
        "source_case": source_case,
        "action": {"action_id": action["action_id"], "action_name": action["action_name"]},
        "source_turn": source_turn,
        "before_occupancy": before_occupancy,
        "after_occupancy": after_occupancy,
        "records": records,
        "errors": errors,
        "boundary_ambiguities": transition["ambiguities"],
        "contract": (
            "The complete native grid was frozen before this exact action. Stable source IDs, source counters, movement "
            "points, list order, monster occupancy, terrain, object stacks, and post-action restoration are assertions "
            "only; no destination, collision, pathing, combat, or AI rule is inferred."
        ),
    }


def destination_collision_rule_assessment(transitions: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Falsify tempting scheduler rules instead of upgrading correlations.

    A passive trace may show a condition is necessary *within that sample*.
    It cannot establish that it is sufficient for a destination choice: the
    unexported player position, target-selection state, and full NetHack
    collision/combat state can still decide the result.  This report makes
    that asymmetry explicit and supplies concrete counterexamples whenever a
    ready entity remained stationary.
    """

    records: list[dict[str, Any]] = []
    for transition in transitions:
        if not isinstance(transition, dict):
            raise ValueError("rule assessment needs causal transition objects")
        source_case = transition.get("source_case")
        action = transition.get("action")
        if not isinstance(source_case, str) or not isinstance(action, dict):
            raise ValueError("rule assessment needs named causal transition provenance")
        for record in transition.get("records", []):
            if not isinstance(record, dict):
                raise ValueError("rule assessment has a malformed transition record")
            records.append({"source_case": source_case, "action": action, **record})

    moved = [record for record in records if record.get("kind") == "moved"]
    stationary_ready = [record for record in records if record.get("kind") == "stationary" and record.get("ready_before") is True]
    moved_without_ready = [record for record in moved if record.get("ready_before") is not True]
    moved_into_other_monster = [record for record in moved if record.get("destination_pre_monster_occupancy") == "other_entity"]
    ready_counterexamples = [
        {
            "source_case": record["source_case"],
            "action": record["action"],
            "entity_id": record["entity_id"],
            "position": record["from"],
            "movement_points_before": record.get("scheduler_movement_points_before"),
            "movement_points_after": record.get("scheduler_movement_points_after"),
            "reason": "ready_before_but_stationary",
        }
        for record in stationary_ready
    ]
    return {
        "schema": "gamebench.nethack.native_destination_collision_rule_assessment.v1",
        "status": "assertion_only",
        "transition_record_count": len(records),
        "moved_record_count": len(moved),
        "movement_points_threshold": {
            "condition": f"action-boundary movement_points >= {NORMAL_SPEED} (not the later movemon pass boundary)",
            "observed_necessary_within_sample": bool(moved) and not moved_without_ready,
            "necessary_counterexamples": moved_without_ready,
            "boundary_eligibility_ambiguity_count": len(moved_without_ready),
            "observed_sufficient": False,
            "sufficiency_status": "counterexample_found" if ready_counterexamples else "not_proven_from_passive_trace",
            "sufficiency_counterexamples": ready_counterexamples,
        },
        "destination_pre_monster_occupancy": {
            "condition": "destination had no other native monster before the action",
            "observed_necessary_within_sample": bool(moved) and not moved_into_other_monster,
            "necessary_counterexamples": moved_into_other_monster,
            "observed_sufficient": False,
            "sufficiency_status": "not_identifiable_from_passive_trace",
            "why_not_sufficient": (
                "The reader does not export player occupancy, target-selection state, full collision/combat state, or a "
                "counterfactual destination set. An empty native-monster slot is not an empty NetHack square."
            ),
        },
        "preoccupied_destination_boundary_outcomes": {
            "condition": "a moved entity's destination held a different native monster in the complete pre-action grid",
            "observed_count": len(moved_into_other_monster),
            "outcomes": {
                status: sum(1 for record in moved_into_other_monster if record.get("destination_pre_occupant_boundary_status") == status)
                for status in sorted({str(record.get("destination_pre_occupant_boundary_status")) for record in moved_into_other_monster})
            },
            "interpretation": (
                "This is a boundary classification, not a reconstructed sub-action order. A removed or displaced prior "
                "occupant may reflect combat, relocation, death, or another unexported source path."
            ),
        },
        "iteration_order": {
            "observed_exactly": True,
            "predicts_destination": False,
            "why_not": "Linked-list order does not reveal whether or where an entity will act.",
        },
        "gold_scheduler_pathing_eligible": False,
        "blocker": (
            "Necessary sample correlations and exact post hoc source assertions do not establish a sufficient general "
            "destination/collision rule. No Python or Rust dynamic-entity behavior may be added from this evidence."
        ),
    }


def static_vacated_underlay_assertion(
    transition: dict[str, Any],
    *,
    after_cells: dict[tuple[int, int], dict[str, Any]],
    after_glyphs: list[list[int]],
    after_chars: list[list[int]] | None = None,
) -> dict[str, Any]:
    """Check restoration only where the post-action public cell is static.

    ``level.locations[x][y].glyph`` is the source terrain-memory glyph, not
    an assertion that NLE currently renders that cell.  A vacated but unseen
    square can still show the unexplored glyph; a hero can also cover it.
    When raw characters are supplied, compare only a directly rendered static
    surface and leave all other cells unjudged rather than mistaking FOW for
    an underlay failure.
    """

    comparisons = 0
    errors: list[dict[str, Any]] = []
    for event in transition.get("events", []):
        if not isinstance(event, dict) or event.get("kind") != "moved":
            continue
        source = event.get("from")
        target = event.get("to")
        if not isinstance(source, dict) or not isinstance(target, dict):
            continue
        x, y = source.get("x"), source.get("y")
        if not (type(x) is int and type(y) is int and (x, y) != (target.get("x"), target.get("y"))):
            continue
        cell = after_cells.get((x, y))
        if not isinstance(cell, dict) or cell.get("object_stack") != [] or cell.get("monster_id") is not None:
            continue
        if not (0 <= y < len(after_glyphs) and isinstance(after_glyphs[y], list) and 0 <= x < len(after_glyphs[y])):
            raise ValueError("after glyph plane does not cover source-static vacated coordinate")
        if after_chars is not None:
            if not (0 <= y < len(after_chars) and isinstance(after_chars[y], list) and 0 <= x < len(after_chars[y])):
                raise ValueError("after character plane does not cover source-static vacated coordinate")
            raw_character = after_chars[y][x]
            character = chr(raw_character) if type(raw_character) is int else raw_character
            if character not in {".", "#", "|", "-", "+", "<", ">", "_", "{", "}", "~"}:
                continue
        comparisons += 1
        expected = cell.get("terrain_memory_glyph")
        actual = after_glyphs[y][x]
        if expected != actual:
            errors.append({"entity_id": event.get("entity_id"), "x": x, "y": y, "expected_glyph": expected, "actual_glyph": actual})
    return {
        "schema": "gamebench.nethack.native_static_vacated_underlay.v1",
        "status": "pass" if not errors else "errors_found",
        "comparisons": comparisons,
        "errors": errors,
        "contract": "Only a vacated cell with exact post-action native empty object stack, no native monster, and a directly rendered static public character is compared to its source terrain-memory glyph.",
    }
