#!/usr/bin/env python3
"""Judge exact-wheel ``mfndpos`` selector/collision hypotheses conservatively.

This consumes the *source-only* LLDB report from ``verify_lldb_branch_trace``.
It never feeds a gold engine or a conformance denominator.  The fixed
hypothesis is intentionally narrow: when a traced dog_move/m_move invocation
returns ``1``, its return-boundary actor coordinate is one of the candidates
that its own mfndpos call returned.  Collision is a separately observed
condition (ALLOW_M or ALLOW_MDISP); zero collision examples are a blocker, not
evidence that ordinary movement generalises to collision handling.

Seeds are split before inspecting outcomes.  There are no coordinate tables,
learned weights, or seed-specific rules.  Every malformed record, empty split,
or missing exact selector binding fails closed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "gamebench.nethack.mfndpos_selector_collision_analysis.v1"
TRACE_SCHEMA = "gamebench.nethack.instrumented_oracle_equivalence.v1"
ALLOW_M = 0x00080000
ALLOW_MDISP = 0x00001000
COLLISION_MASK = ALLOW_M | ALLOW_MDISP


def _as_int(value: Any) -> int | None:
    return value if type(value) is int else None


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    x, y = _as_int(value.get("native_x")), _as_int(value.get("native_y"))
    return (x, y) if x is not None and y is not None else None


def _split_seeds(records: list[dict[str, Any]], calibration: Iterable[int], heldout: Iterable[int]) -> tuple[set[int], set[int]]:
    known = {record.get("seed") for record in records if type(record.get("seed")) is int}
    calibration_set, heldout_set = set(calibration), set(heldout)
    if not calibration_set or not heldout_set:
        raise ValueError("calibration and heldout seed sets must both be non-empty and preselected")
    if calibration_set & heldout_set:
        raise ValueError("calibration and heldout seeds overlap")
    unknown = (calibration_set | heldout_set) - known
    if unknown:
        raise ValueError(f"preselected split contains seeds absent from trace: {sorted(unknown)}")
    unassigned = known - calibration_set - heldout_set
    if unassigned:
        raise ValueError(f"trace records have seeds outside preselected split: {sorted(unassigned)}")
    return calibration_set, heldout_set


def _observe(record: dict[str, Any]) -> dict[str, Any]:
    """Validate one exact branch record without interpreting its outcome."""

    failures: list[str] = []
    seed = _as_int(record.get("seed"))
    stable_id = _as_int(record.get("stable_entity_id"))
    mfndpos = record.get("mfndpos")
    result = record.get("selected_result")
    if seed is None:
        failures.append("missing_seed")
    if stable_id is None or stable_id <= 0:
        failures.append("invalid_stable_entity_id")
    if not isinstance(mfndpos, dict) or not isinstance(result, dict):
        return {"failures": failures + ["missing_branch_record_sections"]}
    caller = mfndpos.get("caller")
    if caller not in {"dog_move", "m_move"}:
        failures.append("unknown_selector_caller")
    source = _point(mfndpos.get("actor_at_mfndpos_return"))
    if source is None:
        failures.append("missing_mfndpos_actor_coordinate")
    count = _as_int(mfndpos.get("candidate_count"))
    candidates = mfndpos.get("candidates")
    if count is None or not 1 <= count <= 9 or not isinstance(candidates, list) or len(candidates) != count:
        failures.append("invalid_candidate_count")
        candidates = []
    candidate_points: list[tuple[int, int]] = []
    candidate_flags: list[int] = []
    for candidate in candidates:
        point = _point(candidate)
        flags = _as_int(candidate.get("mfndpos_flags")) if isinstance(candidate, dict) else None
        if point is None or flags is None:
            failures.append("malformed_candidate")
            continue
        candidate_points.append(point)
        candidate_flags.append(flags)
    if len(set(candidate_points)) != len(candidate_points):
        failures.append("duplicate_candidate_coordinate")
    if source is not None:
        for point in candidate_points:
            if max(abs(point[0] - source[0]), abs(point[1] - source[1])) != 1:
                failures.append("non_adjacent_candidate")
                break
    selector = result.get("branch_selector_return")
    if not isinstance(selector, dict):
        return {"failures": failures + ["missing_exact_selector_return"]}
    if selector.get("selector") != caller:
        failures.append("selector_caller_mismatch")
    selector_actor = selector.get("actor")
    after_actor = selector.get("actor_after")
    if not isinstance(selector_actor, dict) or selector_actor.get("entity_id") != stable_id:
        failures.append("selector_actor_identity_mismatch")
    if not isinstance(after_actor, dict) or after_actor.get("entity_id") != stable_id:
        failures.append("selector_return_actor_identity_mismatch")
    after_point = _point(after_actor)
    return_code = _as_int(selector.get("return_code"))
    if return_code is None:
        failures.append("missing_selector_return_code")
    selected_index = candidate_points.index(after_point) if after_point in candidate_points else None
    selected_flags = candidate_flags[selected_index] if selected_index is not None else None
    return {
        "seed": seed,
        "failures": failures,
        "return_code": return_code,
        "return_one": return_code == 1,
        "arrival_matches_candidate": selected_index is not None,
        "selected_flags": selected_flags,
        "collision_selected": selected_flags is not None and bool(selected_flags & COLLISION_MASK),
        "collision_candidates": sum(bool(flags & COLLISION_MASK) for flags in candidate_flags),
    }


def _score(records: list[dict[str, Any]]) -> dict[str, Any]:
    observations = [_observe(record) for record in records]
    structural_failures = Counter(failure for observation in observations for failure in observation["failures"])
    return_one = [observation for observation in observations if observation.get("return_one")]
    arrival_failures = sum(not observation.get("arrival_matches_candidate", False) for observation in return_one)
    collision = [observation for observation in return_one if observation.get("collision_selected")]
    return {
        "record_count": len(records),
        "structural_comparison_count": len(observations),
        "structural_error_count": sum(structural_failures.values()),
        "structural_failures": dict(sorted(structural_failures.items())),
        "return_one_comparison_count": len(return_one),
        "return_one_arrival_error_count": arrival_failures,
        "collision_selected_comparison_count": len(collision),
        "candidate_collision_flag_count": sum(observation.get("collision_candidates", 0) for observation in observations),
    }


def analyze(trace: dict[str, Any], *, calibration_seeds: Iterable[int], heldout_seeds: Iterable[int]) -> dict[str, Any]:
    if trace.get("schema") != TRACE_SCHEMA:
        raise ValueError("input is not an instrumented-oracle candidate")
    if trace.get("instrumented_source_oracle_eligible") is not True:
        raise ValueError("input trace did not pass exact-wheel source-oracle equivalence")
    controls = trace.get("controls")
    if not isinstance(controls, dict) or any(controls.get(key) != 0 for key in (
        "public_observation_mismatch_count", "native_boundary_mismatch_count", "final_rng_state_mismatch_count",
        "trace_replay_mismatch_count", "unmatched_event_count", "trace_error_count",
    )):
        raise ValueError("input trace lacks zero-mismatch exact-wheel controls")
    records = trace.get("branch_records")
    if not isinstance(records, list) or not records:
        raise ValueError("input trace has zero branch records")
    calibration_set, heldout_set = _split_seeds(records, calibration_seeds, heldout_seeds)
    calibration = _score([record for record in records if record.get("seed") in calibration_set])
    heldout = _score([record for record in records if record.get("seed") in heldout_set])
    if not calibration["record_count"] or not heldout["record_count"]:
        raise ValueError("one preselected split has zero branch comparisons")
    counterexamples: list[dict[str, Any]] = []
    for split_name, score in (("calibration", calibration), ("heldout", heldout)):
        if score["structural_error_count"]:
            counterexamples.append({"code": f"{split_name}_structural_trace_error", "count": score["structural_error_count"], "details": score["structural_failures"]})
        if score["return_one_comparison_count"] == 0:
            counterexamples.append({"code": f"{split_name}_zero_selector_arrival_comparisons", "count": 0})
        elif score["return_one_arrival_error_count"]:
            counterexamples.append({"code": f"{split_name}_selector_arrival_not_in_candidate_set", "count": score["return_one_arrival_error_count"]})
    # Collision must be exercised on heldout data; a noncollision trace
    # cannot validate collision behavior by analogy.
    if heldout["collision_selected_comparison_count"] == 0:
        counterexamples.append({"code": "heldout_zero_selected_collision_examples", "count": 0, "evidence": "No return-code-1 selection used ALLOW_M or ALLOW_MDISP."})
    selector_source_eligible = not counterexamples
    return {
        "schema": SCHEMA,
        "status": "selector_hypothesis_source_only" if selector_source_eligible else "blocked_or_rejected",
        "trace_identity": trace.get("identity"),
        "validity": {
            "preselected_disjoint_seed_split": True,
            "fixed_no_fit_hypothesis": True,
            "no_seed_or_coordinate_lookup": True,
            "exact_wheel_equivalence_already_passed": True,
            "selector_return_boundary_not_action_end": True,
            "trace_excluded_from_gold_runtime_and_scoring": True,
        },
        "split": {"calibration_seeds": sorted(calibration_set), "heldout_seeds": sorted(heldout_set)},
        "hypothesis": {
            "id": "return_one_arrives_on_its_own_mfndpos_candidate",
            "fixed_rule": "For a dog_move/m_move call returning 1, actor_after.native_{x,y} equals exactly one coordinate in its immediately preceding mfndpos candidate array.",
            "collision_definition": "Selected candidate has ALLOW_M (0x00080000) or ALLOW_MDISP (0x00001000).",
        },
        "calibration": calibration,
        "heldout": heldout,
        "counterexamples": counterexamples,
        "source_selector_hypothesis_eligible": selector_source_eligible,
        "gold_implementation_eligible": False,
        "implementation_blocker": (
            "Exact return-boundary tracing can validate a source-local selector invariant, but it is not an action pre-state "
            "input and no cross-language gold destination/collision implementation has been tested."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="standalone LLDB frontier candidate JSON")
    parser.add_argument("--calibration-seeds", required=True, help="comma-separated seeds fixed before outcomes")
    parser.add_argument("--heldout-seeds", required=True, help="comma-separated seeds fixed before outcomes")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parse = lambda value: [int(item) for item in value.split(",") if item]
    result = analyze(json.loads(args.trace.read_text()), calibration_seeds=parse(args.calibration_seeds), heldout_seeds=parse(args.heldout_seeds))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "report": str(args.output.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
