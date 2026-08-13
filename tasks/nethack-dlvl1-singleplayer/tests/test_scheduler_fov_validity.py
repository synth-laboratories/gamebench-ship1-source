from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.scheduler_fov_validity import (
    fov_underlay_applicability,
    masked_surface_audit,
    require_equal_lane_denominators,
    scheduler_applicability,
)


class SchedulerFovValidityTests(unittest.TestCase):
    def test_presentation_continuity_is_not_a_scheduler_identity(self) -> None:
        report = scheduler_applicability(
            {
                "entity_identity_kind": "presentation_continuity_only",
                "pre_action_state_complete": False,
                "underlay_complete": False,
                "transitions": [{"source_case": "seed-1", "replayed_exactly": True, "pre_action_authoritative": False}],
            }
        )

        self.assertEqual("rejected", report["status"])
        self.assertIn("no_stable_public_entity_id", {reason["code"] for reason in report["reasons"]})
        self.assertIn("hidden_entity_state_missing", {reason["code"] for reason in report["reasons"]})

    def test_authoritative_identity_contract_has_a_falsifiable_accept_path(self) -> None:
        report = scheduler_applicability(
            {
                "entity_identity_kind": "stable_public_entity_id",
                "pre_action_state_complete": True,
                "underlay_complete": True,
                "transitions": [
                    {"source_case": f"seed-{seed}", "replayed_exactly": True, "pre_action_authoritative": True}
                    for seed in (1, 2, 3)
                ],
            }
        )

        self.assertEqual("eligible", report["status"])

    def test_future_static_reveal_cannot_hydrate_an_underlay_or_fov_rule(self) -> None:
        report = fov_underlay_applicability(
            {
                "kind": "known_static_cache",
                "cells": [
                    {
                        "x": 3, "y": 4, "char": ".", "glyph": 2371, "color": 7,
                        "observed_at_step": 2, "applied_before_step": 2,
                        "provenance": "direct_static_public_plane",
                    }
                ],
            }
        )

        self.assertEqual("rejected", report["status"])
        self.assertIn("future_observation_leak", {reason["code"] for reason in report["reasons"]})

    def test_fov_rule_requires_negative_controls_not_only_revealed_floor(self) -> None:
        report = fov_underlay_applicability(
            {
                "kind": "fov_visibility_rule",
                "cells": [
                    {
                        "x": 3, "y": 4, "char": ".", "glyph": 2371, "color": 7,
                        "observed_at_step": 0, "applied_before_step": 1,
                        "provenance": "direct_static_public_plane",
                    }
                ],
                "heldout_source_cases": ["seed-1", "seed-2", "seed-3"],
                "negative_controls": {"unseen_cells_exact": True, "occluded_cells_exact": False},
            }
        )

        self.assertEqual("rejected", report["status"])
        self.assertIn("missing_fov_negative_controls", {reason["code"] for reason in report["reasons"]})

    def test_later_direct_overlay_at_masked_coordinate_requires_partial_result(self) -> None:
        report = masked_surface_audit(
            [
                {"chars": ["d"], "glyphs": [[413]], "colors": [[15]]},
                {"chars": ["."], "glyphs": [[2371]], "colors": [[7]]},
            ],
            [(0, 0)],
        )

        self.assertEqual("partial_unjudgeable_required", report["status"])
        self.assertEqual(1, len(report["later_direct_overlay_records"]))
        self.assertEqual(0, report["later_direct_overlay_records"][0]["step"])

    def test_lane_denominator_disagreement_is_report_corruption_not_maximum_coverage(self) -> None:
        lanes = [
            {"visibility_entity_transition_oracle_v1": {"comparisons": 7}},
            {"visibility_entity_transition_oracle_v1": {"comparisons": 6}},
        ]

        with self.assertRaisesRegex(ValueError, "gold lanes disagree"):
            require_equal_lane_denominators(lanes, "visibility_entity_transition_oracle_v1")


if __name__ == "__main__":
    unittest.main()
