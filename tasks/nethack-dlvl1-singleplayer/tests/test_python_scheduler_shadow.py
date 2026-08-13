from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_python_scheduler_shadow import (
    DEFAULT_ACTIONS,
    build_report,
    public_destination_candidate,
    split_manifest,
    validate_manifest,
)


def public() -> dict:
    return {
        "chars": [".@d"],
        "colors": [[0, 15, 3]],
        "glyphs": [[0, 1, 2]],
        "specials": [[0, 0, 0]],
        "blstats": [1, 0],
        "message": "",
        "message_raw": [0],
        "inventory": {},
        "input_mode": {"kind": "normal"},
        "done": False,
    }


def case(seed: int, phase: str) -> dict:
    return {"seed": seed, "phase": phase, "live_boundary_count": 5, "candidate_outcome_comparison_count": 0, "indeterminate_count": 5, "records": []}


class PythonSchedulerShadowTests(unittest.TestCase):
    def test_candidate_has_no_destination_and_uses_no_private_state(self) -> None:
        prediction = public_destination_candidate(public())
        self.assertEqual("indeterminate", prediction["status"])
        self.assertIsNone(prediction["destination"])
        self.assertEqual({"x": 1, "y": 0}, prediction["hero"])
        self.assertIn("stable actor identity", prediction["reason"])

    def test_manifest_is_exact_and_tamper_evident(self) -> None:
        manifest = split_manifest(calibration_seeds=[1, 2], heldout_seeds=[3, 4], actions=DEFAULT_ACTIONS)
        validate_manifest(manifest, manifest)
        changed = copy.deepcopy(manifest)
        changed["actions"] = ["MiscDirection.WAIT", "Command.SEARCH"]
        with self.assertRaises(ValueError):
            validate_manifest(changed, manifest)

    def test_standard_gate_blocks_python_only_zero_destination_shadow(self) -> None:
        manifest = split_manifest(calibration_seeds=[1, 2], heldout_seeds=[3, 4], actions=DEFAULT_ACTIONS)
        report = build_report(manifest, [case(1, "calibration"), case(2, "calibration")], [case(3, "heldout"), case(4, "heldout")])
        self.assertEqual("shadow_evaluated_gold_blocked", report["status"])
        self.assertEqual(10, report["heldout"]["live_boundary_count"])
        self.assertEqual(0, report["heldout"]["candidate_outcome_comparison_count"])
        self.assertFalse(report["gold_implementation_eligible"])
        self.assertIn("zero_heldout_comparisons", report["implementation_blockers"])
        self.assertIn("missing_cross_lane_heldout_records", report["implementation_blockers"])

    def test_cli_requires_freeze_before_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "split.json"
            completed = subprocess.run(
                [".venv/bin/python", "scripts/evaluate_python_scheduler_shadow.py", "--write-split-manifest", str(manifest)],
                capture_output=True,
                check=True,
                text=True,
            )
            self.assertEqual("split_frozen", json.loads(completed.stdout)["status"])
            self.assertTrue(manifest.exists())
            refused = subprocess.run(
                [".venv/bin/python", "scripts/evaluate_python_scheduler_shadow.py", "--report", str(root / "report.json")],
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(0, refused.returncode)
        self.assertIn("pre-existing --split-manifest", refused.stderr)


if __name__ == "__main__":
    unittest.main()
