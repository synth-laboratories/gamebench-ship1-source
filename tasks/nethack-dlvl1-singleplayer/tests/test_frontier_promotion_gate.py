from __future__ import annotations

import copy
import unittest

from scripts.frontier_promotion_gate import SCHEMA, evaluate


def eligible_candidate() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "subsystem": "test-only",
        "validity": {
            "source_identity_pinned": True,
            "captured_pre_action_only": True,
            "no_future_or_reset_hydration": True,
            "no_seed_or_coordinate_lookup": True,
            "source_assertion_repeatable": True,
            "python_rust_parity": True,
            "split_frozen_before_candidate": True,
            "artifact_identity_pinned": True,
        },
        "source_assertions": {"comparison_count": 20, "error_count": 0},
        "heldout": {
            "case_count": 10,
            "comparison_count": 100,
            "counterexample_count": 0,
            "baseline_first_divergence_step": 2,
            "candidate_first_divergence_step": 3,
            "baseline_error_count": 50,
            "candidate_error_count": 40,
            "calibration_identity_sha256": "sha256:" + "1" * 64,
            "heldout_identity_sha256": "sha256:" + "2" * 64,
            "artifact_sha256": "sha256:" + "3" * 64,
            "records": [
                {
                    "fixture_id": "heldout-a",
                    "lane": lane,
                    "comparison_count": 50,
                    "baseline_first_divergence_step": 2,
                    "candidate_first_divergence_step": 3,
                    "baseline_error_count": 25,
                    "candidate_error_count": 20,
                }
                for lane in ("python", "rust")
            ],
        },
        "gold_implementation_eligible": True,
    }


class FrontierPromotionGateTests(unittest.TestCase):
    def test_complete_nonregressing_candidate_is_eligible(self) -> None:
        result = evaluate(eligible_candidate())
        self.assertTrue(result["source_assertion_eligible"])
        self.assertTrue(result["source_export_eligible"])
        self.assertTrue(result["gold_implementation_eligible"])
        self.assertEqual([], result["failures"])

    def test_aggregate_improvement_cannot_hide_earlier_divergence(self) -> None:
        candidate = eligible_candidate()
        candidate["heldout"]["candidate_first_divergence_step"] = 1  # type: ignore[index]
        candidate["heldout"]["candidate_error_count"] = 1  # type: ignore[index]
        candidate["gold_implementation_eligible"] = False
        result = evaluate(candidate)
        self.assertFalse(result["gold_implementation_eligible"])
        self.assertIn("first_divergence_regression", result["failures"])

    def test_zero_comparison_and_counterexample_fail_closed(self) -> None:
        candidate = eligible_candidate()
        candidate["source_assertions"]["comparison_count"] = 0  # type: ignore[index]
        candidate["heldout"]["comparison_count"] = 0  # type: ignore[index]
        candidate["heldout"]["counterexample_count"] = 1  # type: ignore[index]
        candidate["gold_implementation_eligible"] = False
        failures = evaluate(candidate)["failures"]
        self.assertIn("zero_source_comparisons", failures)
        self.assertIn("zero_heldout_comparisons", failures)
        self.assertIn("heldout_counterexamples", failures)

    def test_each_anti_leakage_proof_is_required(self) -> None:
        for key in (
            "captured_pre_action_only",
            "no_future_or_reset_hydration",
            "no_seed_or_coordinate_lookup",
        ):
            with self.subTest(key=key):
                candidate = copy.deepcopy(eligible_candidate())
                candidate["validity"][key] = False
                candidate["gold_implementation_eligible"] = False
                self.assertIn(f"{key}_not_proven", evaluate(candidate)["failures"])

    def test_claimed_pass_cannot_override_missing_evidence(self) -> None:
        candidate = eligible_candidate()
        del candidate["heldout"]
        result = evaluate(candidate)
        self.assertFalse(result["gold_implementation_eligible"])
        self.assertIn("missing_heldout_evidence", result["failures"])
        self.assertIn("claimed_eligibility_mismatch", result["failures"])

    def test_gold_cannot_pass_when_source_export_is_explicitly_ineligible(self) -> None:
        candidate = eligible_candidate()
        candidate["source_export_eligible"] = False
        result = evaluate(candidate)
        self.assertFalse(result["gold_implementation_eligible"])
        self.assertIn("source_export_not_eligible", result["failures"])
        self.assertIn("claimed_eligibility_mismatch", result["failures"])

    def test_boolean_false_is_not_a_measured_zero_error_or_counterexample_count(self) -> None:
        for section, key, failure in (
            ("source_assertions", "error_count", "source_assertion_errors"),
            ("heldout", "counterexample_count", "heldout_counterexamples"),
        ):
            with self.subTest(section=section, key=key):
                candidate = copy.deepcopy(eligible_candidate())
                candidate[section][key] = False
                candidate["gold_implementation_eligible"] = False
                self.assertIn(failure, evaluate(candidate)["failures"])

    def test_per_lane_regression_cannot_hide_under_nonregressing_aggregate(self) -> None:
        candidate = eligible_candidate()
        candidate["heldout"]["records"][1]["candidate_first_divergence_step"] = 1  # type: ignore[index]
        candidate["gold_implementation_eligible"] = False
        result = evaluate(candidate)
        self.assertFalse(result["gold_implementation_eligible"])
        self.assertIn("heldout_record_first_divergence_regression", result["failures"])

    def test_split_and_artifact_identities_are_mandatory(self) -> None:
        for key in ("calibration_identity_sha256", "heldout_identity_sha256", "artifact_sha256"):
            candidate = copy.deepcopy(eligible_candidate())
            del candidate["heldout"][key]  # type: ignore[index]
            candidate["gold_implementation_eligible"] = False
            self.assertIn(f"missing_{key}", evaluate(candidate)["failures"])

    def test_mfndpos_promotion_requires_positive_exact_conservation_planes(self) -> None:
        candidate = eligible_candidate()
        candidate["subsystem"] = "native_mfndpos_candidate"
        candidate["selector_conservation"] = {
            plane: {"comparison_count": 2, "error_count": 0}
            for plane in ("outcome_membership", "destination", "underlay")
        }
        self.assertTrue(evaluate(candidate)["gold_implementation_eligible"])
        candidate["selector_conservation"]["underlay"]["comparison_count"] = 0  # type: ignore[index]
        candidate["gold_implementation_eligible"] = False
        self.assertIn("zero_selector_underlay_comparisons", evaluate(candidate)["failures"])


if __name__ == "__main__":
    unittest.main()
