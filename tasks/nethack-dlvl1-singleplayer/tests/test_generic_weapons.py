"""Parity coverage for authored weapon swapping and two-weapon state."""

from __future__ import annotations

import unittest

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def weapon_task(seed: int = 201) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 12):
        terrain[4][x] = "."
    return {
        "task_id": f"generic-weapons-{seed}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 4},
            "inventory": [
                {"id": "blade-a", "letter": "a", "kind": ")", "name": "a short sword", "damage": 3},
                {"id": "blade-b", "letter": "b", "kind": ")", "name": "a dagger", "damage": 2},
                {"id": "blade-c", "letter": "c", "kind": ")", "name": "a spear", "damage": 4},
            ],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
    }


class GenericWeaponStateTests(unittest.TestCase):
    def test_two_weapon_toggle_and_swap_are_stateful_turns(self) -> None:
        task = weapon_task()
        task["actions"] = ["Command.WIELD", 24, "Command.TWOWEAPON", "Command.SWAP", "Command.TWOWEAPON"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        private = python["readout"]["private"]
        self.assertEqual("blade-b", private["wielded"])
        self.assertEqual("blade-a", private["offhand"])
        self.assertFalse(private["two_weapon"])
        self.assertEqual(4, python["readout"]["public"]["blstats_named"]["time"])
        self.assertTrue(any("TwoWeapon(on)" in event for event in python["events"]))
        self.assertTrue(any("WeaponSwap()" in event for event in python["events"]))

    def test_two_weapon_requires_a_primary_and_second_weapon(self) -> None:
        task = weapon_task(seed=202)
        task["level_dump"]["inventory"] = [{
            "id": "only-blade", "letter": "a", "kind": ")", "name": "a blade", "damage": 2,
        }]
        task["actions"] = ["Command.TWOWEAPON", "Command.WIELD", 24, "Command.TWOWEAPON"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(1, python["readout"]["public"]["blstats_named"]["time"])
        self.assertFalse(python["readout"]["private"]["two_weapon"])
        self.assertIn("no second weapon", python["readout"]["public"]["message"])

    def test_two_weapon_mode_adds_a_second_authored_attack(self) -> None:
        task = weapon_task(seed=202)
        task["level_dump"]["monsters"] = [{
            "id": "two-weapon-target",
            "name": "two-weapon target",
            "char": "t",
            "position": {"x": 6, "y": 4},
            "hp": 50,
            "armor_class": 1,
            "level": 1,
            "to_hit": 0,
            "damage_dice": 1,
            "damage_sides": 1,
            "movement": "stationary",
        }]
        task["actions"] = ["Command.WIELD", 24, "Command.TWOWEAPON", "Command.FIGHT", "CompassDirection.E"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        fight_events = [event for event in python["events"] if "Fight(two-weapon target)" in event]
        self.assertGreaterEqual(len(fight_events), 2)
        self.assertLess(python["readout"]["private"]["monsters"][0]["hp"], 50)

    def test_typed_primary_and_offhand_damage_respect_monster_resistance(self) -> None:
        task = weapon_task(seed=204)
        task["level_dump"]["inventory"][0]["damage_type"] = "fire"
        task["level_dump"]["inventory"][1]["damage_type"] = "fire"
        task["level_dump"]["monsters"] = [{
            "id": "fireproof-target",
            "name": "fireproof target",
            "char": "t",
            "position": {"x": 6, "y": 4},
            "hp": 50,
            "armor_class": 1,
            "level": 1,
            "to_hit": 20,
            "damage_dice": 1,
            "damage_sides": 1,
            "resistances": {"fire": 100},
            "movement": "stationary",
        }]
        task["actions"] = ["Command.WIELD", 24, "Command.TWOWEAPON", "Command.FIGHT", "CompassDirection.E"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        self.assertEqual(50, python["readout"]["private"]["monsters"][0]["hp"])

    def test_randomized_weapon_state_tapes_match_across_both_lanes(self) -> None:
        for seed in range(203, 219):
            task = weapon_task(seed=seed)
            task["actions"] = [
                "Command.WIELD", 24,
                "Command.TWOWEAPON", "Command.SWAP",
                "Command.WIELD", 29,
                "Command.TWOWEAPON", "Command.SWAP",
            ]
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"], f"seed {seed}")
            self.assertEqual(python["events"], rust["events"], f"events seed {seed}")


if __name__ == "__main__":
    unittest.main()
