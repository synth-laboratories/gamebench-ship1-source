"""Regression contract for source-observed empty stair and floor pickup."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.compare_nle_discrepancies import fixture_task, python_step_projections, rust_step_projections
from scripts.verify_known_underlay_pickup import FIXED_STAIR_MESSAGE, expected_message_raw


def snapshots(fixture: str) -> list[dict[str, object]]:
    path = TASK_DIR / "fixtures" / "nle_oracle" / fixture / "snapshots.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def action_records(fixture: str) -> list[dict[str, object]]:
    path = TASK_DIR / "fixtures" / "nle_oracle" / fixture / "actions.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def cell(snapshot: dict[str, object], x: int, y: int) -> str:
    projection = snapshot["projection"]
    assert isinstance(projection, dict)
    chars = projection["chars"]
    assert isinstance(chars, list) and isinstance(chars[y], list)
    return chr(int(chars[y][x]))


def raw_message(snapshot: dict[str, object]) -> list[int]:
    projection = snapshot["projection"]
    assert isinstance(projection, dict)
    message = projection["message_raw"]
    assert isinstance(message, list)
    return [int(value) for value in message]


class KnownUnderlayPickupTests(unittest.TestCase):
    def assert_frozen_parity(self, fixture: str) -> list[dict[str, object]]:
        fixture_dir = TASK_DIR / "fixtures" / "nle_oracle" / fixture
        task, actions, _ = fixture_task(fixture_dir)
        python_trace = python_step_projections(task, actions)
        rust_trace = rust_step_projections(task, actions)
        self.assertEqual(python_trace, rust_trace)
        return python_trace

    def test_observed_reset_stair_pickup_is_exact_message_only_in_both_lanes(self) -> None:
        fixture = "val-stair-pickup-seed-10"
        records = action_records(fixture)
        source = snapshots(fixture)
        self.assertEqual(["CompassDirection.E", "CompassDirection.W", "Command.PICKUP"], [record["action_name"] for record in records])

        reset = source[0]
        projection = reset["projection"]
        assert isinstance(projection, dict)
        blstats = projection["blstats"]
        assert isinstance(blstats, list)
        origin_x, origin_y = int(blstats[0]), int(blstats[1])
        # The reset glyph is @, so this source state is not sufficient evidence.
        self.assertEqual("@", cell(reset, origin_x, origin_y))
        # After moving away, the raw NLE screen—not a terrain annotation—shows
        # the underlay before the return and eventual pickup.
        self.assertEqual("<", cell(source[1], origin_x, origin_y))
        returned = source[2]["projection"]
        assert isinstance(returned, dict)
        self.assertEqual([origin_x, origin_y], returned["blstats"][:2])

        expected_raw = expected_message_raw(FIXED_STAIR_MESSAGE, len(raw_message(source[3])))
        self.assertEqual(expected_raw, raw_message(source[3]))
        self.assertEqual(int(returned["blstats"][20]), int(source[3]["projection"]["blstats"][20]))

        trace = self.assert_frozen_parity(fixture)
        self.assertEqual(expected_raw, trace[3]["message_raw"])
        self.assertEqual(trace[2]["blstats"], trace[3]["blstats"])

    def test_observed_floor_pickup_has_distinct_exact_message_and_zero_turn_cost(self) -> None:
        fixture = "val-east-pickup-seed-20260725"
        records = action_records(fixture)
        source = snapshots(fixture)
        self.assertEqual(["CompassDirection.E", "Command.PICKUP"], [record["action_name"] for record in records])
        reset = source[0]["projection"]
        after_move = source[1]["projection"]
        assert isinstance(reset, dict) and isinstance(after_move, dict)
        x, y = (int(after_move["blstats"][0]), int(after_move["blstats"][1]))
        self.assertEqual(".", chr(int(reset["chars"][y][x])))
        expected = "There is nothing here to pick up."
        expected_raw = expected_message_raw(expected, len(raw_message(source[2])))
        self.assertEqual(expected_raw, raw_message(source[2]))
        self.assertEqual(int(after_move["blstats"][20]), int(source[2]["projection"]["blstats"][20]))

        trace = self.assert_frozen_parity(fixture)
        self.assertEqual(expected_raw, trace[2]["message_raw"])
        self.assertEqual(trace[1]["blstats"], trace[2]["blstats"])


if __name__ == "__main__":
    unittest.main()
