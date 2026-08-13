#!/usr/bin/env python3
"""Emit a fail-closed promotion-gate candidate for native RNG chronology.

An exact raw ISAAC64 transition establishes an oracle assertion: it does not
say which call site consumed a value, nor make the native state legal gold
input.  The emitted candidate deliberately carries counterexamples so a
``pass`` source probe cannot be mistaken for permission to implement combat,
KICK injury, or a monster scheduler.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.frontier_promotion_gate import SCHEMA, evaluate
from scripts.nle_rng_state import PINNED_BINARY_SHA256, validate_rng_record


SOURCE_COMMIT = "2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa"
SOURCE_BRANCHES = {
    "wall_kick_injury": {
        "source": "src/dokick.c:1227-1244",
        "calls": [
            "rn2(3) conditionally enters the wounded-legs branch",
            "rnd(5) runs only when that condition is true",
            "rnd(CON > 15 ? 3 : 5) always selects immediate injury magnitude",
        ],
    },
    "scheduler": {
        "source": "src/monmove.c, src/dogmove.c",
        "calls": [
            "movemon/do_chug/m_move choose paths through many state-conditional rn2 calls",
            "dog movement may consume apport, pickup/drop, combat, and path-selection draws",
        ],
    },
    "combat": {
        "source": "src/uhitm.c",
        "calls": ["to-hit, damage, weapons, effects, and reactive monster branches each own conditional rn2 calls"],
    },
}

RNG_REPORT_SCHEMA = "gamebench.nethack.authoritative_rng_report.v1"
# The current producer emits a causal v2 report.  It contains complete
# action-bound source cells/entity transitions *and* exact raw ISAAC64
# boundaries; accepting the old v1 summary shape would permit stale totals to
# reach this handoff without the stronger causal scheduler checks.
SCHEDULER_REPORT_SCHEMA = "gamebench.nethack.native_causal_scheduler_probe.v2"
SCHEDULER_REPORT_STATUS = "assertion_only_gold_blocked"


def _require(report: dict[str, Any], key: str) -> Any:
    value = report.get(key)
    if value is None:
        raise ValueError(f"report lacks {key}")
    return value


def _require_pinned_binary(value: Any, *, context: str) -> str:
    if value != PINNED_BINARY_SHA256:
        raise ValueError(f"{context} does not bind the exact pinned NLE binary")
    return str(value)


def _validate_rng_report(rng_report: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Accept only the complete pinned RNG report, not a summary-shaped stub."""

    if rng_report.get("schema") != RNG_REPORT_SCHEMA or rng_report.get("status") != "pass":
        raise ValueError("RNG report must be a passing authoritative_rng_report.v1")
    summary = _require(rng_report, "summary")
    if not isinstance(summary, dict) or summary.get("exact_raw_state_call_chronology") is not True:
        raise ValueError("RNG report does not prove exact full-state chronology")
    rng_cases = _require(rng_report, "cases")
    if not isinstance(rng_cases, list) or not rng_cases:
        raise ValueError("RNG report has zero source cases")
    binary_hashes: set[str] = set()
    for index, case in enumerate(rng_cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"RNG report case {index} is malformed")
        for boundary in ("before", "after"):
            record = case.get(boundary)
            if not isinstance(record, dict):
                raise ValueError(f"RNG report case {index} lacks {boundary} raw state")
            binary_hashes.add(_require_pinned_binary(record.get("binary_sha256"), context=f"RNG report case {index} {boundary}"))
            failures = validate_rng_record(record)
            if failures:
                raise ValueError(f"RNG report case {index} has invalid {boundary} raw state: {'; '.join(failures)}")
    if len(binary_hashes) != 1:
        raise ValueError("RNG report mixes native binary identities")
    wall_cases = summary.get("wall_kick_cases")
    if type(wall_cases) is not int or wall_cases <= 0:
        raise ValueError("RNG report has zero wall-KICK cases")
    return rng_cases, summary, binary_hashes.pop()


