"""Fail-closed equivalence gate for an instrumented NLE source oracle.

An instrumented build is not authoritative merely because it came from the
same source commit.  It must reproduce the pinned wheel's public observations,
native source boundaries, and final RNG state over non-empty independent
controls.  Trace events are source evidence only and cannot enter either gold
engine or a conformance denominator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "gamebench.nethack.instrumented_oracle_equivalence.v1"
PINNED_SOURCE_COMMIT = "2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa"
PINNED_BINARY_SHA256 = "7ac1270dfd5fa0a5fb2f715ef6a7151058f06cda595e4b722ac6d070ce0f2057"


def _positive(value: Any) -> bool:
    return type(value) is int and value > 0


def _zero(value: Any) -> bool:
    """Accept only an explicitly measured integer zero, never ``False``."""

    return type(value) is int and value == 0


def evaluate(candidate: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if candidate.get("schema") != SCHEMA:
        failures.append("schema_mismatch")
    identity = candidate.get("identity")
    if not isinstance(identity, dict):
        failures.append("missing_identity")
        identity = {}
    if identity.get("source_commit") != PINNED_SOURCE_COMMIT:
        failures.append("source_commit_mismatch")
    if identity.get("baseline_binary_sha256") != PINNED_BINARY_SHA256:
        failures.append("baseline_binary_mismatch")
    for key in ("instrumented_binary_sha256", "toolchain_identity_sha256", "patch_sha256"):
        if not isinstance(identity.get(key), str) or not identity[key]:
            failures.append(f"missing_{key}")

    controls = candidate.get("controls")
    if not isinstance(controls, dict):
        failures.append("missing_controls")
        controls = {}
    for key in ("independent_seed_count", "transition_count", "trace_event_count"):
        if not _positive(controls.get(key)):
            failures.append(f"zero_{key}")
    for key in (
        "public_observation_mismatch_count",
        "native_boundary_mismatch_count",
        "final_rng_state_mismatch_count",
        "trace_replay_mismatch_count",
    ):
        if not _zero(controls.get(key)):
            failures.append(key.removesuffix("_count") + "es")
    if controls.get("two_independent_runs_exact") is not True:
        failures.append("instrumented_trace_not_repeatable")

    validity = candidate.get("validity")
    if not isinstance(validity, dict):
        failures.append("missing_validity")
        validity = {}
    for key in (
        "inputs_selected_before_results",
        "trace_read_only_from_gold_perspective",
        "trace_excluded_from_gold_runtime",
        "trace_excluded_from_conformance_denominator",
        "zero_and_unmatched_events_fail_closed",
    ):
        if validity.get(key) is not True:
            failures.append(f"{key}_not_proven")

    claimed = candidate.get("instrumented_source_oracle_eligible")
    eligible = not failures
    if claimed is not eligible:
        failures.append("claimed_eligibility_mismatch")
        eligible = False
    return {
        "schema": SCHEMA,
        "instrumented_source_oracle_eligible": eligible,
        "gold_implementation_eligible": False,
        "failures": failures,
        "controls": controls,
        "contract": "Instrumented traces are source evidence only; gold promotion requires a separate frontier gate.",
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
    raise SystemExit(0 if result["instrumented_source_oracle_eligible"] else 1)


if __name__ == "__main__":
    main()
