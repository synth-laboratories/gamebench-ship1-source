#!/usr/bin/env python3
"""Summarize the strict bedroom acceptance gate from a differential-fuzz report.

This is intentionally a *reader*, rather than another oracle runner.  The
frame-by-frame source comparison remains owned by ``fuzz_emerald_differential``;
this command makes its bedroom completion criteria hard to misread:

* every named bedroom fixture must be exact;
* every seeded random bedroom tape must be exact; and
* failures are attributed conservatively as renderer, scheduler, or warp.

``warp`` requires a source/Rust map disagreement at a semantic boundary.
``scheduler`` requires a semantic disagreement without such a map change.
Everything else is ``renderer``: a pixel-only failure.  These labels are
evidence classifications, not a claim about the underlying mGBA task code.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


# This is deliberately fixed.  Changing the bedroom corpus or its acceptance
# surface must be an explicit review decision, not an accidental weakening of
# the regression gate.
EXPECTED_BEDROOM_GATE = {
    "tapes": 26,
    "compared_vblanks": 1687,
    "state_checks": 977,
    "transport_contracts": 21,
}


def oracle_lane(report: dict[str, Any]) -> dict[str, Any]:
    for lane in report.get("lanes", []):
        if lane.get("lane") == "source_behavior_oracle":
            return lane
    raise ValueError("report has no source_behavior_oracle lane")


def transport_lane(report: dict[str, Any]) -> dict[str, Any]:
    for lane in report.get("lanes", []):
        if lane.get("lane") == "rust_transport_contract":
            return lane
    raise ValueError("report has no rust_transport_contract lane")


def semantic_failures(case: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        tick
        for tick in case.get("proof_tape", [])
        if tick.get("semantic_equal") is False
    ]


def map_of(value: Any) -> Any:
    return value.get("map") if isinstance(value, dict) else None


def classify(case: dict[str, Any]) -> tuple[str, str, int | None]:
    """Return (owner, evidence, first semantic mismatch VBlank)."""
    failures = semantic_failures(case)
    first_semantic = failures[0] if failures else None
    if first_semantic is not None:
        source_map = map_of(first_semantic.get("source_semantic"))
        rust_map = map_of(first_semantic.get("rust_semantic"))
        if source_map is not None and rust_map is not None and source_map != rust_map:
            return (
                "warp",
                f"semantic boundary map mismatch: source={source_map}, rust={rust_map}",
                int(first_semantic["vblank"]),
            )
        return (
            "scheduler",
            "semantic boundary mismatch without a map identity disagreement",
            int(first_semantic["vblank"]),
        )
    if case.get("pixel_mismatch_frames", 0):
        return (
            "renderer",
            "pixel mismatch with no observed semantic-boundary mismatch",
            None,
        )
    return ("exact", "all compared VBlanks and semantic boundaries match", None)


def summarize_case(case: dict[str, Any]) -> dict[str, Any]:
    owner, evidence, first_semantic = classify(case)
    first = case.get("first_mismatch") or {}
    return {
        "name": case.get("name"),
        "origin": case.get("origin"),
        "result": case.get("result"),
        "frames": case.get("compared_source_frames", 0),
        "pixel_mismatch_frames": case.get("pixel_mismatch_frames", 0),
        "semantic_boundary_mismatches": case.get("semantic_boundary_mismatches", 0),
        "first_pixel_or_semantic_vblank": first.get("vblank"),
        "first_semantic_vblank": first_semantic,
        "owner": owner,
        "evidence": evidence,
    }


def gate_summary(report: dict[str, Any]) -> dict[str, Any]:
    lane = oracle_lane(report)
    transport = transport_lane(report)
    cases = [summarize_case(case) for case in lane.get("cases", [])]
    random_cases = [case for case in cases if case["origin"] == "deterministic random fuzz"]
    mandatory_cases = [case for case in cases if case not in random_cases]
    failures = [case for case in cases if case["result"] != "exact"]
    owners = Counter(case["owner"] for case in failures)
    state_checks = sum(
        1
        for case in lane.get("cases", [])
        for tick in case.get("proof_tape", [])
        if tick.get("semantic_comparable") is True
    )
    counts = {
        "mandatory": len(mandatory_cases),
        "mandatory_exact": sum(case["result"] == "exact" for case in mandatory_cases),
        "random": len(random_cases),
        "random_exact": sum(case["result"] == "exact" for case in random_cases),
        "tapes": len(cases),
        "compared_vblanks": sum(case["frames"] for case in cases),
        "state_checks": state_checks,
        "pixel_mismatch_frames": sum(case["pixel_mismatch_frames"] for case in cases),
        "semantic_boundary_mismatches": sum(case["semantic_boundary_mismatches"] for case in cases),
        "transport_contracts": int(transport.get("case_count", 0)),
        "transport_violations": int(transport.get("violation_count", 0)),
        "failures_by_owner": dict(sorted(owners.items())),
    }
    count_failures = {
        key: {"expected": expected, "actual": counts[key]}
        for key, expected in EXPECTED_BEDROOM_GATE.items()
        if counts[key] != expected
    }
    exact_failures = {
        "pixel_mismatch_frames": counts["pixel_mismatch_frames"],
        "semantic_boundary_mismatches": counts["semantic_boundary_mismatches"],
        "transport_violations": counts["transport_violations"],
    }
    return {
        "schema": "gamebench.pokemon_emerald.bedroom_gate.v1",
        "oracle_checkpoint": lane.get("oracle_checkpoint"),
        "report_identity": {
            "source_report": report.get("output") or report.get("report_path"),
            "rom_sha256": lane.get("rom_sha256"),
            "state_sha256": lane.get("state_sha256"),
            "oracle_registry_sha256": lane.get("oracle_registry_sha256"),
        },
        "acceptance": {
            "mandatory_fixtures_exact": not any(case["result"] != "exact" for case in mandatory_cases),
            "random_bedroom_tapes_exact": not any(case["result"] != "exact" for case in random_cases),
            "counts_exact": not count_failures,
            "pixels_and_states_exact": not any(exact_failures.values()),
            "gate_passed": not failures and not count_failures and not any(exact_failures.values()),
            "rule": "26 tapes, 1687 compared VBlanks, 977 state checks, 21 transport contracts, and zero mismatches",
        },
        "expected": EXPECTED_BEDROOM_GATE,
        "counts": counts,
        "count_failures": count_failures,
        "exact_failures": exact_failures,
        "mandatory": mandatory_cases,
        "random": random_cases,
        "failures": failures,
        "classification_note": (
            "warp is reserved for a semantic-boundary map disagreement; scheduler is a "
            "same-map semantic disagreement; renderer is pixel-only evidence."
        ),
    }


def print_table(summary: dict[str, Any]) -> None:
    counts = summary["counts"]
    acceptance = summary["acceptance"]
    print("Bedroom gate")
    print(
        "mandatory {}/{} exact | random {}/{} exact | tapes {}/{} | frames {}/{} | states {}/{} | transport {}/{} | pixel errors {} | semantic errors {}".format(
            counts["mandatory_exact"], counts["mandatory"],
            counts["random_exact"], counts["random"],
            counts["tapes"], EXPECTED_BEDROOM_GATE["tapes"],
            counts["compared_vblanks"], EXPECTED_BEDROOM_GATE["compared_vblanks"],
            counts["state_checks"], EXPECTED_BEDROOM_GATE["state_checks"],
            counts["transport_contracts"], EXPECTED_BEDROOM_GATE["transport_contracts"],
            counts["pixel_mismatch_frames"],
            counts["semantic_boundary_mismatches"],
        )
    )
    print("result: " + ("PASS" if acceptance["gate_passed"] else "BLOCKED"))
    for key, values in summary["count_failures"].items():
        print(f"count mismatch: {key} expected {values['expected']}, got {values['actual']}")
    for key, value in summary["exact_failures"].items():
        if value:
            print(f"exactness failure: {key}={value}")
    print()
    print("case\tfirst\tsemantic\tpixel_frames\tstate_errors\towner\tevidence")
    for case in summary["failures"]:
        print(
            "{name}\t{first}\t{semantic}\t{pixels}\t{states}\t{owner}\t{evidence}".format(
                name=case["name"],
                first=case["first_pixel_or_semantic_vblank"] if case["first_pixel_or_semantic_vblank"] is not None else "—",
                semantic=case["first_semantic_vblank"] if case["first_semantic_vblank"] is not None else "—",
                pixels=case["pixel_mismatch_frames"],
                states=case["semantic_boundary_mismatches"],
                owner=case["owner"],
                evidence=case["evidence"],
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="differential fuzz JSON report")
    parser.add_argument("--output", type=Path, help="write JSON summary (refuses overwrite)")
    args = parser.parse_args()
    try:
        report = json.loads(args.input.read_text(encoding="utf-8"))
        summary = gate_summary(report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"bedroom gate error: {exc}", file=sys.stderr)
        return 2
    if args.output:
        if args.output.exists():
            print(f"bedroom gate error: refusing to overwrite {args.output}", file=sys.stderr)
            return 2
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    print_table(summary)
    return 0 if summary["acceptance"]["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
