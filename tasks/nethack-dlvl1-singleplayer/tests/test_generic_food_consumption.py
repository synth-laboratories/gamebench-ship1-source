"""Parity coverage for authored food and monster-corpse consumption."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust
from shared.task_resolve import resolve_task


def food_task(*, seed: int, hunger: int, nutrition: int, quantity: int = 1) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 12):
        terrain[5][x] = "."
    return {
        "task_id": f"generic-food-{seed}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 5},
            "inventory": [{
                "id": f"ration-{seed}",
                "letter": "a",
                "kind": "%",
                "name": f"a ration {seed}",
                "quantity": quantity,
                "nutrition": nutrition,
            }],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": hunger},
        },
        "actions": [],
    }


def assert_lanes_match(test: unittest.TestCase, task: dict[str, object]) -> dict[str, object]:
    python = run_python(task)
    rust = run_rust(task)
    test.assertEqual(python["readout"], rust["readout"])
    test.assertEqual(python["events"], rust["events"])
    return python


def rust_restore(checkpoint: bytes, actions: list[int | str]) -> dict[str, object]:
    completed = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "scenario",
            "--",
            "--checkpoint-replay-stdin",
        ],
        input=json.dumps({"checkpoint": checkpoint.decode("utf-8"), "actions": actions}),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


class GenericFoodConsumptionTests(unittest.TestCase):
    def test_eat_consumes_one_stack_unit_and_updates_hunger_band(self) -> None:
        task = food_task(seed=401, hunger=490, nutrition=320, quantity=3)
        task["actions"] = ["Command.EAT", 24]
        result = assert_lanes_match(self, task)

        private = result["readout"]["private"]
        self.assertEqual(2, private["inventory"][0]["quantity"])
        self.assertEqual(809, private["hunger"])
        self.assertEqual("Not Hungry", private["hunger_state"])
        self.assertEqual(1, result["readout"]["public"]["blstats_named"]["time"])
        self.assertTrue(any("Eat(a ration 401)" in event for event in result["events"]))

    def test_eat_caps_at_satiation_limit_before_turn_drain(self) -> None:
        task = food_task(seed=402, hunger=1950, nutrition=320)
        task["actions"] = ["Command.EAT", 24]
        result = assert_lanes_match(self, task)
        private = result["readout"]["private"]
        self.assertEqual(1999, private["hunger"])
        self.assertEqual("Satiated", private["hunger_state"])
        self.assertEqual([], private["inventory"])

    def test_randomized_authored_food_variants_match_across_both_lanes(self) -> None:
        for seed in range(403, 411):
            with self.subTest(seed=seed):
                task = food_task(
                    seed=seed,
                    hunger=(seed * 97) % 1951,
                    nutrition=75 + (seed * 53) % 700,
                    quantity=1 + seed % 4,
                )
                task["actions"] = ["Command.EAT", 24]
                assert_lanes_match(self, task)

    def test_killed_authored_monster_corpse_can_be_picked_up_and_eaten(self) -> None:
        task = food_task(seed=411, hunger=900, nutrition=200)
        level = task["level_dump"]
        level["inventory"] = []
        level["hero"] = {"x": 5, "y": 5}
        level["monsters"] = [{
            "id": "food-rat",
            "name": "food rat",
            "char": "r",
            "position": {"x": 6, "y": 5},
            "hp": 1,
            "attack": 1,
            "experience": 2,
            "armor_class": 1,
            "level": 1,
            "to_hit": 0,
            "damage_dice": 1,
            "damage_sides": 1,
            "corpse": {"nutrition": 200},
        }]
        task["rules"]["autopickup"] = True
        task["actions"] = [
            "Command.FIGHT",
            "CompassDirection.E",
            "CompassDirection.E",
            "Command.EAT",
            24,
        ]
        result = assert_lanes_match(self, task)
        private = result["readout"]["private"]
        self.assertEqual([], private["monsters"])
        self.assertEqual([], private["floor_items"])
        self.assertEqual([], private["inventory"])
        self.assertEqual(1097, private["hunger"])
        self.assertEqual("Not Hungry", private["hunger_state"])
        self.assertTrue(any("MonsterDrop(food rat," in event for event in result["events"]))
        self.assertTrue(any("Eat(a food rat corpse)" in event for event in result["events"]))

    def test_checkpoint_preserves_eat_inventory_prompt_and_hunger_transition(self) -> None:
        task = food_task(seed=412, hunger=180, nutrition=260, quantity=2)
        resolved = resolve_task(task)
        engine = NethackDlvl1Engine()
        engine.reset(resolved)
        engine.step("Command.EAT")
        checkpoint = engine.checkpoint_bytes()

        engine.step(24)
        restored = rust_restore(checkpoint, [24])
        self.assertEqual(engine.symbolic_readout(), restored["projection"])
        self.assertEqual("Hungry", engine.state["hunger_state"])
        self.assertEqual(439, engine.state["hunger"])


if __name__ == "__main__":
    unittest.main()
