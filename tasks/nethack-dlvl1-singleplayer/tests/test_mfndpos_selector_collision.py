from __future__ import annotations

import copy
import unittest

from scripts.analyze_mfndpos_selector_collision import analyze


def record(seed: int, *, collision: bool = True, arrives: bool = True) -> dict[str, object]:
    flags = 0x00080000 if collision else 0
    after = {"entity_id": 7, "native_x": 11 if arrives else 99, "native_y": 10}
    return {
        "seed": seed,
        "stable_entity_id": 7,
        "mfndpos": {
            "caller": "m_move",
            "actor_at_mfndpos_return": {"entity_id": 7, "native_x": 10, "native_y": 10},
            "candidate_count": 2,
            "candidates": [
                {"native_x": 11, "native_y": 10, "mfndpos_flags": flags},
                {"native_x": 10, "native_y": 11, "mfndpos_flags": 0},
            ],
        },
        "selected_result": {
            "branch_selector_return": {
                "selector": "m_move", "return_code": 1,
                "actor": {"entity_id": 7}, "actor_after": after,
            },
        },
    }


def trace(records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": "gamebench.nethack.instrumented_oracle_equivalence.v1",
        "instrumented_source_oracle_eligible": True,
        "identity": {"source_commit": "unit"},
        "controls": {
            "public_observation_mismatch_count": 0, "native_boundary_mismatch_count": 0,
            "final_rng_state_mismatch_count": 0, "trace_replay_mismatch_count": 0,
            "unmatched_event_count": 0, "trace_error_count": 0,
        },
        "branch_records": records,
    }


class MfndposSelectorCollisionTests(unittest.TestCase):
    def test_fixed_selector_and_collision_hypothesis_requires_heldout_support(self) -> None:
        result = analyze(trace([record(1), record(2)]), calibration_seeds=[1], heldout_seeds=[2])
        self.assertTrue(result["source_selector_hypothesis_eligible"])
        self.assertFalse(result["gold_implementation_eligible"])

    def test_heldout_arrival_counterexample_rejects_hypothesis(self) -> None:
        result = analyze(trace([record(1), record(2, arrives=False)]), calibration_seeds=[1], heldout_seeds=[2])
        self.assertFalse(result["source_selector_hypothesis_eligible"])
        self.assertIn("heldout_selector_arrival_not_in_candidate_set", [item["code"] for item in result["counterexamples"]])

    def test_zero_collision_cannot_be_promoted_by_ordinary_arrivals(self) -> None:
        result = analyze(trace([record(1, collision=False), record(2, collision=False)]), calibration_seeds=[1], heldout_seeds=[2])
        self.assertFalse(result["source_selector_hypothesis_eligible"])
        self.assertIn("heldout_zero_selected_collision_examples", [item["code"] for item in result["counterexamples"]])

    def test_split_must_cover_trace_and_not_overlap(self) -> None:
        value = trace([record(1), record(2)])
        with self.assertRaisesRegex(ValueError, "overlap"):
            analyze(value, calibration_seeds=[1], heldout_seeds=[1, 2])
        with self.assertRaisesRegex(ValueError, "absent"):
            analyze(value, calibration_seeds=[1], heldout_seeds=[3])


if __name__ == "__main__":
    unittest.main()
