"""Parity coverage for authored repeated directional travel."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def corridor_task(seed: int = 401) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 13):
        terrain[5][x] = "."
    return {
        "task_id": f"generic-travel-{seed}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 4, "y": 5},
            "monsters": [],
            "objects": [],
            "traps": [],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
    }


class GenericTravelTests(unittest.TestCase):
    def assert_lanes_match(self, task: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        return python, rust

    def test_travel_reuses_collision_aware_movement_until_wall(self) -> None:
        task = corridor_task()
        task["actions"] = ["Command.TRAVEL", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        private = python["readout"]["private"]
        self.assertEqual({"x": 12, "y": 5}, {key: private["hero"][key] for key in ("x", "y")})
        self.assertEqual(8, private["time"])
        self.assertEqual("normal", python["readout"]["public"]["input_mode"]["kind"])
        self.assertTrue(any("Travel(8)" in event for event in python["events"]))
        self.assertEqual(8, sum("Move(" in event for event in python["events"]))

    def test_travel_stops_at_a_peaceful_actor_after_consuming_the_attempt(self) -> None:
        task = corridor_task(seed=402)
        task["level_dump"]["monsters"] = [{
            "id": "travel-pet",
            "name": "travel pet",
            "char": "d",
            "position": {"x": 7, "y": 5},
            "hp": 8,
            "pet": True,
            "peaceful": True,
            "movement": "stationary",
        }]
        task["actions"] = ["Command.TRAVEL", "CompassDirection.E"]
        python, _ = self.assert_lanes_match(task)
        hero = python["readout"]["private"]["hero"]
        self.assertEqual({"x": 6, "y": 5}, {key: hero[key] for key in ("x", "y")})
        self.assertEqual(3, python["readout"]["private"]["time"])
        self.assertTrue(any("You stop. Your travel pet is in the way!" in event for event in python["events"]))
        self.assertTrue(any("Travel(3)" in event for event in python["events"]))

    def test_travel_stops_on_a_trap_and_preserves_cross_lane_rng(self) -> None:
        task = corridor_task(seed=403)
        task["level_dump"]["traps"] = [{
            "id": "travel-trap",
            "kind": "pit",
            "damage": 2,
            "position": {"x": 7, "y": 5},
            "rearm": 2,
        }]
        task["actions"] = ["Command.TRAVEL", "CompassDirection.E", "MiscDirection.WAIT"]
        python, _ = self.assert_lanes_match(task)
        hero = python["readout"]["private"]["hero"]
        self.assertEqual({"x": 7, "y": 5}, {key: hero[key] for key in ("x", "y")})
        self.assertEqual(4, python["readout"]["private"]["time"])
        self.assertTrue(any("Trap(pit)" in event for event in python["events"]))
        self.assertTrue(any("Travel(3)" in event for event in python["events"]))

    def test_randomized_travel_tapes_match_across_lanes(self) -> None:
        directions = (
            "CompassDirection.E",
            "CompassDirection.W",
            "CompassDirection.NE",
            "CompassDirection.SE",
        )
        for seed in range(16):
            with self.subTest(seed=seed):
                task = corridor_task(seed=410 + seed)
                task["level_dump"]["hero"] = {"x": 4 + (seed % 3), "y": 5}
                task["actions"] = [
                    "Command.TRAVEL", directions[seed % len(directions)],
                    "Command.TRAVEL", directions[(seed + 1) % len(directions)],
                ]
                self.assert_lanes_match(task)


if __name__ == "__main__":
    unittest.main()
