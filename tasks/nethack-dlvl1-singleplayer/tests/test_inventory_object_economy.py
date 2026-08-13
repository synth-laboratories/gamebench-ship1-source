"""Cross-lane regression coverage for ordinary inventory stacks."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from scripts.rust_scenario import run_scenario
from shared.task_resolve import resolve_task


def stacked_object_task() -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x, cell in enumerate("|@....|", start=3):
        terrain[4][x] = cell
    return {
        "task_id": "inventory-stack-economy",
        "seed": 23,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "inventory": [
                {
                    "id": "ration",
                    "letter": "a",
                    "kind": "%",
                    "name": "a food ration",
                    "quantity": 2,
                    "nutrition": 600,
                },
            ],
            "objects": [
                {
                    "id": "floor-ration",
                    "position": {"x": 4, "y": 4},
                    "kind": "%",
                    "name": "a food ration",
                    "quantity": 3,
                    "nutrition": 600,
                },
            ],
            "metadata": {"hp": 14, "hp_max": 14, "hunger": 900},
        },
    }


class InventoryObjectEconomyTests(unittest.TestCase):
    def test_pickup_merges_and_consumption_decrements_a_stack_in_both_lanes(self) -> None:
        task = stacked_object_task()
        resolved = resolve_task(task)
        python = NethackDlvl1Engine()
        python.reset(resolved)
        python_trace = [python.public_projection()]
        for action in (61, 35, 24):  # PICKUP, EAT, inventory letter `a`
            python.step(action)
            python_trace.append(python.public_projection())

        rust = run_scenario({**task, "actions": [61, 35, 24]}, ("--trace-stdin",))
        rust_trace = list(rust["snapshots"])
        self.assertEqual(python_trace, rust_trace)

        self.assertEqual(5, python_trace[1]["inventory"]["items"][0]["quantity"])
        self.assertEqual("What do you want to eat? [a or ?*]", python_trace[2]["message"])
        self.assertEqual(4, python_trace[3]["inventory"]["items"][0]["quantity"])
        self.assertEqual(1498, python.private_projection()["hunger"])
        self.assertEqual(2, python_trace[3]["blstats_named"]["time"])
        self.assertEqual([], python.private_projection()["floor_items"])

    def test_drop_moves_the_remaining_stack_back_to_the_floor_in_both_lanes(self) -> None:
        task = stacked_object_task()
        resolved = resolve_task(task)
        python = NethackDlvl1Engine()
        python.reset(resolved)
        for action in (61, 35, 24, 33, 24, 19):  # pickup/eat/a, drop/a/full-stack
            python.step(action)

        rust = run_scenario({**task, "actions": [61, 35, 24, 33, 24, 19]})
        self.assertEqual(python.public_projection(), rust["readout"]["public"])
        self.assertEqual(python.private_projection(), rust["readout"]["private"])
        self.assertEqual([], python.private_projection()["inventory"])
        floor = python.private_projection()["floor_items"]
        self.assertEqual(1, len(floor))
        self.assertEqual(4, floor[0]["quantity"])
        self.assertEqual({"x": 4, "y": 4}, floor[0]["position"])
        self.assertEqual(3, python.public_projection()["blstats_named"]["time"])

    def test_drop_merges_with_an_existing_floor_stack_in_both_lanes(self) -> None:
        task = stacked_object_task()
        resolved = resolve_task(task)
        python = NethackDlvl1Engine()
        python.reset(resolved)
        python.step(33)  # DROP
        python.step(24)  # inventory letter `a`
        python.step(19)  # empty quantity submission means full stack

        rust = run_scenario({**task, "actions": [33, 24, 19]})
        self.assertEqual(python.public_projection(), rust["readout"]["public"])
        self.assertEqual(python.private_projection(), rust["readout"]["private"])
        self.assertEqual([], python.private_projection()["inventory"])
        floor = python.private_projection()["floor_items"]
        self.assertEqual(1, len(floor))
        self.assertEqual(5, floor[0]["quantity"])


if __name__ == "__main__":
    unittest.main()
