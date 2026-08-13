"""Cross-lane coverage for reusable obstacle-aware monster movement."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def obstacle_course_task() -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 11):
        terrain[4][x] = "."
        terrain[5][x] = "."
        terrain[6][x] = "."
    # The direct west-to-east route is blocked; the north row is the first
    # shortest legal route and exercises the shared tie-break ordering.
    terrain[5][4] = "|"
    terrain[5][8] = "@"
    return {
        "task_id": "generic-monster-pathing",
        "seed": 23,
        "rules": {
            "max_steps": 0,
            "autopickup": False,
            "auto_more": "raw_explicit",
            "vision_radius": 4,
        },
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "monsters": [
                {
                    "id": "newt",
                    "name": "newt",
                    "char": "n",
                    "position": {"x": 3, "y": 5},
                    "hp": 4,
                    "attack": 0,
                }
            ],
            "metadata": {"hp": 14, "hp_max": 14, "hunger": 900},
        },
    }


class GenericMonsterPathingTests(unittest.TestCase):
    def test_monster_routes_around_wall_in_both_lanes(self) -> None:
        entry = {**obstacle_course_task(), "actions": ["MiscDirection.WAIT"]}
        python = run_python(entry)
        rust = run_rust(entry)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(
            {"x": 3, "y": 4},
            python["readout"]["private"]["monsters"][0]["position"],
        )
        self.assertEqual(1, python["readout"]["public"]["blstats_named"]["time"])

    def test_chasing_monster_never_enters_the_hero_cell(self) -> None:
        task = obstacle_course_task()
        task["task_id"] = "generic-monster-collision-boundary"
        task["level_dump"]["hero"] = {"x": 9, "y": 5}
        task["level_dump"]["monsters"][0]["position"] = {"x": 3, "y": 5}
        task["level_dump"]["metadata"]["hp"] = 100
        task["level_dump"]["metadata"]["hp_max"] = 100
        task["actions"] = ["MiscDirection.WAIT"] * 8
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        hero = python["readout"]["private"]["hero"]
        monsters = python["readout"]["private"]["monsters"]
        self.assertTrue(monsters)
        self.assertTrue(all(monster["position"] != {"x": hero["x"], "y": hero["y"]} for monster in monsters))


if __name__ == "__main__":
    unittest.main()
