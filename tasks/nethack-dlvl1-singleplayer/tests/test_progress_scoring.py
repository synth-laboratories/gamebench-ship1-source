"""Regression tests for source-eligible live-fuzz progress scoring."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.fuzz_nle_differential import PROMPT_PROBE_ACTIONS, action_source_eligibility, comparison_eligibility, lane_report
from scripts.progress_scoring import source_behavior_result, source_trace_metrics


def lane(*, judgeable: int, unjudgeable: int, difference: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "source_state_eligibility_v1": {
            "judgeable_action_steps": judgeable,
            "unjudgeable_action_steps": unjudgeable,
        },
        "strict_snapshot_v1": {"first_difference": difference},
        "first_divergent_step_census_v1": {"mismatches": []},
    }


class ProgressScoringTests(unittest.TestCase):
    def test_unjudgeable_case_never_reports_pass_or_divergence(self) -> None:
        expected = [{"chars": ["@"], "blstats": [0, 0], "done": False}, {"chars": ["<"], "blstats": [0, 0], "done": False}]
        actual = [{"chars": ["@"], "blstats": [0, 0], "done": False}, {"chars": ["."], "blstats": [0, 0], "done": False}]
        report = lane_report(
            "python",
            expected,
            actual,
            [{"action_name": "Command.PICKUP", "source_state_eligibility": {"status": "unjudgeable", "requirements": [{"key": "hero_terrain_underlay", "provenance": "unknown"}]}}],
            strict_baseline=True,
        )
        self.assertEqual("unjudgeable", report["strict_snapshot_v1"]["status"])
        self.assertEqual("unjudgeable", report["bootstrap_masked_transition_v0"]["status"])

        metrics = source_trace_metrics(
            [{"fixture_id": "pickup", "lanes": [lane(judgeable=0, unjudgeable=1)]}],
            {"pickup": 1},
            lanes_key="lanes",
        )
        self.assertIsNone(metrics["score"])
        self.assertEqual("partial_unjudgeable", source_behavior_result(metrics))

    def test_unjudgeable_turns_are_excluded_from_the_fidelity_denominator(self) -> None:
        metrics = source_trace_metrics(
            [{"fixture_id": "mixed", "lanes": [lane(judgeable=1, unjudgeable=2), lane(judgeable=1, unjudgeable=2)]}],
            {"mixed": 3},
            lanes_key="lanes",
        )
        self.assertEqual(1, metrics["turns"])
        self.assertEqual(2, metrics["unjudgeable_turns"])
        self.assertEqual(100.0, metrics["score"])
        self.assertEqual("partial_unjudgeable", source_behavior_result(metrics))

    def test_prompt_campaign_is_fully_eligible_because_pickup_is_separate(self) -> None:
        self.assertNotIn("Command.PICKUP", PROMPT_PROBE_ACTIONS)
        actions = [
            {"action_name": name, "source_state_eligibility": {"status": "eligible", "requirements": []}}
            for name in PROMPT_PROBE_ACTIONS
        ]
        eligibility = comparison_eligibility(actions)
        self.assertEqual("eligible", eligibility["status"])
        self.assertEqual(len(PROMPT_PROBE_ACTIONS), eligibility["judgeable_action_steps"])
        self.assertEqual(0, eligibility["unjudgeable_action_steps"])

    def test_pickup_requires_targeted_evidence_outside_prompt_campaign(self) -> None:
        reset = {"chars": [[ord("@")]], "glyphs": [[340]], "colors": [[15]], "blstats": [0, 0]}
        pickup = action_source_eligibility("Command.PICKUP", [reset], step=1, unseen_glyph=2359)
        self.assertEqual("unjudgeable", pickup["status"])
        self.assertTrue((TASK_DIR / "scripts" / "verify_known_underlay_pickup.py").is_file())
        self.assertTrue((TASK_DIR / "fixtures" / "nle_oracle" / "val-stair-pickup-seed-10").is_dir())

    def test_lane_disagreement_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "eligibility differs across lanes"):
            source_trace_metrics(
                [{"fixture_id": "bad", "lanes": [lane(judgeable=1, unjudgeable=0), lane(judgeable=0, unjudgeable=1)]}],
                {"bad": 1},
                lanes_key="lanes",
            )


if __name__ == "__main__":
    unittest.main()
