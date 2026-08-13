"""Exact cross-lane lifecycle checks for the authored fatal-trap fixture."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario
from scripts.trap_outcome_assertions import authored_trap_death_report


class TrapOutcomeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "bootstrap_trap_death.json").read_text())

    def test_fatal_trap_consumes_the_move_turn_and_preserves_terminal_state(self) -> None:
        result = run_scenario(self.entry)
        report = authored_trap_death_report(result, trap_id="fatal-pit", damage=14)
        self.assertEqual("pass", report["status"], report)
        self.assertEqual(1, result["readout"]["public"]["blstats_named"]["time"])

    def test_rust_matches_the_exact_trap_lifecycle(self) -> None:
        completed = subprocess.run(
            ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario"],
            input=json.dumps(self.entry), text=True, capture_output=True, check=True,
        )
        result = json.loads(completed.stdout)
        report = authored_trap_death_report(result, trap_id="fatal-pit", damage=14)
        self.assertEqual("pass", report["status"], report)
        self.assertEqual(1, result["readout"]["public"]["blstats_named"]["time"])


if __name__ == "__main__":
    unittest.main()