def _validate_scheduler_report(scheduler_report: dict[str, Any], *, binary_sha256: str) -> int:
    """Verify every exact scheduler lane count before aggregating it.

    The report remains source evidence, but its count must be derived from
    action-bound raw before/after records that share the same pinned binary as
    the independent RNG report.  A copied total or an old summary cannot
    become promotion evidence by itself.
    """

    if (
        scheduler_report.get("schema") != SCHEDULER_REPORT_SCHEMA
        or scheduler_report.get("status") != SCHEDULER_REPORT_STATUS
    ):
        raise ValueError("scheduler report must be a current assertion-only native_causal_scheduler_probe.v2")
    if scheduler_report.get("two_independent_runs_exact") is not True:
        raise ValueError("scheduler report lacks exact independent replay")
    eligibility = scheduler_report.get("rng_eligibility")
    if not isinstance(eligibility, dict) or eligibility.get("source_assertion_eligible") is not True:
        raise ValueError("scheduler report is not source-assertion eligible for RNG boundaries")
    if eligibility.get("gold_rng_or_branch_implementation_eligible") is not False:
        raise ValueError("scheduler report must explicitly deny gold RNG/branch eligibility")
    cases = scheduler_report.get("cases")
    heldout_seed_count = scheduler_report.get("heldout_seed_count")
    if not isinstance(cases, list) or not cases or type(heldout_seed_count) is not int or heldout_seed_count < 3 or len(cases) != heldout_seed_count:
        raise ValueError("scheduler report lacks three or more complete held-out source cases")
    exact_lane_comparisons = 0
    for case_index, case in enumerate(cases, start=1):
        steps = case.get("steps") if isinstance(case, dict) else None
        if not isinstance(steps, list) or not steps:
            raise ValueError(f"scheduler report case {case_index} has zero action boundaries")
        for step_index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise ValueError(f"scheduler report case {case_index} step {step_index} is malformed")
            rng = step.get("rng")
            if not isinstance(rng, dict):
                raise ValueError(f"scheduler report case {case_index} step {step_index} lacks RNG boundary")
            for boundary in ("before", "after"):
                record = rng.get(boundary)
                if not isinstance(record, dict):
                    raise ValueError(f"scheduler report case {case_index} step {step_index} lacks RNG {boundary} state")
                _require_pinned_binary(record.get("binary_sha256"), context=f"scheduler report case {case_index} step {step_index} RNG {boundary}")
                if record.get("binary_sha256") != binary_sha256:
                    raise ValueError("scheduler and independent RNG reports use different native binaries")
                failures = validate_rng_record(record)
                if failures:
                    raise ValueError(
                        f"scheduler report case {case_index} step {step_index} has invalid RNG {boundary} raw state: "
                        + "; ".join(failures)
                    )
            for lane in ("core", "display"):
                exact = rng.get(f"{lane}_calls_exact_raw_state")
                bounded = rng.get(f"{lane}_calls_bounded_index")
                if type(exact) is not int or exact < 0 or exact != bounded:
                    raise ValueError(f"scheduler report case {case_index} step {step_index} has unauditable {lane} RNG chronology")
                exact_lane_comparisons += 1
    reported_comparisons = scheduler_report.get("exact_rng_lane_comparisons")
    if type(reported_comparisons) is not int or reported_comparisons <= 0:
        raise ValueError("scheduler report has zero exact RNG comparisons")
    if reported_comparisons != exact_lane_comparisons:
        raise ValueError(
            "scheduler report exact RNG comparison total does not match its action-bound raw lane records"
        )
    return exact_lane_comparisons


def build_candidate(rng_report: dict[str, Any], scheduler_report: dict[str, Any]) -> dict[str, Any]:
    """Build an intentionally non-promotable, source-assertion candidate."""

    rng_cases, summary, binary_sha256 = _validate_rng_report(rng_report)
    scheduler_comparisons = _validate_scheduler_report(scheduler_report, binary_sha256=binary_sha256)
    wall_cases = summary["wall_kick_cases"]

    comparisons = len(rng_cases) * 2 + wall_cases * 2 + scheduler_comparisons
    counterexamples = [
        {
            "code": "wall_kick_branch_count_is_not_branch_ownership",
            "evidence": "same direct-wall KICK source branch has conditional rn2(3)/rnd(5) plus always rnd(CON...) and whole-turn scheduler draws",
        },
        {
            "code": "scheduler_actor_population_and_state_change_call_order",
            "evidence": "native entity snapshots prove population at a boundary but no controlled mutation is allowed; movemon/dogmove inspect unexported target/path/status state",
        },
        {
            "code": "gold_cannot_receive_native_rng_sidecar",
            "evidence": "native pre-action policy forbids gold runtime input, reset hydration, and conformance-denominator use",
        },
    ]
    return {
        "schema": SCHEMA,
        "subsystem": "native_rng_scheduler_combat_kick",
        "source_identity": {"nethack_commit": SOURCE_COMMIT, "binary_sha256": binary_sha256},
        "validity": {
            "source_identity_pinned": True,
            "captured_pre_action_only": True,
            "no_future_or_reset_hydration": True,
            "no_seed_or_coordinate_lookup": True,
            "source_assertion_repeatable": True,
            # No candidate behavior exists to run in both lanes.  Treat this
            # as a missing proof, rather than reusing ordinary engine parity.
            "python_rust_parity": False,
        },
        "source_assertions": {
            "comparison_count": comparisons,
            "error_count": 0,
            "source_rng_observable": True,
            "exact_raw_state_replay": True,
            "ownership_scope": "whole action and per-lane only",
        },
        "heldout": {
            "case_count": int(scheduler_report.get("heldout_seed_count", 0)),
            "comparison_count": scheduler_comparisons,
            "counterexample_count": len(counterexamples),
            "counterexamples": counterexamples,
            "baseline_first_divergence_step": 1,
            "candidate_first_divergence_step": 1,
            "baseline_error_count": 0,
            "candidate_error_count": 0,
        },
        "source_branch_inventory": SOURCE_BRANCHES,
        "source_assertion_eligible": True,
        "gold_rng_or_branch_implementation_eligible": False,
        "gold_implementation_eligible": False,
        "implementation_blockers": [entry["code"] for entry in counterexamples],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rng-report", type=Path, required=True)
    parser.add_argument("--scheduler-report", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--gate-report", type=Path, required=True)
    args = parser.parse_args()
    candidate = build_candidate(json.loads(args.rng_report.read_text()), json.loads(args.scheduler_report.read_text()))
    decision = evaluate(candidate)
    if not decision["source_assertion_eligible"] or decision["gold_implementation_eligible"]:
        raise SystemExit("RNG candidate validity contract unexpectedly changed")
    args.candidate.parent.mkdir(parents=True, exist_ok=True)
    args.gate_report.parent.mkdir(parents=True, exist_ok=True)
    args.candidate.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n")
    args.gate_report.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "source_assertion_eligible": decision["source_assertion_eligible"],
        "gold_implementation_eligible": decision["gold_implementation_eligible"],
        "blockers": candidate["implementation_blockers"],
        "candidate": str(args.candidate.resolve()),
        "gate_report": str(args.gate_report.resolve()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
