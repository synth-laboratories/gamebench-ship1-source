#!/usr/bin/env python3
"""Fail closed on the authenticated Route 101 wild-entry handoff gate.

The gate intentionally covers only the closed, source-exact entry segment:
the idle encounter message/trainer rail and the released-A send-out through
the command boundary. Random input tapes are tracked separately until battle
turn ownership is source-exact; they must not silently turn this narrow gate
green or change its corpus.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


EXPECTED = {
    "checkpoint": "route101_wild_battle",
    "segment": "route101_wild_battle",
    "tapes": 2,
    "frames": 127,
    "state_checks": 5,
    # The scoped run uses the five mandatory transport partitions.  The
    # broader 21-case transport corpus remains frozen by the bedroom/Mays
    # gates; this segment gate must not add unrelated random source tapes.
    "transport": 5,
}


def lane(report: dict[str, Any], name: str) -> dict[str, Any]:
    for item in report.get("lanes", []):
        if item.get("lane") == name:
            return item
    raise ValueError(f"report has no {name} lane")


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    source = lane(report, "source_behavior_oracle")
    transport = lane(report, "rust_transport_contract")
    cases = list(source.get("cases", []))
    states = sum(
        1
        for case in cases
        for tick in case.get("proof_tape", [])
        if tick.get("semantic_comparable") is True
    )
    counts = {
        "tapes": len(cases),
        "frames": sum(int(case.get("compared_source_frames", 0)) for case in cases),
        "state_checks": states,
        "transport": int(transport.get("case_count", 0)),
        "pixel_errors": int(source.get("pixel_mismatch_frames", 0)),
        "semantic_errors": int(source.get("semantic_boundary_mismatches", 0)),
        "tape_divergences": sum(case.get("result") != "exact" for case in cases),
    }
    identity = {
        "checkpoint": source.get("oracle_checkpoint"),
        "segment": source.get("coverage_segment"),
    }
    acceptance = {
        "identity_exact": identity == {
            "checkpoint": EXPECTED["checkpoint"],
            "segment": EXPECTED["segment"],
        },
        "counts_exact": all(counts[key] == EXPECTED[key] for key in ("tapes", "frames", "state_checks", "transport")),
        "exact": not any(counts[key] for key in ("pixel_errors", "semantic_errors", "tape_divergences")),
    }
    acceptance["gate_passed"] = all(acceptance.values())
    return {"schema": "gamebench.pokemon_emerald.route101_wild_gate.v1", "expected": EXPECTED, "identity": identity, "counts": counts, "acceptance": acceptance}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = summarize(json.loads(args.input.read_text()))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: cannot validate Route 101 wild gate: {exc}", file=sys.stderr)
        return 2
    c = summary["counts"]
    e = summary["expected"]
    print(
        "Route 101 wild gate: tapes {}/{} | frames {}/{} | states {}/{} | "
        "transport {}/{} | pixel errors {} | semantic errors {} | result {}".format(
            c["tapes"], e["tapes"], c["frames"], e["frames"], c["state_checks"], e["state_checks"],
            c["transport"], e["transport"], c["pixel_errors"], c["semantic_errors"],
            "PASS" if summary["acceptance"]["gate_passed"] else "BLOCKED",
        )
    )
    return 0 if summary["acceptance"]["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
