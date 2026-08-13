"""Cross-lane coverage for actor occupancy during authored pathing."""

from __future__ import annotations

import unittest

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def blocked_item_task(seed: int = 451, *, blocker_x: int = 8, seeker_x: int = 5) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 13):
        terrain[5][x] = "."
    return {
        "task_id": f"generic-actor-occupied-goal-{seed}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 6},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 2, "y": 5},
            "objects": [{
                "id": "guarded-ration",
                "kind": "%",
                "name": "a guarded ration",
                "position": {"x": blocker_x, "y": 5},
                "nutrition": 600,
            }],
            "monsters": [
                {
                    "id": "blocking-mule",
                    "name": "blocking mule",
                    "char": "m",
                    "position": {"x": blocker_x, "y": 5},
                    "hp": 8,
                    "peaceful": True,
                    "movement": "stationary",
                },
                {
                    "id": "ration-seeker",
                    "name": "ration seeker",
                    "char": "r",
                    "position": {"x": seeker_x, "y": 5},
                    "hp": 8,
                    "movement": "seek_items",
                    "pickup": True,
                    "vision": 20,
                },
            ],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
        "actions": ["MiscDirection.WAIT"] * 4,
    }


class GenericActorCollisionTests(unittest.TestCase):
    def test_item_goal_occupied_by_actor_never_allows_overlap(self) -> None:
        task = blocked_item_task()
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        monsters = python["readout"]["private"]["monsters"]
        positions = [tuple(monster["position"].values()) for monster in monsters]
        self.assertEqual(len(positions), len(set(positions)))
        seeker = next(monster for monster in monsters if monster["id"] == "ration-seeker")
        blocker = next(monster for monster in monsters if monster["id"] == "blocking-mule")
        self.assertEqual({"x": 7, "y": 5}, seeker["position"])
        self.assertEqual(blocker["position"], {"x": 8, "y": 5})
        self.assertEqual(1, len(python["readout"]["private"]["floor_items"]))
        self.assertTrue(all("MonsterPickup(ration seeker" not in event for event in python["events"]))

    def test_randomized_occupied_item_goals_preserve_distinct_actor_cells(self) -> None:
        for seed in range(452, 468):
            blocker_x = 7 + (seed % 3)
            seeker_x = 3 + (seed % 3)
            task = blocked_item_task(seed, blocker_x=blocker_x, seeker_x=seeker_x)
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"], f"seed={seed}")
            self.assertEqual(python["events"], rust["events"], f"seed={seed}")
            positions = [
                (monster["position"]["x"], monster["position"]["y"])
                for monster in python["readout"]["private"]["monsters"]
            ]
            self.assertEqual(len(positions), len(set(positions)), f"seed={seed}")


if __name__ == "__main__":
    unittest.main()
