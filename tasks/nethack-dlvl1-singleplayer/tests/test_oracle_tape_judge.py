from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.oracle_tape import validate_manifest
from scripts.judge_nle_tapes import _terminal_ui_from_gold
from scripts.compare_nle_discrepancies import (
    fixture_task,
    first_difference,
    python_step_semantic_snapshots,
    rust_step_semantic_snapshots,
)


class OracleTapeJudgeTests(unittest.TestCase):
    def test_every_canonical_tape_has_a_valid_manifest(self) -> None:
        fixtures = sorted(path.parent for path in (TASK_DIR / "fixtures" / "nle_oracle").rglob("meta.json"))
        self.assertTrue(fixtures)
        failures = [failure for fixture in fixtures for failure in validate_manifest(fixture)]
        self.assertEqual([], failures)

    def test_legacy_corpus_records_truthful_no_native_sidecar_provenance(self) -> None:
        fixture = next(
            path.parent
            for path in (TASK_DIR / "fixtures" / "nle_oracle").glob("*/meta.json")
            if json.loads((path.parent / "tape_manifest.json").read_text()).get("capture_runtime", {}).get("status") == "legacy_version_only"
        )
        manifest = json.loads((fixture / "tape_manifest.json").read_text())
        provenance = manifest["native_pre_action_evidence"]
        self.assertFalse((fixture / "native_pre_action_evidence.jsonl").exists())
        self.assertEqual("legacy_no_native_pre_action_evidence", provenance["status"])
        self.assertIs(False, provenance["conformance_denominator_included"])

    def test_empty_corpus_fails_hard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            completed = subprocess.run(
                [sys.executable, str(TASK_DIR / "scripts" / "judge_nle_tapes.py"), "--root", temporary, "--lane", "python"],
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("zero oracle fixtures", completed.stderr)

    def test_private_state_trace_is_equal_across_gold_lanes(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-wait-seed-20260725"
        task, actions, _ = fixture_task(fixture)
        python_states = python_step_semantic_snapshots(task, actions)
        rust_states = rust_step_semantic_snapshots(task, actions)
        self.assertEqual(len(python_states), len(rust_states))
        self.assertIsNone(first_difference(python_states, rust_states))

    def test_manifest_detects_raw_tape_mutation(self) -> None:
        fixture = next((TASK_DIR / "fixtures" / "nle_oracle").glob("*/meta.json")).parent
        with tempfile.TemporaryDirectory() as temporary:
            clone = Path(temporary) / fixture.name
            clone.mkdir()
            for source in fixture.iterdir():
                if source.is_file():
                    (clone / source.name).write_bytes(source.read_bytes())
            with (clone / "actions.jsonl").open("a") as handle:
                handle.write(json.dumps({"step": 999, "action_id": 0, "action_name": "tampered"}) + "\n")
            failures = validate_manifest(clone)
        self.assertTrue(failures)
        self.assertIn("invalid oracle tape", failures[0])

    def test_inventory_display_terminal_overlay_has_observed_layout_colors_and_cursor(self) -> None:
        entries = [
            (ord("a"), 2, "a +1 long sword (weapon in hand)"),
            (ord("b"), 2, "a +0 dagger (alternate weapon; not wielded)"),
            (ord("c"), 3, "an uncursed +3 small shield (being worn)"),
            (ord("d"), 7, "2 uncursed food rations"),
            (ord("e"), 6, "an uncursed oil lamp"),
        ]
        chars = [" " * 79 for _ in range(21)]
        colors = [[0] * 79 for _ in range(21)]
        chars[2] = " " * 50 + "@" + " " * 28  # This cell is cleared by row-three Armor.
        projection = {
            "blstats": [0] * 27,
            "message_raw": [],
            "chars": chars,
            "colors": colors,
            "input_mode": {"kind": "inventory_display"},
            "inventory": {
                "inv_letters": [letter for letter, _, _ in entries] + [0] * 50,
                "inv_oclasses": [object_class for _, object_class, _ in entries] + [18] * 50,
                "inv_strs": [text for _, _, text in entries] + [""] * 50,
            },
        }
        terminal = _terminal_ui_from_gold(projection)
        rows, row_colors = terminal["char_rows"], terminal["color_rows"]
        self.assertEqual([9, 37], terminal["cursor_yx"])
        self.assertEqual("Weapons", rows[0][31:38])
        self.assertEqual("a - a +1 long sword (weapon in hand)", rows[1][31:67])
        self.assertEqual("Armor", rows[3][31:36])
        self.assertEqual(" ", rows[3][50])
        self.assertEqual("(end)", rows[9][31:36])
        self.assertEqual(23, row_colors[0][31])
        self.assertEqual(7, row_colors[1][31])
        self.assertEqual(0, row_colors[1][32])


if __name__ == "__main__":
    unittest.main()
