"""Fail-closed promotion gate for native-assisted NetHack frontier work.

Native source access can make a diagnostic more informative without making a
gold rule valid.  This gate keeps those claims separate.  A candidate is
implementation-eligible only when it is causal, replay-exact, non-leaking,
cross-language, non-empty, and non-regressing on an independently held-out
set.  Aggregate error reduction cannot compensate for an earlier first
divergence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "gamebench.nethack.frontier_promotion_gate.v1"
REQUIRED_TRUE = (
    "source_identity_pinned",
    "captured_pre_action_only",
    "no_future_or_reset_hydration",
    "no_seed_or_coordinate_lookup",
    "source_assertion_repeatable",
    "python_rust_parity",
    "split_frozen_before_candidate",
    "artifact_identity_pinned",
)


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _zero_int(value: Any) -> bool:
    return type(value) is int and value == 0


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and len(value) == 71


def _heldout_record_failures(heldout: dict[str, Any]) -> list[str]:
    """Verify immutable identities and each fixture/lane, not just aggregates."""

    failures: list[str] = []
    for key in ("calibration_identity_sha256", "heldout_identity_sha256", "artifact_sha256"):
        if not _sha256(heldout.get(key)):
            failures.append(f"missing_{key}")
    records = heldout.get("records")
    if not isinstance(records, list) or not records:
        return failures + ["missing_heldout_records"]
    seen: set[tuple[str, str]] = set()
    lanes: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            failures.append("malformed_heldout_record")
            continue
        fixture, lane = record.get("fixture_id"), record.get("lane")
        if not isinstance(fixture, str) or not fixture or lane not in {"python", "rust"}:
            failures.append("malformed_heldout_record_identity")
            continue
        identity = (fixture, lane)
        if identity in seen:
            failures.append("duplicate_heldout_record_identity")
        seen.add(identity)
        lanes.add(lane)
        if not _positive_int(record.get("comparison_count")):
            failures.append("zero_heldout_record_comparisons")
        baseline_first = record.get("baseline_first_divergence_step")
        candidate_first = record.get("candidate_first_divergence_step")
        if baseline_first is None:
            if candidate_first is not None:
                failures.append("heldout_record_first_divergence_regression")
        elif type(baseline_first) is not int or baseline_first < 1:
            failures.append("invalid_heldout_record_baseline_first_divergence")
        elif candidate_first is not None and (
            type(candidate_first) is not int or candidate_first < baseline_first
        ):
            failures.append("heldout_record_first_divergence_regression")
        baseline_errors = record.get("baseline_error_count")
        candidate_errors = record.get("candidate_error_count")
        if type(baseline_errors) is not int or baseline_errors < 0:
            failures.append("invalid_heldout_record_baseline_errors")
        if type(candidate_errors) is not int or candidate_errors < 0:
            failures.append("invalid_heldout_record_candidate_errors")
        elif type(baseline_errors) is int and candidate_errors > baseline_errors:
            failures.append("heldout_record_error_regression")
    if lanes != {"python", "rust"}:
        failures.append("missing_cross_lane_heldout_records")
    return failures


def evaluate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return an evidence-backed, fail-closed eligibility decision."""

    failures: list[str] = []
    if candidate.get("schema") != SCHEMA:
        failures.append("schema_mismatch")
    subsystem = candidate.get("subsystem")
    if not isinstance(subsystem, str) or not subsystem:
        failures.append("missing_subsystem")
    if isinstance(subsystem, str) and "mfndpos" in subsystem:
        conservation = candidate.get("selector_conservation")
        if not isinstance(conservation, dict):
            failures.append("missing_selector_conservation")
            conservation = {}
        for plane in ("outcome_membership", "destination", "underlay"):
            evidence = conservation.get(plane)
            if not isinstance(evidence, dict):
                failures.append(f"missing_selector_{plane}_evidence")
                continue
            if not _positive_int(evidence.get("comparison_count")):
                failures.append(f"zero_selector_{plane}_comparisons")
            if not _zero_int(evidence.get("error_count")):
                failures.append(f"selector_{plane}_errors")

    validity = candidate.get("validity")
    if not isinstance(validity, dict):
        failures.append("missing_validity_contract")
        validity = {}
    for key in REQUIRED_TRUE:
        if validity.get(key) is not True:
            failures.append(f"{key}_not_proven")

    source = candidate.get("source_assertions")
    if not isinstance(source, dict):
        failures.append("missing_source_assertions")
        source = {}
    if not _positive_int(source.get("comparison_count")):
        failures.append("zero_source_comparisons")
    if not _zero_int(source.get("error_count")):
        failures.append("source_assertion_errors")

    heldout = candidate.get("heldout")
    if not isinstance(heldout, dict):
        failures.append("missing_heldout_evidence")
        heldout = {}
    if not _positive_int(heldout.get("case_count")):
        failures.append("zero_heldout_cases")
    if not _positive_int(heldout.get("comparison_count")):
        failures.append("zero_heldout_comparisons")
    if not _zero_int(heldout.get("counterexample_count")):
        failures.append("heldout_counterexamples")
    failures.extend(_heldout_record_failures(heldout))

    baseline_first = heldout.get("baseline_first_divergence_step")
    candidate_first = heldout.get("candidate_first_divergence_step")
    if baseline_first is None:
        if candidate_first is not None:
            failures.append("first_divergence_regression")
    elif type(baseline_first) is not int or baseline_first < 1:
        failures.append("invalid_baseline_first_divergence")
    elif candidate_first is not None and (
        type(candidate_first) is not int or candidate_first < baseline_first
    ):
        failures.append("first_divergence_regression")

    baseline_errors = heldout.get("baseline_error_count")
    candidate_errors = heldout.get("candidate_error_count")
    if type(baseline_errors) is not int or baseline_errors < 0:
        failures.append("invalid_baseline_error_count")
    if type(candidate_errors) is not int or candidate_errors < 0:
        failures.append("invalid_candidate_error_count")
    elif type(baseline_errors) is int and candidate_errors > baseline_errors:
        failures.append("heldout_error_regression")

    source_assertion_eligible = (
        _positive_int(source.get("comparison_count"))
        and _zero_int(source.get("error_count"))
        and validity.get("source_identity_pinned") is True
        and validity.get("captured_pre_action_only") is True
    )
    # Old candidates predate the explicit source-export field.  Preserve
    # their source assertion result while ensuring every newly emitted gate
    # report says separately whether source export and gold implementation are
    # eligible.  A source export can be eligible while the gold rule remains
    # blocked by held-out counterexamples.
    source_export_eligible = bool(candidate.get("source_export_eligible", source_assertion_eligible)) and source_assertion_eligible
    if not source_export_eligible:
        failures.append("source_export_not_eligible")

    claimed = candidate.get("gold_implementation_eligible")
    eligible = not failures
    if claimed is not eligible:
        failures.append("claimed_eligibility_mismatch")
        eligible = False

    return {
        "schema": SCHEMA,
        "subsystem": subsystem,
        "source_assertion_eligible": source_assertion_eligible,
        "source_export_eligible": source_export_eligible,
        "gold_implementation_eligible": eligible,
        "failures": failures,
        "heldout": heldout,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = evaluate(json.loads(args.candidate.read_text()))
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload)
    print(payload, end="")
    raise SystemExit(0 if result["gold_implementation_eligible"] else 1)


if __name__ == "__main__":
    main()
