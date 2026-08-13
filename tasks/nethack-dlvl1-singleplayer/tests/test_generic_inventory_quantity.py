"""Cross-lane coverage for quantity-aware authored inventory drops."""

from __future__ import annotations

import unittest

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def quantity_task(seed: int = 301, quantity: int = 4) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 14):
        terrain[5][x] = "."
    return {
        "task_id": f"generic-inventory-quantity-{seed}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 5},
            "inventory": [{
                "id": "ration-stack",
                "letter": "a",
                "kind": "%",
                "name": "a ration",
                "quantity": quantity,
            }],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
        "actions": [],
    }


class GenericInventoryQuantityTests(unittest.TestCase):
    def test_partial_drop_splits_stack_and_consumes_one_turn(self) -> None:
        task = quantity_task()
        task["actions"] = ["Command.DROP", 24, "TextCharacters.NUM_1", "MiscAction.MORE"]
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        private = python["readout"]["private"]
        self.assertEqual(3, private["inventory"][0]["quantity"])
        floor = private["floor_items"]
        self.assertEqual(1, len(floor))
        self.assertEqual(1, floor[0]["quantity"])
        self.assertEqual({"x": 5, "y": 5}, floor[0]["position"])
        self.assertEqual(1, python["readout"]["public"]["blstats_named"]["time"])
        self.assertTrue(any("Drop(a ration)" in event for event in python["events"]))

    def test_empty_quantity_submission_drops_whole_stack(self) -> None:
        task = quantity_task(seed=302, quantity=2)
        task["actions"] = ["Command.DROP", 24, "MiscAction.MORE"]
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual([], python["readout"]["private"]["inventory"])
        self.assertEqual(2, python["readout"]["private"]["floor_items"][0]["quantity"])
        self.assertEqual(1, python["readout"]["public"]["blstats_named"]["time"])

    def test_randomized_quantity_tapes_match_across_both_lanes(self) -> None:
        for seed in range(303, 319):
            quantity = 2 + (seed % 7)
            amount = 1 + (seed % quantity)
            task = quantity_task(seed=seed, quantity=quantity)
            task["actions"] = [
                "Command.DROP", 24,
                *[f"TextCharacters.NUM_{digit}" for digit in str(amount)],
                "MiscAction.MORE",
            ]
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"], f"seed={seed}")
            self.assertEqual(python["events"], rust["events"], f"seed={seed}")


if __name__ == "__main__":
    unittest.main()
