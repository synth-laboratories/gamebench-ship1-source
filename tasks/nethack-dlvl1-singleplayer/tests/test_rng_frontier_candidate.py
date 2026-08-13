"""The native RNG frontier must remain assertion-only until ownership exists."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.emit_rng_frontier_candidate import build_candidate
from scripts.frontier_promotion_gate import evaluate
from scripts.nle_rng_state import EXPECTED_CONTEXT_SIZE, PINNED_BINARY_SHA256


def raw_rng_record() -> dict[str, object]:
    state = bytes(EXPECTED_CONTEXT_SIZE)
    lane = {
        "n": 0,
        "byte_length": EXPECTED_CONTEXT_SIZE,
        "state_hex": state.hex(),
        "state_sha256": hashlib.sha256(state).hexdigest(),
    }
    return {
        "schema": "gamebench.nethack.authoritative_rng_snapshot.v1",
        "binary_sha256": PINNED_BINARY_SHA256,
        "core": lane,
        "display": dict(lane),
    }


def reports() -> tuple[dict[str, object], dict[str, object]]:
    rng = {
        "schema": "gamebench.nethack.authoritative_rng_report.v1",
        "status": "pass",
        "summary": {"exact_raw_state_call_chronology": True, "wall_kick_cases": 3},
        "cases": [
            {"before": raw_rng_record(), "after": raw_rng_record()}
            for _ in range(3)
        ],
    }
    steps = [
        {
            "rng": {
                "before": raw_rng_record(),
                "after": raw_rng_record(),
                "core_calls_exact_raw_state": 2,
                "core_calls_bounded_index": 2,
                "display_calls_exact_raw_state": 0,
                "display_calls_bounded_index": 0,
            }
        }
        for _ in range(2)
    ]
    scheduler = {
        "schema": "gamebench.nethack.native_causal_scheduler_probe.v2",
        "status": "assertion_only_gold_blocked",
        "two_independent_runs_exact": True,
        "rng_eligibility": {
            "source_assertion_eligible": True,
            "gold_rng_or_branch_implementation_eligible": False,
        },
        "heldout_seed_count": 3,
        "cases": [{"steps": steps} for _ in range(3)],
        "exact_rng_lane_comparisons": 12,
    }
    return rng, scheduler


class RngFrontierCandidateTests(unittest.TestCase):
    def test_exact_source_chronology_is_not_gold_rng_eligibility(self) -> None:
        rng, scheduler = reports()
        candidate = build_candidate(rng, scheduler)
        decision = evaluate(candidate)
        self.assertTrue(candidate["source_assertion_eligible"])
        self.assertFalse(candidate["gold_rng_or_branch_implementation_eligible"])
        self.assertTrue(decision["source_assertion_eligible"])
        self.assertFalse(decision["gold_implementation_eligible"])
        self.assertIn("python_rust_parity_not_proven", decision["failures"])
        self.assertIn("heldout_counterexamples", decision["failures"])

    def test_zero_exact_scheduler_comparisons_fail_closed(self) -> None:
        rng, scheduler = reports()
        scheduler["exact_rng_lane_comparisons"] = 0
        with self.assertRaisesRegex(ValueError, "zero exact RNG"):
            build_candidate(rng, scheduler)

    def test_mismatched_or_summary_only_scheduler_handoff_fails_closed(self) -> None:
        rng, scheduler = reports()
        scheduler["cases"][0]["steps"][0]["rng"]["after"]["binary_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "exact pinned NLE binary"):
            build_candidate(rng, scheduler)

        rng, scheduler = reports()
        scheduler["exact_rng_lane_comparisons"] = 11
        with self.assertRaisesRegex(ValueError, "does not match"):
            build_candidate(rng, scheduler)

        rng, scheduler = reports()
        scheduler.pop("cases")
        with self.assertRaisesRegex(ValueError, "complete held-out"):
            build_candidate(rng, scheduler)


if __name__ == "__main__":
    unittest.main()
