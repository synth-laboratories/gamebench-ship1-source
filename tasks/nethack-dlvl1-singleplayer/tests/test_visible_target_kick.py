"""Narrow cross-lane contract for a raw-visible wall KICK."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.compare_nle_discrepancies import fixture_task, python_step_projections, rust_step_projections
from scripts.verify_visible_target_kick import PROMPT_RAW_TEXT, expected_raw, target_class


class VisibleTargetKickTests(unittest.TestCase):
    def test_target_classification_never_names_an_unobserved_overlay_identity(self) -> None:
        self.assertEqual("empty_floor", target_class("."))
        self.assertEqual("wall", target_class("|"))
        self.assertEqual("wall", target_class("-"))
        self.assertEqual("door", target_class("+"))
        self.assertEqual("visible_entity_overlay", target_class("d"))
        self.assertIsNone(target_class("@"))

    def test_wall_kick_has_observed_message_and_turn_contract_in_both_lanes(self) -> None:
        fixture_dir = TASK_DIR / "fixtures" / "nle_oracle" / "val-east-pickup-seed-20260725"
        task, _, _ = fixture_task(fixture_dir)
        actions = json.loads((TASK_DIR / "shared" / "nle_action_map.json").read_text())["actions"]
        ids = {record[1]: int(record[0]) for record in actions}
        trace_actions = [
            {"step": 1, "action_id": ids["Command.KICK"], "action_name": "Command.KICK"},
            {"step": 2, "action_id": ids["CompassDirection.W"], "action_name": "CompassDirection.W"},
        ]
        python_trace = python_step_projections(task, trace_actions)
        rust_trace = rust_step_projections(task, trace_actions)
        self.assertEqual(python_trace, rust_trace)
        reset, prompt, result = python_trace
        self.assertEqual(expected_raw(PROMPT_RAW_TEXT, len(prompt["message_raw"])), prompt["message_raw"])
        self.assertEqual("Ouch! That hurts!", result["message"])
        self.assertEqual(expected_raw("Ouch!  That hurts!", len(result["message_raw"])), result["message_raw"])
        self.assertEqual(reset["blstats"], prompt["blstats"])
        self.assertEqual(reset["blstats"][20] + 1, result["blstats"][20])


if __name__ == "__main__":
    unittest.main()
