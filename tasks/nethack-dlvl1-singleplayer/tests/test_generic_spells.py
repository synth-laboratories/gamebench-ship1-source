"""Parity coverage for authored generic spell selection and casting."""

from __future__ import annotations

import unittest

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def spell_task(seed: int = 71) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 15):
        terrain[4][x] = "."
    return {
        "task_id": f"generic-spells-{seed}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 6},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 4, "y": 4},
            "monsters": [{
                "id": "spell-target",
                "name": "spell target",
                "char": "s",
                "position": {"x": 9, "y": 4},
                "hp": 5,
                "experience": 12,
                "movement": "stationary",
            }],
            "metadata": {
                "hp": 8,
                "hp_max": 20,
                "energy": 8,
                "energy_max": 10,
                "hunger": 900,
                "spells": [
                    {
                        "id": "magic-missile",
                        "letter": "a",
                        "name": "magic missile",
                        "effect": "damage",
                        "damage": 5,
                        "cost": 3,
                        "target": "direction",
                    },
                    {
                        "id": "healing",
                        "letter": "b",
                        "name": "healing",
                        "effect": "healing",
                        "cost": 2,
                        "target": "self",
                    },
                ],
            },
        },
    }


class GenericSpellTests(unittest.TestCase):
    def test_spell_selection_directional_damage_and_self_effect_match(self) -> None:
        task = spell_task()
        task["actions"] = ["Command.CAST", 24, "CompassDirection.E", "Command.CAST", 6]
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        public = python["readout"]["public"]
        private = python["readout"]["private"]
        self.assertTrue(any("ModeEnter(spell_letter)" in event for event in python["events"]))
        self.assertTrue(any("Cast which spell? [a b or ?*]" in event for event in python["events"]))
        self.assertEqual(23, private["hp"])
        self.assertEqual(9, public["blstats_named"]["energy"])
        self.assertEqual([], private["monsters"])
        self.assertEqual(12, private["experience"])
        self.assertTrue(any("Cast(magic missile)" in event for event in python["events"]))
        self.assertTrue(any("Kill(spell target)" in event for event in python["events"]))
        self.assertEqual(2, public["blstats_named"]["time"])

    def test_spell_energy_gate_and_no_spell_command_are_zero_turn(self) -> None:
        task = spell_task(seed=72)
        task["level_dump"]["metadata"]["energy"] = 0
        task["actions"] = ["Command.CAST", 24]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(0, python["readout"]["public"]["blstats_named"]["time"])
        self.assertIn("enough energy", python["readout"]["public"]["message"])

        no_spells = spell_task(seed=73)
        no_spells["level_dump"]["metadata"].pop("spells")
        no_spells["actions"] = ["Command.CAST"]
        python = run_python(no_spells)
        rust = run_rust(no_spells)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual("You don't know any spells.", python["readout"]["public"]["message"])
        self.assertEqual(0, python["readout"]["public"]["blstats_named"]["time"])

    def test_authored_elemental_resistance_reduces_directional_spell_damage(self) -> None:
        task = spell_task(seed=74)
        task["level_dump"]["monsters"][0].update({
            "hp": 10,
            "combat_model": "d20",
            "armor_class": 1,
            "to_hit": 0,
            "damage_dice": 1,
            "damage_sides": 1,
            "resistances": {"fire": 100},
        })
        task["level_dump"]["metadata"]["spells"][0]["damage_type"] = "fire"
        task["actions"] = ["Command.CAST", 24, "CompassDirection.E"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(10, python["readout"]["private"]["monsters"][0]["hp"])
        self.assertTrue(any("Cast(magic missile)" in event for event in python["events"]))

    def test_authored_elemental_resistance_reduces_typed_projectile_damage(self) -> None:
        task = spell_task(seed=75)
        task["level_dump"]["inventory"] = [{
            "id": "fire-wand",
            "letter": "a",
            "kind": "/",
            "name": "a fire wand",
            "damage": 5,
            "damage_type": "fire",
        }]
        task["level_dump"]["monsters"][0].update({
            "hp": 10,
            "combat_model": "d20",
            "armor_class": 1,
            "to_hit": 0,
            "damage_dice": 1,
            "damage_sides": 1,
            "resistances": {"fire": 100},
        })
        task["actions"] = ["Command.ZAP", 24, "CompassDirection.E"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(10, python["readout"]["private"]["monsters"][0]["hp"])
        self.assertTrue(any("Projectile(spell target)" in event for event in python["events"]))

    def test_typed_projectile_effect_applies_to_a_surviving_monster(self) -> None:
        task = spell_task(seed=76)
        task["level_dump"]["inventory"] = [{
            "id": "poison-wand",
            "letter": "a",
            "kind": "/",
            "name": "a poison wand",
            "damage": 1,
            "effect": "poison",
        }]
        task["level_dump"]["monsters"][0].update({
            "hp": 20,
            "combat_model": "d20",
            "armor_class": 1,
            "to_hit": 0,
            "damage_dice": 1,
            "damage_sides": 1,
            "movement": "stationary",
        })
        task["actions"] = ["Command.ZAP", 24, "CompassDirection.E"]
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        self.assertEqual(4, python["readout"]["private"]["monsters"][0]["status_effects"]["poisoned"])
        self.assertTrue(any("ProjectileEffect(a poison wand,spell target,poisoned)" in event for event in python["events"]))

    def test_randomized_authored_spell_tapes_match_across_both_lanes(self) -> None:
        for seed in range(80, 96):
            task = spell_task(seed)
            task["actions"] = [
                "Command.CAST", 24, "CompassDirection.E",
                "Command.CAST", 6,
                "MiscDirection.WAIT",
                "Command.CAST", 24, "CompassDirection.W",
            ]
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"], f"seed {seed}")


if __name__ == "__main__":
    unittest.main()
