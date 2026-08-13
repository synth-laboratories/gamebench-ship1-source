#!/usr/bin/env python3
"""Validate the authenticated Mays House 1F/Mom/exit regression gate.

The differential fuzzer owns the frame-by-frame comparison.  This reader
keeps the acceptance surface explicit so a future corpus edit cannot make a
smaller run look like a passing regression test.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


EXPECTED_MAYS_HOUSE_GATE = {
    "tapes": 18,
    "compared_vblanks": 6384,
    "state_checks": 968,
    "transport_contracts": 21,
}


def _lane(report: dict[str, Any], name: str) -> dict[str, Any]:
    for lane in report.get("lanes", []):
        if lane.get("lane") == name:
            return lane
    raise ValueError(f"report has no {name} lane")


def gate_summary(report: dict[str, Any]) -> dict[str, Any]:
    source = _lane(report, "source_behavior_oracle")
    transport = _lane(report, "rust_transport_contract")
    cases = list(source.get("cases", []))
    random_cases = [
        case for case in cases if case.get("origin") == "deterministic random fuzz"
    ]
    mandatory_cases = [case for case in cases if case not in random_cases]
    counts = {
        "mandatory": len(mandatory_cases),
        "mandatory_exact": sum(case.get("result") == "exact" for case in mandatory_cases),
        "random": len(random_cases),
        "random_exact": sum(case.get("result") == "exact" for case in random_cases),
        "tapes": len(cases),
        "compared_vblanks": sum(int(case.get("compared_source_frames", 0)) for case in cases),
        "state_checks": sum(
            1
            for case in cases
            for tick in case.get("proof_tape", [])
            if tick.get("semantic_comparable") is True
        ),
        "pixel_mismatch_frames": sum(int(case.get("pixel_mismatch_frames", 0)) for case in cases),
        "semantic_boundary_mismatches": sum(
            int(case.get("semantic_boundary_mismatches", 0)) for case in cases
        ),
        "transport_contracts": int(transport.get("case_count", 0)),
        "transport_violations": int(transport.get("violation_count", 0)),
    }
    count_failures = {
        key: {"expected": expected, "actual": counts[key]}
        for key, expected in EXPECTED_MAYS_HOUSE_GATE.items()
        if counts[key] != expected
    }
    exact_failures = {
        "case_divergences": sum(case.get("result") != "exact" for case in cases),
        "pixel_mismatch_frames": counts["pixel_mismatch_frames"],
        "semantic_boundary_mismatches": counts["semantic_boundary_mismatches"],
        "transport_violations": counts["transport_violations"],
    }
    acceptance = {
        "checkpoint_exact": source.get("oracle_checkpoint") == "bedroom_idle",
        "segment_exact": source.get("coverage_segment") == "mays_house_exit",
        "mandatory_tapes_exact": counts["mandatory_exact"] == counts["mandatory"],
        "random_tapes_exact": counts["random_exact"] == counts["random"],
        "counts_exact": not count_failures,
        "pixels_and_states_exact": not any(exact_failures.values()),
    }
    acceptance["gate_passed"] = all(acceptance.values())
    return {
        "schema": "gamebench.pokemon_emerald.mays_house_gate.v1",
        "acceptance": acceptance,
        "expected": EXPECTED_MAYS_HOUSE_GATE,
        "counts": counts,
        "count_failures": count_failures,
        "exact_failures": exact_failures,
        "report_identity": {
            "oracle_checkpoint": source.get("oracle_checkpoint"),
            "coverage_segment": source.get("coverage_segment"),
            "rom_sha256": source.get("rom_sha256"),
            "state_sha256": source.get("state_sha256"),
            "oracle_registry_sha256": source.get("oracle_registry_sha256"),
        },
    }


def print_summary(summary: dict[str, Any]) -> None:
    counts = summary["counts"]
    expected = summary["expected"]
    acceptance = summary["acceptance"]
    print(
        "Mays House gate: mandatory {}/{} exact | random {}/{} exact | "
        "tapes {}/{} | frames {}/{} | states {}/{} | transport {}/{} | "
        "pixel errors {} | semantic errors {} | result {}".format(
            counts["mandatory_exact"],
            counts["mandatory"],
            counts["random_exact"],
            counts["random"],
            counts["tapes"],
            expected["tapes"],
            counts["compared_vblanks"],
            expected["compared_vblanks"],
            counts["state_checks"],
            expected["state_checks"],
            counts["transport_contracts"] - counts["transport_violations"],
            expected["transport_contracts"],
            counts["pixel_mismatch_frames"],
            counts["semantic_boundary_mismatches"],
            "PASS" if acceptance["gate_passed"] else "BLOCKED",
        )
    )
    for key, values in summary["count_failures"].items():
        print(f"count mismatch: {key} expected {values['expected']}, got {values['actual']}")
    for key, value in summary["exact_failures"].items():
        if value:
            print(f"exactness failure: {key}={value}")
    for key in ("checkpoint_exact", "segment_exact"):
        if not acceptance[key]:
            print(f"identity failure: {key}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="differential fuzz JSON report")
    parser.add_argument("--output", type=Path, help="optional JSON summary; refuses overwrite")
    args = parser.parse_args()
    try:
        report = json.loads(args.input.read_text())
        summary = gate_summary(report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: cannot validate Mays House report: {exc}", file=sys.stderr)
        return 2
    print_summary(summary)
    if args.output is not None:
        if args.output.exists():
            print(f"error: refusing to overwrite existing summary: {args.output}", file=sys.stderr)
            return 2
        args.output.write_text(json.dumps(summary, indent=2) + "\n")
    return 0 if summary["acceptance"]["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
