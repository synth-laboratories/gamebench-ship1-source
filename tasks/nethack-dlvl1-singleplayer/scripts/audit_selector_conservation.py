#!/usr/bin/env python3
"""Audit exact-wheel selector conservation without manufacturing denominators.

Only state captured at the same ``dog_move``/``m_move`` return boundary is
eligible.  In particular, action-end entity/map state is deliberately ignored:
fast monsters can execute another selector call before the action ends.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "gamebench.nethack.selector_conservation_audit.v1"
TRACE_SCHEMA = "gamebench.nethack.instrumented_oracle_equivalence.v1"
ZERO_CONTROLS = (
    "public_observation_mismatch_count",
    "native_boundary_mismatch_count",
    "final_rng_state_mismatch_count",
    "trace_replay_mismatch_count",
    "trace_error_count",
)


def _integer(value: Any) -> int | None:
    return value if type(value) is int else None


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    x = _integer(value.get("native_x"))
    y = _integer(value.get("native_y"))
    return (x, y) if x is not None and y is not None else None


def _plane(comparisons: int, errors: int) -> dict[str, int]:
    return {"comparison_count": comparisons, "error_count": errors}


def audit(value: dict[str, Any], *, seeds: set[int] | None = None) -> dict[str, Any]:
    """Return denominators justified by the supplied branch-local evidence."""

    if "frontier_candidate" in value:
        value = value["frontier_candidate"]
    if value.get("schema") != TRACE_SCHEMA:
        raise ValueError("input is not an exact-wheel instrumented-oracle candidate")
    controls = value.get("controls")
    identity = value.get("identity")
    records = value.get("branch_records")
    if not isinstance(controls, dict) or not isinstance(identity, dict):
        raise ValueError("trace lacks controls or pinned identity")
    if not isinstance(records, list) or not records:
        raise ValueError("trace has zero branch records")
    if any(_integer(controls.get(name)) != 0 for name in ZERO_CONTROLS):
        raise ValueError("trace has a nonzero equivalence or trace-error control")
    known_seeds = {record.get("seed") for record in records if isinstance(record, dict) and type(record.get("seed")) is int}
    if seeds is not None:
        if not seeds or not seeds <= known_seeds:
            raise ValueError("requested conservation split is empty or absent from trace")
        records = [record for record in records if isinstance(record, dict) and record.get("seed") in seeds]

    membership_comparisons = membership_errors = 0
    completion_comparisons = completion_errors = stationary_completion_count = 0
    destination_comparisons = destination_errors = 0
    underlay_comparisons = underlay_errors = 0
    structural_errors: list[dict[str, Any]] = []
    membership_counterexamples: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        mfndpos = record.get("mfndpos")
        selected = record.get("selected_result")
        selector = selected.get("branch_selector_return") if isinstance(selected, dict) else None
        if not isinstance(mfndpos, dict) or not isinstance(selector, dict):
            structural_errors.append({"record": index, "error": "missing_exact_selector_binding"})
            continue
        if selector.get("selector") != mfndpos.get("caller"):
            structural_errors.append({"record": index, "error": "selector_caller_mismatch"})
            continue
        stable_id = _integer(record.get("stable_entity_id"))
        actor = selector.get("actor")
        actor_after = selector.get("actor_after")
        if (
            stable_id is None
            or not isinstance(actor, dict)
            or not isinstance(actor_after, dict)
            or actor.get("entity_id") != stable_id
            or actor_after.get("entity_id") != stable_id
        ):
            structural_errors.append({"record": index, "error": "selector_actor_identity_mismatch"})
            continue
        destination = _point(actor_after)
        candidates = mfndpos.get("candidates")
        if destination is None or not isinstance(candidates, list) or not candidates:
            structural_errors.append({"record": index, "error": "missing_destination_or_candidates"})
            continue
        candidate_points = [_point(item) for item in candidates]
        if any(point is None for point in candidate_points):
            structural_errors.append({"record": index, "error": "malformed_candidate_coordinate"})
            continue

        # Destination is an independently readable return-boundary actor
        # coordinate. Membership compares that coordinate with the earlier,
        # invocation-local mfndpos array.
        destination_comparisons += 1
        destination_errors += int(not (1 <= destination[0] <= 79 and 0 <= destination[1] <= 20))
        return_code = _integer(selector.get("return_code"))
        if return_code == 1:
            # NetHack's dog_move returns 1 for a completed pet turn, not
            # exclusively for displacement.  Preserve stationary completions
            # as positive source observations; candidate membership applies
            # only to the distinct, actually selected destination.
            completion_comparisons += 1
            source = _point(actor)
            if source is None:
                completion_errors += 1
                structural_errors.append({"record": index, "error": "missing_selector_source_coordinate"})
            elif destination == source:
                stationary_completion_count += 1
            else:
                membership_comparisons += 1
                if destination not in candidate_points:
                    membership_errors += 1
                    membership_counterexamples.append({
                        "record": index,
                        "seed": record.get("seed"),
                        "step": record.get("step"),
                        "stable_entity_id": stable_id,
                        "selector": selector.get("selector"),
                        "return_code": return_code,
                        "actor_after": {"native_x": destination[0], "native_y": destination[1]},
                        "candidate_coordinates": [
                            {"native_x": point[0], "native_y": point[1]}
                            for point in candidate_points
                            if point is not None
                        ],
                    })

        # Underlay is eligible only when the callback captured both source
        # and destination cells immediately before and after this selector
        # invocation. Never substitute pre-action or action-end frames here.
        if return_code != 1:
            continue
        source_before = selector.get("source_underlay_before")
        source_after = selector.get("source_underlay_after")
        destination_before = selector.get("destination_underlay_before")
        destination_after = selector.get("destination_underlay_after")
        snapshots = (source_before, source_after, destination_before, destination_after)
        if all(snapshot is None for snapshot in snapshots):
            continue
        if not all(isinstance(snapshot, dict) for snapshot in snapshots):
            structural_errors.append({"record": index, "error": "partial_selector_boundary_underlay"})
            continue
        for name, before, after in (
            ("source", source_before, source_after),
            ("destination", destination_before, destination_after),
        ):
            if before.get("coordinate") != after.get("coordinate"):
                structural_errors.append({"record": index, "error": f"{name}_underlay_coordinate_mismatch"})
                break
            before_state = before.get("state")
            after_state = after.get("state")
            before_occupancy = before.get("occupancy")
            after_occupancy = after.get("occupancy")
            if not isinstance(before_state, dict) or not isinstance(after_state, dict) or not isinstance(before_occupancy, dict) or not isinstance(after_occupancy, dict):
                structural_errors.append({"record": index, "error": f"malformed_{name}_selector_boundary_underlay_or_occupancy"})
                break
            # A cell's terrain and full floor stack are conserved independent
            # of a monster entering/leaving it.  Occupancy is deliberately
            # retained as a separate raw observation; do not erase it from
            # the denominator by comparing only renderer output.
            underlay_comparisons += 1
            underlay_errors += int(before_state != after_state)

    unmatched = _integer(controls.get("unmatched_event_count"))
    unmatched = unmatched if unmatched is not None else -1
    conservation = {
        "outcome_membership": _plane(membership_comparisons, membership_errors),
        "destination": _plane(destination_comparisons, destination_errors),
        "underlay": _plane(underlay_comparisons, underlay_errors),
    }
    completion = {
        "comparison_count": completion_comparisons,
        "error_count": completion_errors,
        "stationary_completed_turn_count": stationary_completion_count,
    }
    blockers: list[str] = []
    if unmatched != 0:
        blockers.append("unmatched_selector_events")
    if structural_errors:
        blockers.append("structural_record_errors")
    for name, plane in conservation.items():
        if plane["comparison_count"] == 0:
            blockers.append(f"zero_{name}_comparisons")
        elif plane["error_count"]:
            blockers.append(f"{name}_errors")
    return {
        "schema": SCHEMA,
        "status": "source_only_conservation_pass" if not blockers else "blocked",
        "identity": identity,
        "validity": {
            "exact_selector_return_boundary_only": True,
            "action_end_state_excluded": True,
            "no_seed_or_coordinate_lookup": True,
            "trace_excluded_from_gold_runtime_and_scoring": True,
            "seed_subset_preselected": seeds is not None,
        },
        "analyzed_seeds": sorted(seeds) if seeds is not None else sorted(seed for seed in known_seeds if type(seed) is int),
        "selector_conservation": conservation,
        "selector_completion": completion,
        "unmatched_event_count": unmatched,
        "structural_errors": structural_errors,
        "membership_counterexamples": membership_counterexamples,
        "blockers": blockers,
        "source_assertion_eligible": not blockers,
        "gold_implementation_eligible": False,
        "required_capture_for_nonzero_underlay": (
            "At each selector invocation, capture the actor source coordinate and raw levl/object-stack "
            "underlay immediately before selector entry and at that exact selector return. Bind both "
            "snapshots with the same invocation/event identity; action-end frames are ineligible."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--seeds", help="optional preselected comma-separated source seeds")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    selected = {int(value) for value in args.seeds.split(",") if value} if args.seeds else None
    result = audit(json.loads(args.trace.read_text()), seeds=selected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "report": str(args.output.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
