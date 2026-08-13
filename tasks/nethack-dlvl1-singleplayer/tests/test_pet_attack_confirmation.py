"""Cross-lane contract for source-annotated pet KICK confirmation."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.compare_nle_discrepancies import fixture_task, python_step_projections, rust_step_projections
from scripts.verify_pet_attack_confirmation import expected_raw


class PetAttackConfirmationTests(unittest.TestCase):
    @staticmethod
    def _task() -> tuple[dict, dict[str, int]]:
        fixture_dir = TASK_DIR / "fixtures" / "nle_oracle" / "val-east-pickup-seed-20260725"
        task, _, _ = fixture_task(fixture_dir)
        actions = json.loads((TASK_DIR / "shared" / "nle_action_map.json").read_text())["actions"]
        return task, {record[1]: int(record[0]) for record in actions}

    @staticmethod
    def _trace(ids: dict[str, int], names: list[str]) -> list[dict[str, int | str]]:
        return [{"step": index + 1, "action_id": ids[name], "action_name": name} for index, name in enumerate(names)]

    def test_source_annotated_pet_kick_has_exact_prompt_and_no_response(self) -> None:
        task, ids = self._task()
        trace = self._trace(ids, ["Command.KICK", "CompassDirection.NE", "CompassDirection.SE"])
        python_trace = python_step_projections(task, trace)
        rust_trace = rust_step_projections(task, trace)
        self.assertEqual(python_trace, rust_trace)
        reset, direction, prompt, declined = python_trace
        expected_prompt = "Really attack the little dog? [yn] (n)"
        self.assertEqual("In what direction?", direction["message"])
        self.assertEqual(expected_prompt, prompt["message"])
        self.assertEqual(expected_raw(f"{expected_prompt} ", len(prompt["message_raw"])), prompt["message_raw"])
        self.assertEqual(reset["blstats"], direction["blstats"])
        self.assertEqual(reset["blstats"], prompt["blstats"])
        self.assertEqual(f"{expected_prompt} n", declined["message"])
        self.assertEqual(expected_raw(f"{expected_prompt} n", len(declined["message_raw"])), declined["message_raw"])
        self.assertEqual(prompt["blstats"], declined["blstats"])

    def test_confirmed_pet_kick_preserves_source_observed_dog_text(self) -> None:
        task, ids = self._task()
        trace = self._trace(ids, ["Command.KICK", "CompassDirection.NE", "CompassDirection.NW"])
        python_trace = python_step_projections(task, trace)
        rust_trace = rust_step_projections(task, trace)
        self.assertEqual(python_trace, rust_trace)
        confirmed = python_trace[-1]
        expected = "You kick the little dog. The little dog yelps!"
        self.assertEqual(expected, confirmed["message"])
        self.assertEqual(expected_raw(expected, len(confirmed["message_raw"])), confirmed["message_raw"])

    def test_pet_escape_requires_two_zero_turn_escapes_and_exposes_ynq(self) -> None:
        task, ids = self._task()
        trace = self._trace(ids, ["Command.KICK", "CompassDirection.NE", "Command.ESC", "Command.ESC"])
        python_trace = python_step_projections(task, trace)
        rust_trace = rust_step_projections(task, trace)
        self.assertEqual(python_trace, rust_trace)
        _, _, prompt, first_escape, second_escape = python_trace
        text = "Really attack the little dog? [yn] (n)"
        self.assertEqual("ynq", prompt["input_mode"]["kind"])
        self.assertEqual(f"{text} n", first_escape["message"])
        self.assertEqual(expected_raw(f"{text} n", len(first_escape["message_raw"])), first_escape["message_raw"])
        self.assertEqual("ynq", first_escape["input_mode"]["kind"])
        self.assertEqual("", second_escape["message"])
        self.assertEqual("normal", second_escape["input_mode"]["kind"])
        self.assertEqual(prompt["blstats"], first_escape["blstats"])
        self.assertEqual(first_escape["blstats"], second_escape["blstats"])

    def test_fight_is_not_routed_through_pet_kick_confirmation(self) -> None:
        task, ids = self._task()
        trace = self._trace(ids, ["Command.FIGHT", "CompassDirection.NE"])
        python_trace = python_step_projections(task, trace)
        rust_trace = rust_step_projections(task, trace)
        self.assertEqual(python_trace, rust_trace)
        self.assertFalse(python_trace[-1]["message"].startswith("Really attack the "))
        self.assertNotEqual("attack_confirm", python_trace[-1]["input_mode"]["kind"])

    def test_pet_glyph_without_source_pet_annotation_cannot_open_confirmation(self) -> None:
        task, ids = self._task()
        task = copy.deepcopy(task)
        task["level_dump"]["monsters"][0]["pet"] = False
        task["level_dump"]["monsters"][0]["peaceful"] = False
        trace = self._trace(ids, ["Command.KICK", "CompassDirection.NE"])
        python_trace = python_step_projections(task, trace)
        rust_trace = rust_step_projections(task, trace)
        self.assertEqual(python_trace, rust_trace)
        self.assertFalse(python_trace[-1]["message"].startswith("Really attack the "))
        self.assertNotEqual("attack_confirm", python_trace[-1]["input_mode"]["kind"])

    def test_source_pet_marker_sets_mg_pet_and_confirms_without_becoming_a_monster(self) -> None:
        task, ids = self._task()
        task = copy.deepcopy(task)
        level = task["level_dump"]
        pet = level["monsters"][0]
        level["monsters"] = []
        position = pet["position"]
        level["presentation_overlays"] = [{
            "x": position["x"], "y": position["y"], "char": pet["char"], "glyph": pet["glyph"], "color": pet["color"],
            "provenance": "nle_reset_presentation", "presentation_class": "pet_presentation", "identity_status": "unavailable_from_nle_presentation",
        }]
        level["pet_interaction_markers"] = [{
            "id": "nle-reset-pet", "name": "little dog", "x": position["x"], "y": position["y"], "char": pet["char"], "glyph": pet["glyph"], "color": pet["color"],
            "provenance": "nle_reset_pet_glyph", "identity_source": "glyph_to_mon_permonst",
        }]
        trace = self._trace(ids, ["Command.KICK", "CompassDirection.NE", "CompassDirection.SE"])
        python_trace = python_step_projections(task, trace)
        rust_trace = rust_step_projections(task, trace)
        self.assertEqual(python_trace, rust_trace)
        self.assertEqual(8, python_trace[0]["specials"][position["y"]][position["x"]])
        self.assertEqual("Really attack the little dog? [yn] (n) n", python_trace[-1]["message"])


if __name__ == "__main__":
    unittest.main()
