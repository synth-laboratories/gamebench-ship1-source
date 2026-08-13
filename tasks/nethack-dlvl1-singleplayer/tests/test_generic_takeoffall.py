"""Parity coverage for the generic all-equipment removal command."""

from __future__ import annotations

import unittest

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def takeoffall_task(seed: int = 181) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 12):
        terrain[4][x] = "."
    return {
        "task_id": f"generic-takeoffall-{seed}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 4},
            "inventory": [
                {"id": "mail", "letter": "a", "kind": "[", "name": "a suit of mail", "armor": 3},
                {"id": "ring", "letter": "b", "kind": "\"", "name": "a ring"},
            ],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 12, "hunger": 900},
        },
    }


class GenericTakeoffAllTests(unittest.TestCase):
    def test_all_equipment_is_removed_in_one_turn(self) -> None:
        task = takeoffall_task()
        task["actions"] = ["Command.WEAR", 24, "Command.PUTON", 6, "Command.TAKEOFFALL"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        private = python["readout"]["private"]
        self.assertEqual(12, private["ac"])
        self.assertEqual("", private["worn"])
        self.assertEqual([], private["accessories"])
        self.assertEqual(3, python["readout"]["public"]["blstats_named"]["time"])
        self.assertTrue(any("TakeoffAll()" in event for event in python["events"]))

    def test_empty_takeoffall_is_a_zero_turn_noop(self) -> None:
        task = takeoffall_task(seed=182)
        task["actions"] = ["Command.TAKEOFFALL"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(0, python["readout"]["public"]["blstats_named"]["time"])
        self.assertEqual("You are not wearing anything.", python["readout"]["public"]["message"])

    def test_randomized_equipment_tapes_match_across_both_lanes(self) -> None:
        for seed in range(183, 199):
            task = takeoffall_task(seed=seed)
            task["actions"] = ["Command.WEAR", 24, "Command.PUTON", 6, "Command.TAKEOFFALL", "Command.TAKEOFFALL"]
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"], f"seed {seed}")
            self.assertEqual(python["events"], rust["events"], f"events seed {seed}")


if __name__ == "__main__":
    unittest.main()
