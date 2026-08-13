from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_scheduler_destination_candidate import evaluate


def record(seed: int, *, source=(4, 4), destination=(5, 4), candidates=((5, 4),)) -> dict:
    return {
        "seed": seed,
        "step": 1,
        "stable_entity_id": seed,
        "mfndpos": {
            "caller": "m_move",
            "actor_at_mfndpos_return": {"native_x": source[0], "native_y": source[1]},
            "candidates": [{"native_x": x, "native_y": y, "mfndpos_flags": 0} for x, y in candidates],
        },
        "selected_result": {
            "branch_selector_return": {
                "selector": "m_move",
                "return_code": 1,
                "actor_after": {"native_x": destination[0], "native_y": destination[1]},
            },
        },
    }


def trace() -> dict:
    return {
        "schema": "gamebench.nethack.instrumented_oracle_equivalence.v1",
        "identity": {"source_commit": "pinned"},
        "controls": {
            "public_observation_mismatch_count": 0,
            "native_boundary_mismatch_count": 0,
            "final_rng_state_mismatch_count": 0,
            "trace_replay_mismatch_count": 0,
            "unmatched_event_count": 0,
            "trace_error_count": 0,
            "two_independent_runs_exact": True,
        },
        "branch_records": [
            record(1),
            record(2, destination=(4, 4)),  # successful stationary dog/pet path
            record(3),
            record(4, destination=(4, 4)),
        ],
    }


class SchedulerDestinationCandidateTests(unittest.TestCase):
    def test_stay_or_candidate_is_source_eligible_but_gold_fails_zero_denominators(self) -> None:
        result = evaluate(trace(), calibration_seeds=[1, 2], heldout_seeds=[3, 4])
        self.assertTrue(result["source_assertion_eligible"])
        self.assertEqual(1, result["heldout"]["movement_comparison_count"])
        self.assertFalse(result["gold_implementation_eligible"])
        self.assertEqual({"python", "rust"}, {item["lane"] for item in result["cross_language_evaluation"]})
        self.assertTrue(all(item["comparison_count"] == 0 for item in result["cross_language_evaluation"]))
        self.assertIn("zero_heldout_comparisons", result["implementation_blockers"])
        self.assertIn("zero_selector_underlay_comparisons", result["implementation_blockers"])
        self.assertIn("completed actor turn", result["hypothesis"]["rule"])
        self.assertIn("excluded", result["hypothesis"]["nonmovement_semantics"])

    def test_heldout_counterexample_rejects_source_rule(self) -> None:
        value = trace()
        value["branch_records"][-1] = record(4, destination=(8, 8))
        result = evaluate(value, calibration_seeds=[1, 2], heldout_seeds=[3, 4])
        self.assertFalse(result["source_assertion_eligible"])
        self.assertEqual(1, result["heldout"]["error_count"])
        self.assertEqual(1, len(result["heldout"]["counterexamples"]))

    def test_split_must_be_exact_disjoint_and_preselected(self) -> None:
        with self.assertRaises(ValueError):
            evaluate(trace(), calibration_seeds=[1, 2], heldout_seeds=[2, 3, 4])
        with self.assertRaises(ValueError):
            evaluate(trace(), calibration_seeds=[1], heldout_seeds=[3, 4])

    def test_nonzero_equivalence_control_fails_closed(self) -> None:
        value = copy.deepcopy(trace())
        value["controls"]["trace_replay_mismatch_count"] = 1
        with self.assertRaises(ValueError):
            evaluate(value, calibration_seeds=[1, 2], heldout_seeds=[3, 4])

    def test_boolean_does_not_satisfy_zero_control(self) -> None:
        value = copy.deepcopy(trace())
        value["controls"]["unmatched_event_count"] = False
        with self.assertRaises(ValueError):
            evaluate(value, calibration_seeds=[1, 2], heldout_seeds=[3, 4])

    def test_cli_writes_fail_closed_report_for_rejected_trace(self) -> None:
        value = trace()
        value["controls"]["unmatched_event_count"] = 2
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "trace.json", Path(directory) / "report.json"
            source.write_text(json.dumps(value))
            completed = subprocess.run(
                [
                    ".venv/bin/python", "scripts/evaluate_scheduler_destination_candidate.py",
                    str(source), "--calibration-seeds", "1,2", "--heldout-seeds", "3,4",
                    "--output", str(output),
                ],
                text=True, capture_output=True, check=True,
            )
            result = json.loads(output.read_text())
        self.assertEqual("input_trace_rejected", result["status"])
        self.assertFalse(result["gold_implementation_eligible"])
        self.assertIn("input_trace_prerequisite_failed", result["promotion_gate"]["failures"])
        self.assertEqual(2, result["counterexamples"][0]["observed_control"])
        self.assertTrue(result["input_artifact_file_sha256"].startswith("sha256:"))
        self.assertIn("input_trace_rejected", completed.stdout)


if __name__ == "__main__":
    unittest.main()
