"""Parity coverage for authored AUTOPICKUP state and movement pickup."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def pickup_task(seed: int = 501, *, enabled: bool = False) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 9):
        terrain[5][x] = "."
    return {
        "task_id": f"generic-autopickup-{seed}-{enabled}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": enabled, "auto_more": "raw_explicit", "vision_radius": 5},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 3, "y": 5},
            "objects": [{
                "id": "autopickup-ration",
                "kind": "%",
                "name": "a ration",
                "position": {"x": 5, "y": 5},
                "nutrition": 500,
                "quantity": 2,
            }],
            "monsters": [],
            "traps": [],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
    }


class GenericAutopickupTests(unittest.TestCase):
    def assert_lanes_match(self, task: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        return python, rust

    def test_toggle_controls_later_movement_pickup_without_consuming_time(self) -> None:
        task = pickup_task()
        task["actions"] = [
            "CompassDirection.E",
            "Command.AUTOPICKUP",
            "CompassDirection.E",
        ]
        python, _ = self.assert_lanes_match(task)
        private = python["readout"]["private"]
        self.assertTrue(private["autopickup"])
        self.assertEqual(2, private["time"])
        self.assertEqual([], private["floor_items"])
        self.assertEqual(2, private["inventory"][0]["quantity"])
        self.assertTrue(any("Autopickup(on)" in event for event in python["events"]))
        self.assertTrue(any("Pickup(a ration)" in event for event in python["events"]))

    def test_rule_enabled_autopickup_applies_on_the_first_move(self) -> None:
        task = pickup_task(seed=502, enabled=True)
        task["actions"] = ["CompassDirection.E", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        private = python["readout"]["private"]
        self.assertTrue(private["autopickup"])
        self.assertEqual(2, private["time"])
        self.assertEqual([], private["floor_items"])
        self.assertEqual("autopickup-ration", private["inventory"][0]["id"])

    def test_authored_capacity_blocks_heavy_pickup_in_both_lanes(self) -> None:
        task = pickup_task(seed=503)
        task["level_dump"]["objects"][0].update({"position": {"x": 3, "y": 5}, "weight": 6})
        task["level_dump"]["metadata"]["capacity"] = 5
        task["actions"] = ["Command.PICKUP"]
        python, _ = self.assert_lanes_match(task)
        private = python["readout"]["private"]
        self.assertEqual([], private["inventory"])
        self.assertEqual(6, private["floor_items"][0]["weight"])
        self.assertEqual(5, private["capacity"])
        self.assertEqual(0, private["inventory_weight"])
        self.assertEqual("You cannot carry that much.", python["readout"]["public"]["message"])

    def test_authored_capacity_allows_weighted_pickup_and_reports_burden(self) -> None:
        task = pickup_task(seed=504)
        task["level_dump"]["objects"][0].update({"position": {"x": 3, "y": 5}, "quantity": 1, "weight": 4})
        task["level_dump"]["metadata"]["capacity"] = 5
        task["actions"] = ["Command.PICKUP"]
        python, _ = self.assert_lanes_match(task)
        private = python["readout"]["private"]
        self.assertEqual([], private["floor_items"])
        self.assertEqual(4, private["inventory_weight"])
        self.assertEqual(0, python["readout"]["public"]["blstats_named"]["capacity"])

    def test_randomized_autopickup_toggles_and_travel_match_across_lanes(self) -> None:
        for seed in range(16):
            with self.subTest(seed=seed):
                task = pickup_task(seed=510 + seed, enabled=seed % 2 == 0)
                task["level_dump"]["objects"][0]["position"] = {"x": 4 + (seed % 3), "y": 5}
                task["actions"] = [
                    "Command.AUTOPICKUP",
                    "Command.TRAVEL", "CompassDirection.E",
                    "Command.AUTOPICKUP",
                    "Command.TRAVEL", "CompassDirection.W",
                    "MiscDirection.WAIT",
                ]
                self.assert_lanes_match(task)


if __name__ == "__main__":
    unittest.main()
