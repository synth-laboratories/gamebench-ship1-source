"""Parity coverage for generic supercover line-of-sight corners."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def square_floor() -> list[str]:
    terrain = [[" "] * 79 for _ in range(21)]
    for y in range(3, 10):
        for x in range(3, 10):
            terrain[y][x] = "."
    return ["".join(row) for row in terrain]


def corner_task(*, task_id: str, seed: int, east_wall: bool, south_wall: bool) -> dict[str, object]:
    terrain = square_floor()
    if east_wall:
        terrain[4] = terrain[4][:5] + "|" + terrain[4][6:]
    if south_wall:
        terrain[5] = terrain[5][:4] + "-" + terrain[5][5:]
    return {
        "task_id": task_id,
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
        "level_dump": {
            "terrain": terrain,
            "hero": {"x": 4, "y": 4},
            "monsters": [{
                "id": "corner-target",
                "name": "corner target",
                "char": "m",
                "position": {"x": 6, "y": 6},
                "hp": 4,
                "peaceful": True,
                "movement": "stationary",
            }],
            "objects": [],
            "traps": [],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
    }


class GenericFovCornerTests(unittest.TestCase):
    def assert_lanes_match(self, task: dict[str, object]) -> dict[str, object]:
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        return python

    def test_two_opaque_corner_tiles_hide_diagonal_target(self) -> None:
        task = corner_task(task_id="generic-fov-closed-corner", seed=211, east_wall=True, south_wall=True)
        result = self.assert_lanes_match(task)
        self.assertEqual(".", result["readout"]["public"]["chars"][6][6])

    def test_open_corner_keeps_diagonal_target_visible(self) -> None:
        task = corner_task(task_id="generic-fov-open-corner", seed=212, east_wall=True, south_wall=False)
        result = self.assert_lanes_match(task)
        self.assertEqual("m", result["readout"]["public"]["chars"][6][6])

    def test_corner_visibility_parity_over_wall_combinations(self) -> None:
        for seed in range(16):
            east_wall = bool(seed & 1)
            south_wall = bool(seed & 2)
            task = corner_task(
                task_id=f"generic-fov-corner-{seed}",
                seed=300 + seed,
                east_wall=east_wall,
                south_wall=south_wall,
            )
            result = self.assert_lanes_match(task)
            visible = result["readout"]["public"]["chars"][6][6] == "m"
            self.assertEqual(not (east_wall and south_wall), visible)


if __name__ == "__main__":
    unittest.main()
