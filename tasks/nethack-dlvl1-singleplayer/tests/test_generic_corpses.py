"""Parity coverage for authored monster corpse drops."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust
from tests.test_generic_combat import combat_task


class GenericCorpseTests(unittest.TestCase):
    def assert_lanes_match(self, task: dict[str, object]) -> dict[str, object]:
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        return python

    def test_authored_kill_materializes_an_edible_renderable_corpse(self) -> None:
        task = combat_task(seed=23, armor_class=1, hp=1)
        task["level_dump"]["monsters"][0]["corpse"] = True
        result = self.assert_lanes_match(task)
        private = result["readout"]["private"]
        self.assertEqual([], private["monsters"])
        corpse = private["floor_items"][0]
        self.assertEqual("training-dummy-corpse", corpse["id"])
        self.assertEqual("%", corpse["kind"])
        self.assertEqual("a training dummy corpse", corpse["name"])
        self.assertEqual(200, corpse["nutrition"])
        self.assertEqual({"x": 6, "y": 4}, corpse["position"])
        self.assertEqual("%", result["readout"]["public"]["chars"][4][6])
        self.assertTrue(any("MonsterDrop(training dummy,a training dummy corpse)" in event for event in result["events"]))

    def test_corpse_contract_supports_custom_item_fields_and_explicit_suppression(self) -> None:
        custom = combat_task(seed=23, armor_class=1, hp=1)
        custom["level_dump"]["monsters"][0]["corpse"] = {
            "id": "dummy-carcass",
            "name": "the dummy carcass",
            "nutrition": 333,
            "color": 4,
            "special": 9,
        }
        result = self.assert_lanes_match(custom)
        corpse = result["readout"]["private"]["floor_items"][0]
        self.assertEqual("dummy-carcass", corpse["id"])
        self.assertEqual("the dummy carcass", corpse["name"])
        self.assertEqual(333, corpse["nutrition"])
        self.assertEqual(4, corpse["color"])
        self.assertEqual(9, corpse["special"])

        suppressed = combat_task(seed=23, armor_class=1, hp=1)
        suppressed["level_dump"]["monsters"][0]["corpse"] = False
        suppressed_result = self.assert_lanes_match(suppressed)
        self.assertEqual([], suppressed_result["readout"]["private"]["floor_items"])

        no_corpse = combat_task(seed=23, armor_class=1, hp=1)
        no_corpse["level_dump"]["monsters"][0].update({
            "corpse": True,
            "geno": 16,
            "generation_frequency": 0,
            "corpse_weight": 15,
            "no_corpse": True,
        })
        no_corpse_result = self.assert_lanes_match(no_corpse)
        self.assertEqual([], no_corpse_result["readout"]["private"]["floor_items"])

    def test_randomized_corpse_variants_remain_cross_language_equal(self) -> None:
        for seed in range(12):
            task = combat_task(seed=100 + seed, armor_class=1, hp=1)
            if seed % 3 == 0:
                task["level_dump"]["monsters"][0]["corpse"] = False
            elif seed % 3 == 1:
                task["level_dump"]["monsters"][0]["corpse"] = True
            else:
                task["level_dump"]["monsters"][0]["corpse"] = {
                    "id": f"variant-corpse-{seed}",
                    "nutrition": 100 + seed,
                    "special": seed,
                }
            result = self.assert_lanes_match(task)
            floor_items = result["readout"]["private"]["floor_items"]
            if seed % 3 == 0:
                self.assertEqual([], floor_items)
            else:
                self.assertEqual(1, len(floor_items))
                self.assertEqual("%", floor_items[0]["kind"])


if __name__ == "__main__":
    unittest.main()
