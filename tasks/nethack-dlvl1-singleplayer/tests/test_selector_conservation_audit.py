from __future__ import annotations

import copy
import unittest

from scripts.audit_selector_conservation import audit


def candidate() -> dict[str, object]:
    actor = {"entity_id": 7, "native_x": 10, "native_y": 10}
    return {
        "schema": "gamebench.nethack.instrumented_oracle_equivalence.v1",
        "identity": {"source_commit": "pinned", "baseline_binary_sha256": "abc"},
        "controls": {
            "public_observation_mismatch_count": 0,
            "native_boundary_mismatch_count": 0,
            "final_rng_state_mismatch_count": 0,
            "trace_replay_mismatch_count": 0,
            "trace_error_count": 0,
            "unmatched_event_count": 0,
        },
        "branch_records": [{
            "seed": 1,
            "stable_entity_id": 7,
            "mfndpos": {
                "caller": "m_move",
                "candidates": [
                    {"native_x": 11, "native_y": 10},
                    {"native_x": 10, "native_y": 11},
                ],
            },
            "selected_result": {"branch_selector_return": {
                "selector": "m_move",
                "return_code": 1,
                "actor": actor,
                "actor_after": {"entity_id": 7, "native_x": 11, "native_y": 10},
            }},
        }],
    }


class SelectorConservationAuditTests(unittest.TestCase):
    def test_preselected_seed_subset_is_explicit_and_fail_closed(self) -> None:
        result = audit(candidate(), seeds={1})
        self.assertEqual([1], result["analyzed_seeds"])
        with self.assertRaises(ValueError):
            audit(candidate(), seeds={2})

    def test_exact_return_supplies_destination_and_membership_not_underlay(self) -> None:
        result = audit(candidate())
        self.assertEqual(1, result["selector_conservation"]["destination"]["comparison_count"])
        self.assertEqual(1, result["selector_conservation"]["outcome_membership"]["comparison_count"])
        self.assertEqual(0, result["selector_conservation"]["underlay"]["comparison_count"])
        self.assertIn("zero_underlay_comparisons", result["blockers"])

    def test_exact_boundary_underlay_supplies_nonzero_denominator(self) -> None:
        value = candidate()
        selector = value["branch_records"][0]["selected_result"]["branch_selector_return"]  # type: ignore[index]
        source = {"coordinate": {"native_x": 10, "native_y": 10}, "state": {"typ": 24, "objects": []}, "occupancy": {"entity_id": 7}}
        source_after = copy.deepcopy(source)
        source_after["occupancy"] = {"entity_id": None}
        destination = {"coordinate": {"native_x": 11, "native_y": 10}, "state": {"typ": 24, "objects": []}, "occupancy": {"entity_id": None}}
        destination_after = copy.deepcopy(destination)
        destination_after["occupancy"] = {"entity_id": 7}
        selector["source_underlay_before"] = source
        selector["source_underlay_after"] = source_after
        selector["destination_underlay_before"] = destination
        selector["destination_underlay_after"] = destination_after
        result = audit(value)
        self.assertEqual({"comparison_count": 2, "error_count": 0}, result["selector_conservation"]["underlay"])
        self.assertTrue(result["source_assertion_eligible"])

    def test_action_end_underlay_is_never_accepted(self) -> None:
        value = candidate()
        selected = value["branch_records"][0]["selected_result"]  # type: ignore[index]
        selected["post_action_entity"] = {"underlay": {"terrain_type": 24}}
        self.assertEqual(0, audit(value)["selector_conservation"]["underlay"]["comparison_count"])

    def test_partial_destination_boundary_is_a_structural_error(self) -> None:
        value = candidate()
        selector = value["branch_records"][0]["selected_result"]["branch_selector_return"]  # type: ignore[index]
        source = {"coordinate": {"native_x": 10, "native_y": 10}, "state": {"typ": 24, "objects": []}, "occupancy": {"entity_id": 7}}
        selector["source_underlay_before"] = source
        selector["source_underlay_after"] = copy.deepcopy(source)
        selector["destination_underlay_before"] = {"coordinate": {"native_x": 11, "native_y": 10}, "state": {"typ": 24, "objects": []}, "occupancy": {"entity_id": None}}
        result = audit(value)
        self.assertIn("structural_record_errors", result["blockers"])
        self.assertEqual("partial_selector_boundary_underlay", result["structural_errors"][0]["error"])

    def test_unmatched_events_fail_even_with_positive_planes(self) -> None:
        value = candidate()
        value["controls"]["unmatched_event_count"] = 2  # type: ignore[index]
        result = audit(value)
        self.assertFalse(result["source_assertion_eligible"])
        self.assertIn("unmatched_selector_events", result["blockers"])

    def test_membership_counterexample_is_surfaced(self) -> None:
        value = candidate()
        selector = value["branch_records"][0]["selected_result"]["branch_selector_return"]  # type: ignore[index]
        selector["actor_after"]["native_x"] = 12
        result = audit(value)
        self.assertEqual(1, result["selector_conservation"]["outcome_membership"]["error_count"])

    def test_stationary_code_one_is_completed_turn_not_membership_error(self) -> None:
        value = candidate()
        selector = value["branch_records"][0]["selected_result"]["branch_selector_return"]  # type: ignore[index]
        selector["actor_after"]["native_x"] = 10
        selector["actor_after"]["native_y"] = 10
        result = audit(value)
        self.assertEqual({"comparison_count": 0, "error_count": 0}, result["selector_conservation"]["outcome_membership"])
        self.assertEqual(
            {"comparison_count": 1, "error_count": 0, "stationary_completed_turn_count": 1},
            result["selector_completion"],
        )


if __name__ == "__main__":
    unittest.main()
