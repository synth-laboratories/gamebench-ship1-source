"""Parity coverage for authored mount/dismount behavior."""

from __future__ import annotations

import unittest

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def riding_task(seed: int = 161, *, mountable: bool = True) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 14):
        terrain[4][x] = "."
    return {
        "task_id": f"generic-riding-{seed}-{mountable}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 4},
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
            "traps": [{
                "id": "dismount-trap",
                "kind": "pit",
                "damage": 2,
                "position": {"x": 5, "y": 4},
                "one_shot": True,
            }],
            "monsters": [{
                "id": "riding-goat",
                "name": "riding goat",
                "char": "q",
                "position": {"x": 6, "y": 4},
                "hp": 8,
                "peaceful": True,
                "pet": True,
                "mountable": mountable,
                "movement": "stationary",
            }],
        },
    }


class GenericRidingTests(unittest.TestCase):
    def test_mount_move_and_directional_dismount_match(self) -> None:
        task = riding_task()
        task["actions"] = [
            "Command.RIDE", "CompassDirection.E",
            "CompassDirection.E",
            "Command.RIDE", "CompassDirection.W",
        ]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        self.assertEqual("", python["readout"]["private"]["riding"])
        self.assertEqual(18, python["readout"]["private"]["hp"])
        self.assertEqual((5, 4), (python["readout"]["private"]["hero"]["x"], python["readout"]["private"]["hero"]["y"]))
        self.assertEqual({"x": 6, "y": 4}, python["readout"]["private"]["monsters"][0]["position"])
        self.assertEqual(3, python["readout"]["public"]["blstats_named"]["time"])
        self.assertTrue(any("Ride(riding goat)" in event for event in python["events"]))
        self.assertTrue(any("Dismount(riding goat)" in event for event in python["events"]))

    def test_missing_or_nonmountable_targets_do_not_consume_turns(self) -> None:
        for task in (riding_task(seed=162), riding_task(seed=163, mountable=False)):
            task["level_dump"]["monsters"][0]["position"] = {"x": 8, "y": 4}
            task["actions"] = ["Command.RIDE", "CompassDirection.E"]
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"])
            self.assertEqual(0, python["readout"]["public"]["blstats_named"]["time"])
            self.assertEqual("", python["readout"]["private"]["riding"])

    def test_randomized_mount_tapes_match_across_both_lanes(self) -> None:
        for seed in range(164, 180):
            task = riding_task(seed=seed)
            task["actions"] = [
                "Command.RIDE", "CompassDirection.E",
                "CompassDirection.E", "MiscDirection.WAIT",
                "Command.RIDE", "CompassDirection.W",
            ]
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"], f"seed {seed}")
            self.assertEqual(python["events"], rust["events"], f"events seed {seed}")


if __name__ == "__main__":
    unittest.main()
