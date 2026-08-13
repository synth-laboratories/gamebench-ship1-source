"""Parity coverage for authored dynamic light and render underlays."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def light_room() -> list[str]:
    terrain = [[" "] * 79 for _ in range(21)]
    for y in range(4, 8):
        for x in range(2, 18):
            terrain[y][x] = "."
    return ["".join(row) for row in terrain]


def light_task(*, task_id: str, seed: int, source: dict[str, object], object_x: int) -> dict[str, object]:
    return {
        "task_id": task_id,
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 2},
        "level_dump": {
            "terrain": light_room(),
            "hero": {"x": 4, "y": 5},
            "objects": [{
                "id": "lit-underlay-object",
                "kind": "*",
                "name": "a gem",
                "position": {"x": object_x, "y": 5},
            }],
            "inventory": [],
            "monsters": [],
            "traps": [],
            "light_sources": [source],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
    }


class GenericDynamicLightTests(unittest.TestCase):
    def assert_lanes_match(self, task: dict[str, object]) -> dict[str, object]:
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        return python

    def test_expiring_light_reveals_then_hides_floor_underlay(self) -> None:
        source = {"id": "short-torch", "position": {"x": 8, "y": 5}, "radius": 4, "duration": 2}
        initial = self.assert_lanes_match(light_task(task_id="generic-light-initial", seed=401, source=source, object_x=11))
        self.assertEqual("*", initial["readout"]["public"]["chars"][5][11])

        one_turn = light_task(task_id="generic-light-one-turn", seed=401, source=source, object_x=11)
        one_turn["actions"] = ["MiscDirection.WAIT"]
        after_one = self.assert_lanes_match(one_turn)
        self.assertEqual("*", after_one["readout"]["public"]["chars"][5][11])

        two_turn = light_task(task_id="generic-light-expired", seed=401, source=source, object_x=11)
        two_turn["actions"] = ["MiscDirection.WAIT", "MiscDirection.WAIT"]
        after_two = self.assert_lanes_match(two_turn)
        self.assertEqual(".", after_two["readout"]["public"]["chars"][5][11])
        self.assertFalse(after_two["readout"]["private"]["light_sources"][0]["active"])
        self.assertTrue(any("LightExpired(short-torch)" in event for event in after_two["events"]))

    def test_hero_following_light_moves_with_the_hero(self) -> None:
        source = {"id": "hero-lamp", "follow": "hero", "radius": 2}
        initial = light_task(task_id="generic-light-follow-initial", seed=402, source=source, object_x=7)
        initial_result = self.assert_lanes_match(initial)
        self.assertEqual(".", initial_result["readout"]["public"]["chars"][5][7])

        moved = light_task(task_id="generic-light-follow-moved", seed=402, source=source, object_x=7)
        moved["actions"] = ["CompassDirection.E"]
        moved_result = self.assert_lanes_match(moved)
        self.assertEqual("*", moved_result["readout"]["public"]["chars"][5][7])

    def test_actor_following_light_moves_and_restores_its_old_underlay(self) -> None:
        task = light_task(
            task_id="generic-light-follows-actor",
            seed=403,
            source={
                "id": "pet-lamp",
                "position": {"x": 10, "y": 5},
                "follow": "lamp-dog",
                "radius": 2,
            },
            object_x=12,
        )
        task["level_dump"]["objects"].append({
            "id": "leading-edge-object",
            "kind": "!",
            "name": "a potion",
            "position": {"x": 7, "y": 5},
        })
        task["level_dump"]["monsters"] = [{
            "id": "lamp-dog",
            "name": "dog",
            "char": "d",
            "position": {"x": 10, "y": 5},
            "hp": 4,
            "attack": 1,
            "pet": True,
            "movement": "follow",
            "vision": 20,
        }]

        initial = self.assert_lanes_match(task)
        self.assertEqual("*", initial["readout"]["public"]["chars"][5][12])
        self.assertEqual(".", initial["readout"]["public"]["chars"][5][7])

        task["actions"] = ["MiscDirection.WAIT"]
        moved = self.assert_lanes_match(task)
        self.assertEqual({"x": 9, "y": 4}, moved["readout"]["private"]["monsters"][0]["position"])
        self.assertEqual("!", moved["readout"]["public"]["chars"][5][7])
        self.assertEqual(".", moved["readout"]["public"]["chars"][5][10])
        self.assertEqual(".", moved["readout"]["public"]["chars"][5][12])

    def test_randomized_source_durations_remain_cross_language_equal(self) -> None:
        for seed in range(12):
            duration = 1 + (seed % 4)
            source_x = 7 + (seed % 5)
            radius = 2 + (seed % 4)
            task = light_task(
                task_id=f"generic-light-random-{seed}",
                seed=500 + seed,
                source={
                    "id": f"torch-{seed}",
                    "position": {"x": source_x, "y": 5},
                    "radius": radius,
                    "duration": duration,
                },
                object_x=min(16, source_x + radius),
            )
            task["actions"] = ["MiscDirection.WAIT", "MiscDirection.WAIT"]
            result = self.assert_lanes_match(task)
            source_state = result["readout"]["private"]["light_sources"][0]
            self.assertEqual(duration > 2, source_state["active"])


if __name__ == "__main__":
    unittest.main()
