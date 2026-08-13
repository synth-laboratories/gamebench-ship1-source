"""Cross-lane coverage for authored item effects and timed statuses."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def item_effect_task() -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 16):
        terrain[4][x] = "."
    return {
        "task_id": "generic-item-effects",
        "seed": 23,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 3},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 4},
            "inventory": [
                {"id": "healing-potion", "letter": "a", "kind": "!", "name": "a healing potion", "effect": "healing"},
                {"id": "speed-potion", "letter": "b", "kind": "!", "name": "a speed potion", "effect": "speed"},
                {"id": "poison-potion", "letter": "c", "kind": "!", "name": "a poison potion", "effect": "poison"},
                {"id": "mapping-scroll", "letter": "d", "kind": "?", "name": "a mapping scroll", "effect": "mapping"},
                {"id": "teleport-wand", "letter": "e", "kind": "/", "name": "a teleport wand", "effect": "teleport", "quantity": 2},
            ],
            "metadata": {"hp": 20, "hp_max": 20, "energy": 0, "energy_max": 10, "hunger": 900, "ac": 100},
        },
        "actions": [
            "Command.QUAFF", 24,
            "Command.QUAFF", 6,
            "CompassDirection.E",
            "Command.QUAFF", 30,
            "MiscDirection.WAIT",
            "Command.READ", 33,
            "Command.ZAP", 35, "CompassDirection.N",
        ],
    }


class GenericItemEffectsTests(unittest.TestCase):
    def test_generic_inventory_display_accepts_authored_object_classes(self) -> None:
        task = item_effect_task()
        task["task_id"] = "generic-inventory-display"
        task["level_dump"]["inventory"] = [{
            "id": "odd-artifact",
            "letter": "a",
            "kind": "*",
            "name": "an odd artifact",
        }]
        task["actions"] = ["Command.INVENTORY"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual("inventory_display", python["readout"]["public"]["input_mode"]["kind"])
        self.assertEqual("a", python["readout"]["public"]["inventory"]["items"][0]["letter"])

    def test_light_expands_live_fov_and_expires_without_erasing_underlay(self) -> None:
        def light_task(actions: list[object], task_id: str) -> dict[str, object]:
            terrain = [[" "] * 79 for _ in range(21)]
            for x in range(2, 14):
                terrain[5][x] = "."
            return {
                "task_id": task_id,
                "seed": 31,
                "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 3},
                "level_dump": {
                    "terrain": ["".join(row) for row in terrain],
                    "hero": {"x": 3, "y": 5},
                    "inventory": [{"id": "lamp", "letter": "a", "kind": "!", "name": "a lamp", "effect": "light"}],
                    "monsters": [{
                        "id": "lit-watcher",
                        "name": "lit watcher",
                        "char": "w",
                        "position": {"x": 9, "y": 5},
                        "hp": 4,
                        "peaceful": True,
                        "movement": "stationary",
                    }],
                    "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
                },
                "actions": actions,
            }

        lit = light_task(["Command.QUAFF", 24], "generic-light-live-fov")
        python = run_python(lit)
        rust = run_rust(lit)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual("w", python["readout"]["public"]["chars"][5][9])
        self.assertGreater(python["readout"]["private"]["status_effects"]["light"], 0)

        expired = light_task(["Command.QUAFF", 24, "MiscDirection.WAIT", "MiscDirection.WAIT", "MiscDirection.WAIT", "MiscDirection.WAIT"], "generic-light-expiry")
        python = run_python(expired)
        rust = run_rust(expired)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(".", python["readout"]["public"]["chars"][5][9])
        self.assertTrue(any("StatusExpired(light)" in event for event in python["events"]))

    def test_effects_statuses_prompts_and_rng_match_both_lanes(self) -> None:
        task = item_effect_task()
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        private = python["readout"]["private"]
        self.assertEqual(16, private["hp"])
        self.assertIn("poisoned", private["status_effects"])
        self.assertIn("speed", private["status_effects"])
        self.assertEqual(1, private["inventory"][0]["quantity"] if private["inventory"] else 0)
        self.assertTrue(any("MapRevealed(all)" in event for event in python["events"]))
        self.assertTrue(any("Teleport(hero)" in event for event in python["events"]))
        self.assertTrue(any("StatusTick(poisoned)" in event for event in python["events"]))
        self.assertTrue(any("Move(7,4)" in event for event in python["events"]))

    def test_generic_item_selection_rejects_wrong_class_and_applies_tool_effects(self) -> None:
        task = item_effect_task()
        task["task_id"] = "generic-item-selection-contract"
        task["level_dump"]["inventory"] = [
            {"id": "dagger", "letter": "a", "kind": ")", "name": "a dagger", "damage": 2},
            {"id": "mapping-tool", "letter": "b", "kind": "(", "name": "a mapping tool", "effect": "mapping"},
        ]
        task["actions"] = [
            "Command.QUAFF", 24, "Command.ESC",
            "Command.APPLY", 6,
        ]
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertTrue(all(python["readout"]["private"]["seen"][4][x] for x in range(2, 16)))
        self.assertTrue(any("That is not a potion." in event for event in python["events"]))
        self.assertTrue(any("Apply(a mapping tool)" in event for event in python["events"]))

    def test_generic_equipment_requires_matching_state_and_clears_consumed_slots(self) -> None:
        task = {
            "task_id": "generic-equipment-state",
            "seed": 29,
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
            "level_dump": {
                "terrain": [" " * 79 for _ in range(21)],
                "hero": {"x": 4, "y": 4},
                "inventory": [
                    {"id": "mail", "letter": "a", "kind": "[", "name": "a suit of mail", "armor": 3},
                    {"id": "ring", "letter": "b", "kind": "\"", "name": "a ring"},
                    {"id": "dagger", "letter": "c", "kind": ")", "name": "a dagger", "damage": 2},
                    {"id": "dart", "letter": "d", "kind": ")", "name": "a dart", "damage": 1},
                ],
                "metadata": {"hp": 20, "hp_max": 20, "ac": 12, "hunger": 900},
            },
            "actions": [
                "Command.WEAR", 24,
                "Command.WEAR", 6, "Command.ESC",
                "Command.TAKEOFF", 6, "Command.ESC",
                "Command.TAKEOFF", 24,
                "Command.PUTON", 6,
                "Command.REMOVE", 6,
                "Command.REMOVE", 6, "Command.ESC",
                "Command.QUIVER", 32,
                "Command.THROW", 32, "CompassDirection.E",
                "Command.WIELD", 29,
                "Command.DROP", 29, "Command.ESC",
            ],
        }
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        private = python["readout"]["private"]
        self.assertEqual(12, private["ac"])
        self.assertEqual("", private["worn"])
        self.assertEqual([], private["accessories"])
        self.assertEqual("dagger", private["wielded"])
        self.assertEqual("", private["quiver"])
        self.assertTrue(any("You are already wearing something." in event for event in python["events"]))
        self.assertTrue(any("You are not wearing that." in event for event in python["events"]))
        self.assertTrue(any("You cannot drop something you are using." in event for event in python["events"]))


if __name__ == "__main__":
    unittest.main()
