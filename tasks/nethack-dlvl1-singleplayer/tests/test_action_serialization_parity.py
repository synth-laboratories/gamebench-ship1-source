"""Parity coverage for rejected-action NEV serialization."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


class ActionSerializationParityTests(unittest.TestCase):
    def test_unsupported_string_action_is_not_json_quoted_in_rust_nev(self) -> None:
        task = {
            "task_id": "unsupported-action-nev",
            "seed": 812,
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit"},
            "actions": ["MiscDirection.ESC"],
        }
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        self.assertEqual(python["nev"], rust["nev"])
        violation = next(event for event in rust["nev"] if event["kind"] == "rule_violation")
        self.assertEqual("MiscDirection.ESC", violation["action"])


if __name__ == "__main__":
    unittest.main()
