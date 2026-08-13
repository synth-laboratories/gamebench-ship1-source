"""Parity coverage for authored inspection and turning commands."""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def room_task(seed: int = 311) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for y in range(3, 8):
        for x in range(3, 11):
            terrain[y][x] = "."
    terrain[4][4] = " "
    return {
        "task_id": f"generic-inspection-{seed}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 5},
            "objects": [
                {"id": "inspection-ration", "kind": "%", "name": "a ration", "position": {"x": 6, "y": 5}, "nutrition": 500},
            ],
            "monsters": [
                {
                    "id": "inspection-goblin",
                    "name": "goblin",
                    "char": "g",
                    "position": {"x": 5, "y": 4},
                    "hp": 4,
                    "movement": "stationary",
                    "peaceful": True,
                },
            ],
            "traps": [
                {"id": "inspection-web", "kind": "web", "position": {"x": 5, "y": 6}, "seen": True},
            ],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "wisdom": 18},
        },
    }


class GenericInspectionTests(unittest.TestCase):
    def assert_lanes_match(self, task: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        return python, rust

    def test_look_and_glance_report_visible_authored_cells_without_time(self) -> None:
        task = room_task()
        task["actions"] = [
            "Command.LOOK", "CompassDirection.N",
            "Command.GLANCE", "CompassDirection.E",
            "Command.LOOK", "CompassDirection.S",
        ]
        python, _ = self.assert_lanes_match(task)
        public = python["readout"]["public"]
        private = python["readout"]["private"]
        self.assertEqual("You see a web trap.", public["message"])
        self.assertEqual(0, private["time"])
        self.assertEqual("normal", public["input_mode"]["kind"])
        self.assertTrue(any("Look(5,4)" in event for event in python["events"]))
        self.assertTrue(any("Glance(6,5)" in event for event in python["events"]))
        self.assertTrue(any("Look(5,6)" in event for event in python["events"]))

    def test_inspection_is_visibility_gated(self) -> None:
        task = room_task(seed=312)
        task["actions"] = ["Command.GLANCE", "CompassDirection.NW"]
        python, _ = self.assert_lanes_match(task)
        self.assertEqual("You cannot see there.", python["readout"]["public"]["message"])
        self.assertEqual(0, python["readout"]["private"]["time"])
        self.assertTrue(any("Glance(4,4)" in event for event in python["events"]))

    def test_turn_undead_applies_temporary_fleeing_status_and_actor_pass(self) -> None:
        task = room_task(seed=313)
        task["level_dump"]["objects"] = []
        task["level_dump"]["monsters"] = [{
            "id": "turnable-zombie",
            "name": "zombie",
            "char": "Z",
            "position": {"x": 6, "y": 5},
            "hp": 8,
            "undead": True,
            "turn_difficulty": 1,
            "movement": "stationary",
            "speed": 1,
        }]
        task["actions"] = ["Command.TURN"]
        python, _ = self.assert_lanes_match(task)
        monster = python["readout"]["private"]["monsters"][0]
        self.assertEqual({"x": 7, "y": 4}, monster["position"])
        self.assertEqual(2, monster["status_effects"]["fleeing"])
        self.assertEqual(1, python["readout"]["private"]["time"])
        self.assertTrue(any("TurnUndead(zombie,success)" in event for event in python["events"]))
        self.assertTrue(any("MonsterMove(zombie,7,4)" in event for event in python["events"]))

    def test_randomized_inspection_and_turn_tapes_match_across_lanes(self) -> None:
        for seed in range(16):
            with self.subTest(seed=seed):
                task = room_task(seed=320 + seed)
                task["level_dump"]["metadata"]["wisdom"] = 8 + (seed % 12)
                undead = deepcopy(task["level_dump"]["monsters"][0])
                undead.update({
                    "id": f"turnable-{seed}",
                    "name": "ghoul",
                    "char": "G",
                    "position": {"x": 6, "y": 5},
                    "undead": True,
                    "turn_difficulty": 6 + (seed % 8),
                    "movement": "stationary",
                })
                task["level_dump"]["monsters"] = [undead]
                task["actions"] = [
                    "Command.LOOK", "CompassDirection.E",
                    "Command.TURN",
                    "Command.GLANCE", "CompassDirection.W",
                    "MiscDirection.WAIT",
                ]
                self.assert_lanes_match(task)


if __name__ == "__main__":
    unittest.main()
