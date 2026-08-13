#!/usr/bin/env python3
"""Evaluate the narrowest held-out-safe selector destination candidate.

The LLDB trace is source-only evidence.  It can test a branch-local invariant,
but it cannot become a gold scheduler input: candidate arrays and selector
returns are captured after an action has begun.  This evaluator therefore
keeps two decisions separate:

* source assertion: a successful selector ends at either its invocation-local
  source coordinate or one of its own ``mfndpos`` candidates;
* gold promotion: Python and Rust must each have positive, independently
  held-out pre-action comparisons.  Until those exist, both lanes are emitted
  with honest zero denominators and the standard promotion gate rejects them.

The calibration/held-out seed split and fixed rule are arguments, recorded and
hashed before observations are scored.  No coordinate, seed, or outcome table
is fitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.frontier_promotion_gate import SCHEMA as GATE_SCHEMA
from scripts.frontier_promotion_gate import evaluate as evaluate_gate


SCHEMA = "gamebench.nethack.scheduler_destination_candidate.v1"
RULE_ID = "successful_selector_stays_or_chooses_own_mfndpos_candidate_v1"


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    x, y = value.get("native_x"), value.get("native_y")
    return (x, y) if type(x) is int and type(y) is int else None


def _candidate_payload(record: dict[str, Any]) -> tuple[int, tuple[int, int], list[tuple[int, int]], tuple[int, int], int] | None:
    seed = record.get("seed")
    mfndpos = record.get("mfndpos")
    selected = record.get("selected_result")
    if type(seed) is not int or not isinstance(mfndpos, dict) or not isinstance(selected, dict):
        return None
    source = _point(mfndpos.get("actor_at_mfndpos_return"))
    candidates_raw = mfndpos.get("candidates")
    selector = selected.get("branch_selector_return")
    if source is None or not isinstance(candidates_raw, list) or not isinstance(selector, dict):
        return None
    candidates = [_point(value) for value in candidates_raw]
    destination = _point(selector.get("actor_after"))
    return_code = selector.get("return_code")
    if not candidates or any(value is None for value in candidates) or destination is None or type(return_code) is not int:
        return None
    return seed, source, [value for value in candidates if value is not None], destination, return_code


def _score(records: list[dict[str, Any]], seeds: set[int]) -> dict[str, Any]:
    comparisons = movement_comparisons = errors = stationary = selected = 0
    counterexamples: list[dict[str, Any]] = []
    structural_errors: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if record.get("seed") not in seeds:
            continue
        payload = _candidate_payload(record)
        if payload is None:
            structural_errors.append({"record": index, "error": "malformed_or_non_invocation_bound_record"})
            continue
        seed, source, candidates, destination, return_code = payload
        if return_code != 1:
            continue
        comparisons += 1
        stationary += int(destination == source)
        movement_comparisons += int(destination != source)
        selected += int(destination in candidates)
        if destination != source and destination not in candidates:
            errors += 1
            counterexamples.append({
                "record": index,
                "seed": seed,
                "step": record.get("step"),
                "stable_entity_id": record.get("stable_entity_id"),
                "source": {"native_x": source[0], "native_y": source[1]},
                "destination": {"native_x": destination[0], "native_y": destination[1]},
                "candidates": [{"native_x": x, "native_y": y} for x, y in candidates],
            })
    return {
        "comparison_count": comparisons,
        "movement_comparison_count": movement_comparisons,
        "error_count": errors + len(structural_errors),
        "stationary_success_count": stationary,
        "candidate_selected_count": selected,
        "structural_errors": structural_errors,
        "counterexamples": counterexamples,
    }


def _diagnostic_conservation(records: Any) -> dict[str, int]:
    comparisons = errors = 0
    if not isinstance(records, list):
        return {"comparison_count": 0, "error_count": 0}
    for record in records:
        selected = record.get("selected_result") if isinstance(record, dict) else None
        selector = selected.get("branch_selector_return") if isinstance(selected, dict) else None
        if not isinstance(selector, dict) or selector.get("return_code") != 1:
            continue
        for prefix in ("source", "destination"):
            before, after = selector.get(f"{prefix}_underlay_before"), selector.get(f"{prefix}_underlay_after")
            if not isinstance(before, dict) or not isinstance(after, dict):
                continue
            comparisons += 1
            errors += int(before.get("state") != after.get("state"))
    return {"comparison_count": comparisons, "error_count": errors}


def _split_underlay(records: list[dict[str, Any]], seeds: set[int]) -> dict[str, int]:
    return _diagnostic_conservation([record for record in records if record.get("seed") in seeds])


def evaluate(trace: dict[str, Any], *, calibration_seeds: Iterable[int], heldout_seeds: Iterable[int]) -> dict[str, Any]:
    calibration, heldout = set(calibration_seeds), set(heldout_seeds)
    if not calibration or not heldout or calibration & heldout:
        raise ValueError("calibration and heldout splits must be non-empty and disjoint")
    if trace.get("schema") != "gamebench.nethack.instrumented_oracle_equivalence.v1":
        raise ValueError("trace is not an instrumented-oracle candidate")
    controls, records = trace.get("controls"), trace.get("branch_records")
    if not isinstance(controls, dict) or not isinstance(records, list) or not records:
        raise ValueError("trace lacks positive records and equivalence controls")
    for key in (
        "public_observation_mismatch_count", "native_boundary_mismatch_count",
        "final_rng_state_mismatch_count", "trace_replay_mismatch_count",
        "unmatched_event_count", "trace_error_count",
    ):
        if type(controls.get(key)) is not int or controls[key] != 0:
            raise ValueError(f"trace control is nonzero or malformed: {key}")
    known = {record.get("seed") for record in records if type(record.get("seed")) is int}
    if known != calibration | heldout:
        raise ValueError("preselected split must cover exactly the recorded seeds")

    split_contract = {
        "rule_id": RULE_ID,
        "calibration_seeds": sorted(calibration),
        "heldout_seeds": sorted(heldout),
    }
    calibration_score = _score(records, calibration)
    heldout_score = _score(records, heldout)
    heldout_underlay = _split_underlay(records, heldout)
    source_eligible = (
        calibration_score["comparison_count"] > 0
        and heldout_score["comparison_count"] > 0
        and calibration_score["error_count"] == 0
        and heldout_score["error_count"] == 0
    )

    # Deliberately zero: neither gold engine receives invocation-local mfndpos
    # arrays or selector results as pre-action inputs.  Positive numbers here
    # would manufacture a cross-language denominator.
    lane_records = [
        {
            "fixture_id": "scheduler-heldout-preaction-unavailable",
            "lane": lane,
            "comparison_count": 0,
            "baseline_first_divergence_step": None,
            "candidate_first_divergence_step": None,
            "baseline_error_count": 0,
            "candidate_error_count": 0,
            "blocker": "candidate arrays and selector returns are post-action source trace, not gold runtime inputs",
        }
        for lane in ("python", "rust")
    ]
    identity = trace.get("identity")
    candidate = {
        "schema": GATE_SCHEMA,
        "subsystem": "native_mfndpos_scheduler_destination_candidate",
        "validity": {
            "source_identity_pinned": isinstance(identity, dict),
            "captured_pre_action_only": False,
            "no_future_or_reset_hydration": True,
            "no_seed_or_coordinate_lookup": True,
            "source_assertion_repeatable": controls.get("two_independent_runs_exact") is True,
            "python_rust_parity": False,
            "split_frozen_before_candidate": True,
            "artifact_identity_pinned": True,
        },
        "source_assertions": {
            "comparison_count": calibration_score["comparison_count"] + heldout_score["comparison_count"],
            "error_count": calibration_score["error_count"] + heldout_score["error_count"],
        },
        "selector_conservation": {
            "outcome_membership": {
                "comparison_count": heldout_score["movement_comparison_count"],
                "error_count": heldout_score["error_count"],
            },
            "destination": {
                "comparison_count": heldout_score["comparison_count"],
                "error_count": heldout_score["error_count"],
            },
            "underlay": heldout_underlay,
        },
        "heldout": {
            "case_count": len(heldout),
            "comparison_count": 0,
            "counterexample_count": len(heldout_score["counterexamples"]),
            "baseline_first_divergence_step": None,
            "candidate_first_divergence_step": None,
            "baseline_error_count": 0,
            "candidate_error_count": 0,
            "calibration_identity_sha256": _canonical_sha256(sorted(calibration)),
            "heldout_identity_sha256": _canonical_sha256(sorted(heldout)),
            "artifact_sha256": _canonical_sha256({"identity": identity, "split": split_contract, "rule": RULE_ID}),
            "records": lane_records,
        },
        "source_export_eligible": source_eligible,
        "gold_implementation_eligible": False,
    }
    gate = evaluate_gate(candidate)
    return {
        "schema": SCHEMA,
        "status": "source_only_candidate" if source_eligible else "source_candidate_rejected",
        "fixed_before_scoring": split_contract,
        "split_contract_sha256": _canonical_sha256(split_contract),
        "hypothesis": {
            "id": RULE_ID,
            "rule": "dog_move/m_move return code 1 means a completed actor turn, not displacement. Its return-boundary coordinate may remain at its own mfndpos source; if it differs, it must equal exactly one candidate from that invocation.",
            "scope": "source-local selector invariant only; not a destination-selection algorithm",
            "nonmovement_semantics": "return_code=1 and destination==source is an eligible completed-turn observation but is excluded from any positive movement-selection denominator",
        },
        "calibration": calibration_score,
        "heldout": heldout_score,
        "heldout_underlay": heldout_underlay,
        "source_assertion_eligible": source_eligible,
        "cross_language_evaluation": lane_records,
        "promotion_candidate": candidate,
        "promotion_gate": gate,
        "gold_implementation_eligible": False,
        "implementation_blockers": gate["failures"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--calibration-seeds", required=True)
    parser.add_argument("--heldout-seeds", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-manifest", type=Path)
    args = parser.parse_args()
    parse = lambda value: [int(item) for item in value.split(",") if item]
    source = json.loads(args.trace.read_text())
    artifact_sha256 = _file_sha256(args.trace)
    split_manifest_sha256 = None
    if args.split_manifest is not None:
        manifest = json.loads(args.split_manifest.read_text())
        expected_split = {
            "rule_id": RULE_ID,
            "calibration_seeds": parse(args.calibration_seeds),
            "heldout_seeds": parse(args.heldout_seeds),
        }
        if manifest.get("fixed_before_scoring") != expected_split:
            raise ValueError("split manifest does not exactly match the requested frozen split and rule")
        split_manifest_sha256 = _file_sha256(args.split_manifest)
    trace = source.get("frontier_candidate", source)
    try:
        result = evaluate(
            trace,
            calibration_seeds=parse(args.calibration_seeds),
            heldout_seeds=parse(args.heldout_seeds),
        )
    except ValueError as error:
        # A rejected trace is still a useful durable result.  Never relax a
        # nonzero control merely to obtain a candidate score.
        result = {
            "schema": SCHEMA,
            "status": "input_trace_rejected",
            "fixed_before_scoring": {
                "rule_id": RULE_ID,
                "calibration_seeds": parse(args.calibration_seeds),
                "heldout_seeds": parse(args.heldout_seeds),
            },
            "input_artifact_sha256": _canonical_sha256(trace),
            "source_assertion_eligible": False,
            "cross_language_evaluation": [
                {"fixture_id": "scheduler-heldout-preaction-unavailable", "lane": lane, "comparison_count": 0}
                for lane in ("python", "rust")
            ],
            "heldout_nonregression": {
                "status": "not_evaluable",
                "baseline_first_divergence_step": None,
                "candidate_first_divergence_step": None,
                "baseline_error_count": None,
                "candidate_error_count": None,
                "reason": "the clean artifact does not contain the frozen heldout seeds and neither gold lane has a positive eligible denominator",
            },
            "promotion_gate": {
                "schema": GATE_SCHEMA,
                "gold_implementation_eligible": False,
                "failures": ["input_trace_prerequisite_failed", "zero_python_comparisons", "zero_rust_comparisons"],
            },
            "gold_implementation_eligible": False,
            "implementation_blockers": [str(error)],
            "source_only_underlay_diagnostic": _diagnostic_conservation(trace.get("branch_records")),
            "counterexamples": [
                {
                    "code": "input_trace_prerequisite_failed",
                    "detail": str(error),
                    "observed_control": (
                        trace.get("controls", {}).get("unmatched_event_count")
                        if isinstance(trace.get("controls"), dict) else None
                    ),
                },
                {
                    "code": "python_zero_eligible_pre_action_comparisons",
                    "count": 0,
                },
                {
                    "code": "rust_zero_eligible_pre_action_comparisons",
                    "count": 0,
                },
            ],
        }
    result["input_artifact_file_sha256"] = artifact_sha256
    result["input_artifact_path"] = str(args.trace.resolve())
    if args.split_manifest is not None:
        result["split_manifest_path"] = str(args.split_manifest.resolve())
        result["split_manifest_file_sha256"] = split_manifest_sha256
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "gold_implementation_eligible": False, "report": str(args.output.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
