from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.outcome_assertions import (
    seeded_outcome_report,
    stochastic_contexts,
    transition_outcome,
)


class SeededOutcomeAssertionTests(unittest.TestCase):
    def test_stochastic_context_requires_the_direction_prompt_origin(self) -> None:
        actions = [
            {"step": 1, "input_mode": "normal", "action_name": "Command.KICK"},
            {"step": 2, "input_mode": "direction", "action_name": "CompassDirection.E"},
            {"step": 3, "input_mode": "normal", "action_name": "Command.SEARCH"},
            {"step": 4, "input_mode": "direction", "action_name": "CompassDirection.N"},
        ]

        self.assertEqual(
            [{"step": 2, "command": "Command.KICK", "response": "CompassDirection.E"}],
            stochastic_contexts(actions),
        )

    def test_transition_outcome_includes_stats_message_and_exact_cells(self) -> None:
        before = {
            "chars": [".."],
            "colors": [[7, 7]],
            "glyphs": [[1, 1]],
            "blstats": [5, 9],
            "message": "",
            "message_raw": [],
            "done": False,
        }
        after = {
            "chars": [".+"],
            "colors": [[7, 3]],
            "glyphs": [[1, 9]],
            "blstats": [5, 8],
            "message": "WHAMMM!!!",
            "message_raw": [87],
            "done": False,
        }

        outcome = transition_outcome(before, after)

        self.assertEqual([{"slot": 1, "before": 9, "after": 8, "delta": -1}], outcome["blstats_deltas"])
        self.assertEqual([{"y": 0, "x": 1, "before": ".", "after": "+"}], outcome["char_deltas"])
        self.assertEqual("WHAMMM!!!", outcome["message"])

    def test_report_excludes_outcomes_after_the_trustworthy_prefix(self) -> None:
        snapshots = [
            {"chars": ["."], "colors": [[7]], "glyphs": [[1]], "blstats": [0], "message": "", "message_raw": []},
            {"chars": ["."], "colors": [[7]], "glyphs": [[1]], "blstats": [0], "message": "In what direction?", "message_raw": []},
            {"chars": ["."], "colors": [[7]], "glyphs": [[1]], "blstats": [1], "message": "WHAMMM!!!", "message_raw": []},
        ]
        actions = [
            {"step": 1, "input_mode": "normal", "action_name": "Command.KICK"},
            {"step": 2, "input_mode": "direction", "action_name": "CompassDirection.E"},
        ]

        excluded = seeded_outcome_report(snapshots, snapshots, actions, through_step=1)
        included = seeded_outcome_report(snapshots, snapshots, actions, through_step=2)

        self.assertEqual("not_exercised", excluded["status"])
        self.assertEqual("pass", included["status"])
        self.assertEqual(1, included["comparisons"])

    def test_report_surfaces_the_first_exact_observable_difference(self) -> None:
        expected = [
            {"chars": ["."], "colors": [[7]], "glyphs": [[1]], "blstats": [0], "message": "", "message_raw": []},
            {"chars": ["."], "colors": [[7]], "glyphs": [[1]], "blstats": [0], "message": "In what direction?", "message_raw": []},
            {"chars": ["."], "colors": [[7]], "glyphs": [[1]], "blstats": [1], "message": "Ouch!", "message_raw": [79]},
        ]
        actual = [dict(snapshot) for snapshot in expected]
        actual[2] = {**actual[2], "message": "You kick at empty space."}
        actions = [
            {"step": 1, "input_mode": "normal", "action_name": "Command.KICK"},
            {"step": 2, "input_mode": "direction", "action_name": "CompassDirection.E"},
        ]

        report = seeded_outcome_report(expected, actual, actions, through_step=2)

        self.assertEqual("errors_found", report["status"])
        self.assertEqual("$.seeded_outcome.message", report["errors"][0]["path"])
        self.assertEqual("Ouch!", report["errors"][0]["expected"])


if __name__ == "__main__":
    unittest.main()
