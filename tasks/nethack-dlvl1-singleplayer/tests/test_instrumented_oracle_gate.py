from __future__ import annotations

import copy
import unittest

from scripts.instrumented_oracle_gate import (
    PINNED_BINARY_SHA256,
    PINNED_SOURCE_COMMIT,
    SCHEMA,
    evaluate,
)


def candidate() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "identity": {
            "source_commit": PINNED_SOURCE_COMMIT,
            "baseline_binary_sha256": PINNED_BINARY_SHA256,
            "instrumented_binary_sha256": "instrumented",
            "toolchain_identity_sha256": "toolchain",
            "patch_sha256": "patch",
        },
        "controls": {
            "independent_seed_count": 6,
            "transition_count": 30,
            "trace_event_count": 20,
            "public_observation_mismatch_count": 0,
            "native_boundary_mismatch_count": 0,
            "final_rng_state_mismatch_count": 0,
            "trace_replay_mismatch_count": 0,
            "two_independent_runs_exact": True,
        },
        "validity": {
            "inputs_selected_before_results": True,
            "trace_read_only_from_gold_perspective": True,
            "trace_excluded_from_gold_runtime": True,
            "trace_excluded_from_conformance_denominator": True,
            "zero_and_unmatched_events_fail_closed": True,
        },
        "instrumented_source_oracle_eligible": True,
    }


class InstrumentedOracleGateTests(unittest.TestCase):
    def test_nonempty_exact_equivalence_is_source_only_eligible(self) -> None:
        result = evaluate(candidate())
        self.assertTrue(result["instrumented_source_oracle_eligible"])
        self.assertFalse(result["gold_implementation_eligible"])
        self.assertEqual([], result["failures"])

    def test_zero_trace_events_fail_closed(self) -> None:
        value = candidate()
        value["controls"]["trace_event_count"] = 0  # type: ignore[index]
        value["instrumented_source_oracle_eligible"] = False
        self.assertIn("zero_trace_event_count", evaluate(value)["failures"])

    def test_public_or_rng_drift_rejects_instrumentation(self) -> None:
        for key in ("public_observation_mismatch_count", "final_rng_state_mismatch_count"):
            with self.subTest(key=key):
                value = copy.deepcopy(candidate())
                value["controls"][key] = 1
                value["instrumented_source_oracle_eligible"] = False
                self.assertIn(key.removesuffix("_count") + "es", evaluate(value)["failures"])

    def test_boolean_false_is_not_a_measured_zero_mismatch_count(self) -> None:
        value = candidate()
        value["controls"]["native_boundary_mismatch_count"] = False  # type: ignore[index]
        value["instrumented_source_oracle_eligible"] = False
        result = evaluate(value)
        self.assertFalse(result["instrumented_source_oracle_eligible"])
        self.assertIn("native_boundary_mismatches", result["failures"])

    def test_trace_must_not_feed_gold_or_score(self) -> None:
        for key in ("trace_excluded_from_gold_runtime", "trace_excluded_from_conformance_denominator"):
            with self.subTest(key=key):
                value = copy.deepcopy(candidate())
                value["validity"][key] = False
                value["instrumented_source_oracle_eligible"] = False
                self.assertIn(f"{key}_not_proven", evaluate(value)["failures"])

    def test_claimed_pass_cannot_override_missing_toolchain_identity(self) -> None:
        value = candidate()
        del value["identity"]["toolchain_identity_sha256"]  # type: ignore[index]
        result = evaluate(value)
        self.assertFalse(result["instrumented_source_oracle_eligible"])
        self.assertIn("missing_toolchain_identity_sha256", result["failures"])
        self.assertIn("claimed_eligibility_mismatch", result["failures"])


if __name__ == "__main__":
    unittest.main()
