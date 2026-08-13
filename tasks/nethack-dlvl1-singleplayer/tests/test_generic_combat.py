"""Cross-lane coverage for the explicit authored-level combat contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def combat_task(*, seed: int, armor_class: int, hp: int) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 10):
        terrain[4][x] = "."
    return {
        "task_id": "generic-authored-combat",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 4},
            "monsters": [
                {
                    "id": "training-dummy",
                    "name": "training dummy",
                    "char": "d",
                    "position": {"x": 6, "y": 4},
                    "hp": hp,
                    "attack": 1,
                    "experience": 3,
                    "armor_class": armor_class,
                    "level": 1,
                    "to_hit": 0,
                    "damage_dice": 1,
                    "damage_sides": 1,
                }
            ],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
        "actions": ["Command.FIGHT", "CompassDirection.E"],
    }


def gas_spore_task() -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 10):
        terrain[4][x] = "."
    return {
        "task_id": "generic-gas-spore-death",
        "seed": 41,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 4},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 4},
            "monsters": [{
                "id": "gas-spore",
                "name": "gas spore",
                "char": "e",
                "position": {"x": 6, "y": 4},
                "hp": 1,
                "experience": 3,
                "armor_class": -100,
                "level": 1,
                "to_hit": 0,
                "damage_dice": 1,
                "damage_sides": 1,
                "death_effect": "explode",
                "attacks": [{
                    "id": "death-boom",
                    "name": "death boom",
                    "attack_effect": "explode_on_death",
                    "damage_type": "physical",
                    "damage_dice": 1,
                    "damage_sides": 1,
                }],
            }],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
        "actions": ["Command.FIGHT", "CompassDirection.E"],
    }


class GenericCombatTests(unittest.TestCase):
    def test_gas_spore_death_explosion_matches_in_both_lanes(self) -> None:
        python = run_python(gas_spore_task())
        rust = run_rust(gas_spore_task())

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        self.assertEqual([], python["readout"]["private"]["monsters"])
        self.assertLess(python["readout"]["private"]["hp"], 20)
        self.assertTrue(any("MonsterExplode(gas spore)" in event for event in python["events"]))

    def test_generic_fire_requires_and_honors_the_quiver(self) -> None:
        terrain = [[" "] * 79 for _ in range(21)]
        for x in range(2, 11):
            terrain[4][x] = "."
        task = {
            "task_id": "generic-fire-quiver",
            "seed": 23,
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 8},
            "level_dump": {
                "terrain": ["".join(row) for row in terrain],
                "hero": {"x": 3, "y": 4},
                "inventory": [
                    {"id": "dart", "letter": "a", "kind": ")", "name": "a dart", "damage": 2, "quantity": 2},
                    {"id": "stone", "letter": "b", "kind": ")", "name": "a stone", "damage": 1, "quantity": 2},
                ],
                "monsters": [{
                    "id": "fire-target",
                    "name": "fire target",
                    "char": "t",
                    "position": {"x": 8, "y": 4},
                    "hp": 1,
                    "armor_class": 1,
                    "level": 1,
                    "to_hit": 0,
                    "damage_dice": 1,
                    "damage_sides": 1,
                }],
                "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
            },
            "actions": ["Command.FIRE", "Command.QUIVER", 24, "Command.FIRE", 6, "CompassDirection.E", "Command.FIRE", 24, "CompassDirection.E"],
        }
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        private = python["readout"]["private"]
        self.assertEqual("dart", private["quiver"])
        self.assertEqual(1, private["inventory"][0]["quantity"])
        self.assertEqual(2, private["inventory"][1]["quantity"])
        self.assertEqual([], private["monsters"])
        self.assertTrue(any("You have no ammunition readied." in event for event in python["events"]))
        self.assertTrue(any("That is not the object readied in your quiver." in event for event in python["events"]))

    def test_authored_monster_attack_effect_applies_status_in_both_lanes(self) -> None:
        task = combat_task(seed=23, armor_class=1, hp=4)
        task["level_dump"]["hero"] = {"x": 5, "y": 4}
        task["level_dump"]["metadata"]["ac"] = 1
        task["level_dump"]["monsters"][0].update({
            "position": {"x": 6, "y": 4},
            "combat_model": "d20",
            "to_hit": 20,
            "damage_dice": 1,
            "damage_sides": 1,
            "attack_effect": "poison",
            "attack_effect_duration": 4,
        })
        task["actions"] = ["MiscDirection.WAIT"]

        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(19, python["readout"]["private"]["hp"])
        self.assertEqual(4, python["readout"]["private"]["status_effects"]["poisoned"])
        self.assertTrue(any("MonsterEffect(training dummy,poisoned)" in event for event in python["events"]))

    def test_authored_multiattack_turn_matches_for_hero_and_actor_targets(self) -> None:
        task = combat_task(seed=31, armor_class=1, hp=20)
        task["level_dump"]["metadata"]["ac"] = 1
        task["level_dump"]["monsters"][0].update({
            "combat_model": "d20",
            "to_hit": 20,
            "damage_dice": 1,
            "damage_sides": 1,
            "attacks": [
                {"id": "bite", "name": "bite", "combat_model": "d20", "to_hit": 20, "damage_sides": 1},
                {"id": "sting", "name": "sting", "combat_model": "d20", "to_hit": 20, "damage_sides": 1, "effect": "poison", "effect_duration": 4},
            ],
        })
        task["actions"] = ["MiscDirection.WAIT"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        self.assertEqual(18, python["readout"]["private"]["hp"])
        self.assertEqual(4, python["readout"]["private"]["status_effects"]["poisoned"])
        self.assertEqual(2, sum("MonsterAttack(training dummy)" in event for event in python["events"]))

        actor_task = dict(task)
        actor_task["task_id"] = "generic-authored-multiattack-actor"
        actor_task["level_dump"] = dict(task["level_dump"])
        actor_task["level_dump"]["hero"] = {"x": 2, "y": 4}
        actor_task["level_dump"]["monsters"] = [
            {
                "id": "authored-pet",
                "name": "authored pet",
                "char": "d",
                "position": {"x": 6, "y": 4},
                "hp": 10,
                "pet": True,
                "attack_monsters": True,
                "movement": "stationary",
                "attacks": task["level_dump"]["monsters"][0]["attacks"],
            },
            {
                "id": "hostile-target",
                "name": "hostile target",
                "char": "h",
                "position": {"x": 7, "y": 4},
                "hp": 20,
                "peaceful": False,
                "movement": "stationary",
            },
        ]
        actor_python = run_python(actor_task)
        actor_rust = run_rust(actor_task)
        self.assertEqual(actor_python["readout"], actor_rust["readout"])
        self.assertEqual(actor_python["events"], actor_rust["events"])
        target = next(monster for monster in actor_python["readout"]["private"]["monsters"] if monster["id"] == "hostile-target")
        self.assertEqual(17, target["hp"])
        self.assertEqual(3, target["status_effects"]["poisoned"])
        self.assertEqual(2, sum("MonsterFight(authored pet,hostile target)" in event for event in actor_python["events"]))

    def test_authored_elemental_attack_resistance_matches_for_hero_and_actor_targets(self) -> None:
        hero_task = combat_task(seed=32, armor_class=1, hp=20)
        hero_task["level_dump"]["metadata"]["ac"] = 1
        hero_task["level_dump"]["metadata"]["resistances"] = {"fire": 100}
        hero_task["level_dump"]["monsters"][0].update({
            "combat_model": "d20",
            "to_hit": 20,
            "attacks": [{
                "id": "fire-bite",
                "name": "fire bite",
                "combat_model": "d20",
                "to_hit": 20,
                "damage_sides": 1,
                "damage_type": "fire",
            }],
        })
        hero_task["actions"] = ["MiscDirection.WAIT"]
        hero_python = run_python(hero_task)
        hero_rust = run_rust(hero_task)
        self.assertEqual(hero_python["readout"], hero_rust["readout"])
        self.assertEqual(20, hero_python["readout"]["private"]["hp"])

        actor_task = dict(hero_task)
        actor_task["task_id"] = "generic-authored-attack-resistance-actor"
        actor_task["level_dump"] = dict(hero_task["level_dump"])
        actor_task["level_dump"]["hero"] = {"x": 2, "y": 4}
        actor_task["level_dump"]["metadata"] = dict(hero_task["level_dump"]["metadata"])
        actor_task["level_dump"]["metadata"].pop("resistances")
        actor_task["level_dump"]["monsters"] = [
            {
                "id": "authored-pet",
                "name": "authored pet",
                "char": "d",
                "position": {"x": 6, "y": 4},
                "hp": 10,
                "pet": True,
                "attack_monsters": True,
                "movement": "stationary",
                "attacks": hero_task["level_dump"]["monsters"][0]["attacks"],
            },
            {
                "id": "fire-resistant-target",
                "name": "fire-resistant target",
                "char": "h",
                "position": {"x": 7, "y": 4},
                "hp": 20,
                "peaceful": False,
                "movement": "stationary",
                "resistances": {"fire": 100},
            },
        ]
        actor_python = run_python(actor_task)
        actor_rust = run_rust(actor_task)
        self.assertEqual(actor_python["readout"], actor_rust["readout"])
        target = next(monster for monster in actor_python["readout"]["private"]["monsters"] if monster["id"] == "fire-resistant-target")
        self.assertEqual(20, target["hp"])

    def test_typed_poison_attack_applies_status_without_duplicate_effect_field(self) -> None:
        task = combat_task(seed=33, armor_class=1, hp=20)
        task["level_dump"]["metadata"]["ac"] = 1
        task["level_dump"]["monsters"][0].update({
            "combat_model": "d20",
            "to_hit": 20,
            "attacks": [{
                "id": "poison-bite",
                "name": "poison bite",
                "combat_model": "d20",
                "to_hit": 20,
                "damage_sides": 1,
                "damage_type": "poison",
            }],
        })
        task["actions"] = ["MiscDirection.WAIT"]
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        self.assertEqual(19, python["readout"]["private"]["hp"])
        self.assertEqual(5, python["readout"]["private"]["status_effects"]["poisoned"])
        self.assertTrue(any("MonsterEffect(poison bite,poisoned)" in event for event in python["events"]))

    def test_floating_eye_paralysis_blocks_the_next_normal_action(self) -> None:
        task = combat_task(seed=34, armor_class=1, hp=20)
        task["level_dump"]["metadata"]["ac"] = 1
        task["level_dump"]["monsters"][0].update({
            "name": "floating eye",
            "combat_model": "d20",
            "to_hit": 20,
            "attacks": [{
                "id": "gaze",
                "name": "gaze",
                "combat_model": "d20",
                "to_hit": 20,
                "damage_sides": 1,
                "damage_type": "physical",
                "attack_effect": "paralyzed",
                "attack_effect_duration": 2,
            }],
        })
        task["actions"] = ["MiscDirection.WAIT", "CompassDirection.W"]
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        self.assertEqual(
            {"x": 5, "y": 4},
            {key: python["readout"]["private"]["hero"][key] for key in ("x", "y")},
        )
        self.assertEqual(2, python["readout"]["private"]["status_effects"]["paralyzed"])
        self.assertTrue(any("MonsterEffect(gaze,paralyzed)" in event for event in python["events"]))
        self.assertTrue(any("You are paralyzed." in event for event in python["events"]))

    def test_randomized_authored_typed_multiattacks_match_across_both_lanes(self) -> None:
        for seed in range(40, 50):
            with self.subTest(seed=seed):
                resistance = (seed * 37) % 101
                task = combat_task(seed=seed, armor_class=1, hp=60)
                task["level_dump"]["metadata"]["ac"] = 1
                task["level_dump"]["metadata"]["resistances"] = {"fire": resistance}
                task["level_dump"]["monsters"][0].update({
                    "combat_model": "d20",
                    "to_hit": 20,
                    "attacks": [
                        {
                            "id": "physical-bite",
                            "name": "physical bite",
                            "combat_model": "d20",
                            "to_hit": 20,
                            "damage_sides": 4 + seed % 3,
                        },
                        {
                            "id": "fire-sting",
                            "name": "fire sting",
                            "combat_model": "d20",
                            "to_hit": 20,
                            "damage_sides": 5 + seed % 4,
                            "damage_type": "fire",
                        },
                    ],
                })
                task["actions"] = ["MiscDirection.WAIT"]
                python = run_python(task)
                rust = run_rust(task)
                self.assertEqual(python["readout"], rust["readout"])
                self.assertEqual(python["events"], rust["events"])

                actor_task = dict(task)
                actor_task["task_id"] = f"generic-authored-typed-multiattack-actor-{seed}"
                actor_task["level_dump"] = dict(task["level_dump"])
                actor_task["level_dump"]["hero"] = {"x": 2, "y": 4}
                actor_task["level_dump"]["metadata"] = dict(task["level_dump"]["metadata"])
                actor_task["level_dump"]["metadata"].pop("resistances")
                actor_task["level_dump"]["monsters"] = [
                    {
                        "id": "authored-pet",
                        "name": "authored pet",
                        "char": "d",
                        "position": {"x": 6, "y": 4},
                        "hp": 20,
                        "pet": True,
                        "attack_monsters": True,
                        "movement": "stationary",
                        "attacks": task["level_dump"]["monsters"][0]["attacks"],
                    },
                    {
                        "id": "resistant-target",
                        "name": "resistant target",
                        "char": "h",
                        "position": {"x": 7, "y": 4},
                        "hp": 60,
                        "peaceful": False,
                        "movement": "stationary",
                        "resistances": {"fire": resistance},
                    },
                ]
                actor_python = run_python(actor_task)
                actor_rust = run_rust(actor_task)
                self.assertEqual(actor_python["readout"], actor_rust["readout"])
                self.assertEqual(actor_python["events"], actor_rust["events"])

    def test_player_death_drops_authored_inventory_and_clears_equipment(self) -> None:
        task = combat_task(seed=17, armor_class=1, hp=1)
        task["level_dump"]["hero"] = {"x": 5, "y": 4}
        task["level_dump"]["inventory"] = [
            {"id": "death-gem", "letter": "a", "kind": "*", "name": "a death gem", "quantity": 2},
            {"id": "death-dagger", "letter": "b", "kind": ")", "name": "a death dagger", "damage": 2},
        ]
        task["level_dump"]["metadata"]["hp"] = 1
        task["level_dump"]["metadata"]["ac"] = -100
        task["level_dump"]["monsters"][0]["position"] = {"x": 6, "y": 4}
        task["level_dump"]["monsters"][0]["attack"] = 4
        task["actions"] = ["MiscDirection.WAIT"]

        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        private = python["readout"]["private"]
        self.assertTrue(python["readout"]["terminated"])
        self.assertEqual("death", private["terminal_reason"])
        self.assertEqual([], private["inventory"])
        self.assertEqual("", private["wielded"])
        self.assertEqual("", private["worn"])
        self.assertEqual([], private["accessories"])
        self.assertEqual("", private["quiver"])
        self.assertEqual({"death-gem", "death-dagger"}, {item["id"] for item in private["floor_items"]})
        self.assertTrue(any("PlayerDrop(a death gem)" in event for event in python["events"]))
        self.assertTrue(any("PlayerDrop(a death dagger)" in event for event in python["events"]))

    def test_explicit_d20_miss_preserves_hp_and_matches_both_lanes(self) -> None:
        for seed in (0, 1, 23, 20260731):
            with self.subTest(seed=seed):
                task = combat_task(seed=seed, armor_class=100, hp=5)
                python = run_python(task)
                rust = run_rust(task)
                self.assertEqual(python["readout"], rust["readout"])
                monster = python["readout"]["private"]["monsters"][0]
                self.assertEqual(5, monster["hp"])
                self.assertTrue(any("You miss the training dummy." in event for event in python["events"]))

    def test_explicit_d20_hit_kills_and_matches_both_lanes(self) -> None:
        task = combat_task(seed=23, armor_class=1, hp=1)
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual([], python["readout"]["private"]["monsters"])
        self.assertEqual(3, python["readout"]["private"]["experience"])
        self.assertTrue(any("You kill the training dummy!" in event for event in python["events"]))

    def test_authored_experience_crosses_a_level_and_grows_resources(self) -> None:
        task = combat_task(seed=23, armor_class=1, hp=1)
        task["level_dump"]["monsters"][0]["experience"] = 10
        task["level_dump"]["metadata"].update({
            "experience": 0,
            "experience_level": 1,
            "hp": 10,
            "hp_max": 10,
            "energy": 2,
            "energy_max": 2,
            "constitution": 10,
        })
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        private = python["readout"]["private"]
        self.assertEqual(2, private["experience_level"])
        self.assertEqual(10, private["experience"])
        self.assertEqual(13, private["hp_max"])
        self.assertEqual(13, private["hp"])
        self.assertEqual(3, python["readout"]["public"]["blstats_named"]["energy_max"])
        self.assertTrue(any("LevelUp(1->2)" in event for event in python["events"]))

    def test_explicit_d20_projectile_uses_defense_and_consumes_throwable(self) -> None:
        task = combat_task(seed=23, armor_class=1, hp=1)
        task["level_dump"]["inventory"] = [
            {"id": "dart", "letter": "a", "kind": ")", "name": "a dart", "damage": 2, "quantity": 2}
        ]
        task["actions"] = ["Command.THROW", 24, "CompassDirection.E"]
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual([], python["readout"]["private"]["monsters"])
        self.assertEqual(1, python["readout"]["private"]["inventory"][0]["quantity"])
        self.assertEqual(3, python["readout"]["private"]["experience"])
        self.assertTrue(any("The throw kills the training dummy!" in event for event in python["events"]))

    def test_generic_projectiles_trace_to_first_actor_and_stop_at_walls(self) -> None:
        terrain = [[" "] * 79 for _ in range(21)]
        for x in range(2, 11):
            terrain[4][x] = "."
        task = {
            "task_id": "generic-projectile-trace",
            "seed": 23,
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 8},
            "level_dump": {
                "terrain": ["".join(row) for row in terrain],
                "hero": {"x": 3, "y": 4},
                "inventory": [{"id": "dart", "letter": "a", "kind": ")", "name": "a dart", "damage": 2}],
                "monsters": [{
                    "id": "distant-dummy",
                    "name": "distant dummy",
                    "char": "d",
                    "position": {"x": 8, "y": 4},
                    "hp": 1,
                    "armor_class": 1,
                    "level": 1,
                    "to_hit": 0,
                    "damage_dice": 1,
                    "damage_sides": 1,
                }],
                "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
            },
            "actions": ["Command.THROW", 24, "CompassDirection.E"],
        }
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual([], python["readout"]["private"]["monsters"])

        blocked = {**task, "task_id": "generic-projectile-wall"}
        blocked_level = {**task["level_dump"]}
        blocked_terrain = [list(row) for row in terrain]
        blocked_terrain[4][5] = "|"
        blocked_level["terrain"] = ["".join(row) for row in blocked_terrain]
        blocked["level_dump"] = blocked_level
        python = run_python(blocked)
        rust = run_rust(blocked)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(1, python["readout"]["private"]["monsters"][0]["hp"])
        self.assertTrue(any("flies harmlessly" in event for event in python["events"]))

    def test_authored_ranged_monster_requires_clear_line_of_sight(self) -> None:
        terrain = [[" "] * 79 for _ in range(21)]
        for x in range(2, 11):
            terrain[4][x] = "."
        task = {
            "task_id": "generic-ranged-monster",
            "seed": 41,
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": {
                "terrain": ["".join(row) for row in terrain],
                "hero": {"x": 3, "y": 4},
                "monsters": [{
                    "id": "ranged-jackal",
                    "name": "ranged jackal",
                    "char": "j",
                    "position": {"x": 8, "y": 4},
                    "hp": 5,
                    "attack_range": 5,
                    "armor_class": 0,
                    "level": 1,
                    "to_hit": 0,
                    "damage_dice": 1,
                    "damage_sides": 1,
                }],
                "metadata": {"hp": 20, "hp_max": 20, "ac": -100, "hunger": 900},
            },
            "actions": ["MiscDirection.WAIT"],
        }
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(19, python["readout"]["private"]["hp"])
        self.assertEqual({"x": 8, "y": 4}, python["readout"]["private"]["monsters"][0]["position"])
        self.assertTrue(any("MonsterAttack(ranged jackal)" in event for event in python["events"]))

        blocked = {**task, "task_id": "generic-ranged-monster-blocked"}
        blocked_level = dict(task["level_dump"])
        blocked_terrain = [list(row) for row in terrain]
        blocked_terrain[4][5] = "|"
        blocked_level["terrain"] = ["".join(row) for row in blocked_terrain]
        blocked["level_dump"] = blocked_level
        python = run_python(blocked)
        rust = run_rust(blocked)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(20, python["readout"]["private"]["hp"])
        self.assertFalse(any("MonsterAttack(ranged jackal)" in event for event in python["events"]))

    def test_explicit_actor_combat_resolves_pet_and_hostile_collisions(self) -> None:
        terrain = [[" "] * 79 for _ in range(21)]
        for x in range(2, 9):
            terrain[4][x] = "."
        task = {
            "task_id": "generic-actor-combat",
            "seed": 61,
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": {
                "terrain": ["".join(row) for row in terrain],
                "hero": {"x": 3, "y": 4},
                "monsters": [
                    {
                        "id": "authored-pet",
                        "name": "authored pet",
                        "char": "d",
                        "position": {"x": 4, "y": 4},
                        "hp": 8,
                        "pet": True,
                        "movement": "stationary",
                        "attack_monsters": True,
                        "combat_model": "d20",
                        "armor_class": 1,
                        "to_hit": 20,
                        "damage_dice": 1,
                        "damage_sides": 1,
                    },
                    {
                        "id": "authored-hostile",
                        "name": "authored hostile",
                        "char": "h",
                        "position": {"x": 5, "y": 4},
                        "hp": 8,
                        "movement": "stationary",
                        "attack_monsters": True,
                        "combat_model": "d20",
                        "armor_class": 1,
                        "to_hit": 20,
                        "damage_dice": 1,
                        "damage_sides": 1,
                    },
                ],
                "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
            },
            "actions": ["MiscDirection.WAIT"],
        }
        python = run_python(task)
        rust = run_rust(task)

        self.assertEqual(python["readout"], rust["readout"])
        monsters = python["readout"]["private"]["monsters"]
        self.assertEqual(7, monsters[0]["hp"])
        self.assertEqual(7, monsters[1]["hp"])
        self.assertTrue(any("MonsterFight(authored pet,authored hostile)" in event for event in python["events"]))
        self.assertTrue(any("MonsterFight(authored hostile,authored pet)" in event for event in python["events"]))


if __name__ == "__main__":
    unittest.main()
