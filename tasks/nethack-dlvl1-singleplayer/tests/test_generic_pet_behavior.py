"""Cross-lane coverage for authored pet following and collision separation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def pet_task() -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 15):
        terrain[4][x] = "."
    terrain[3][7] = " "
    return {
        "task_id": "generic-pet-following",
        "seed": 91,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 10, "y": 4},
            "monsters": [
                {
                    "id": "kitten",
                    "name": "kitten",
                    "char": "f",
                    "position": {"x": 4, "y": 4},
                    "hp": 3,
                    "attack": 0,
                    "experience": 0,
                    "pet": True,
                },
                {
                    "id": "hostile",
                    "name": "jackal",
                    "char": "j",
                    "position": {"x": 13, "y": 4},
                    "hp": 4,
                    "attack": 0,
                    "experience": 1,
                    "peaceful": True,
                },
            ],
            "metadata": {"hp": 20, "hp_max": 20, "hunger": 900, "ac": 100},
        },
        "actions": ["MiscDirection.WAIT", "MiscDirection.WAIT", "MiscDirection.WAIT"],
    }


class GenericPetBehaviorTests(unittest.TestCase):
    def test_explicit_food_eating_pet_consumes_floor_item_and_tracks_hunger(self) -> None:
        task = pet_task()
        task["task_id"] = "generic-pet-eating"
        task["level_dump"]["objects"] = [{
            "id": "pet-ration",
            "kind": "%",
            "name": "a ration",
            "position": {"x": 4, "y": 4},
            "nutrition": 600,
        }]
        task["level_dump"]["monsters"][0].update({
            "eat": True,
            "movement": "stationary",
            "hunger": 0,
            "hunger_max": 1000,
        })
        task["actions"] = ["MiscDirection.WAIT"]

        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        kitten = next(monster for monster in python["readout"]["private"]["monsters"] if monster["id"] == "kitten")
        self.assertEqual(600, kitten["hunger"])
        self.assertEqual([], python["readout"]["private"]["floor_items"])
        self.assertTrue(any("MonsterEat(kitten,a ration)" in event for event in python["events"]))

    def test_authored_hunger_drain_reaches_feed_threshold_and_preserves_parity(self) -> None:
        task = pet_task()
        task["task_id"] = "generic-pet-hunger-threshold"
        task["level_dump"]["objects"] = [{
            "id": "threshold-ration",
            "kind": "%",
            "name": "a threshold ration",
            "position": {"x": 4, "y": 4},
            "nutrition": 600,
        }]
        task["level_dump"]["monsters"][0].update({
            "eat": True,
            "movement": "stationary",
            "hunger": 101,
            "hunger_max": 1000,
            "hunger_drain": 1,
            "eat_threshold": 100,
        })
        task["actions"] = ["MiscDirection.WAIT"]

        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        kitten = next(monster for monster in python["readout"]["private"]["monsters"] if monster["id"] == "kitten")
        self.assertEqual(700, kitten["hunger"])
        self.assertEqual([], python["readout"]["private"]["floor_items"])
        self.assertTrue(any("MonsterHungerTick(kitten,101->100)" in event for event in python["events"]))
        self.assertTrue(any("MonsterEat(kitten,a threshold ration)" in event for event in python["events"]))

    def test_authored_starvation_damage_can_remove_a_monster(self) -> None:
        task = pet_task()
        task["task_id"] = "generic-pet-starvation"
        task["level_dump"]["monsters"] = [{
            "id": "starving-pet",
            "name": "starving pet",
            "char": "f",
            "position": {"x": 4, "y": 4},
            "hp": 2,
            "movement": "stationary",
            "pet": True,
            "eat": True,
            "hunger": 1,
            "hunger_drain": 1,
            "starve_damage": 2,
        }]
        task["actions"] = ["MiscDirection.WAIT"]

        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual([], python["readout"]["private"]["monsters"])
        self.assertTrue(any("MonsterStarve(starving pet)" in event for event in python["events"]))
        self.assertTrue(any("MonsterKilled(starving pet)" in event for event in python["events"]))

    def test_pet_follows_without_attacking_or_overlapping_the_hero(self) -> None:
        task = pet_task()
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        monsters = python["readout"]["private"]["monsters"]
        kitten = next(monster for monster in monsters if monster["id"] == "kitten")
        hostile = next(monster for monster in monsters if monster["id"] == "hostile")
        self.assertEqual({"x": 7, "y": 4}, kitten["position"])
        self.assertEqual({"x": 13, "y": 4}, hostile["position"])
        self.assertEqual(20, python["readout"]["private"]["hp"])


if __name__ == "__main__":
    unittest.main()
