"""Broad deterministic tape parity for fixture-free authored levels."""

from __future__ import annotations

import random
import sys
import unittest
from copy import deepcopy
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust
from shared.task_resolve import (
    PROCEDURAL_POPULATION_TABLE,
    procedural_population_profile,
    resolve_task,
)


DIRECTIONS = (
    "CompassDirection.N",
    "CompassDirection.NE",
    "CompassDirection.E",
    "CompassDirection.SE",
    "CompassDirection.S",
    "CompassDirection.SW",
    "CompassDirection.W",
    "CompassDirection.NW",
)


def randomized_tape(seed: int) -> list[str]:
    rng = random.Random(seed ^ 0x5EED)
    actions: list[str] = []
    for _ in range(14):
        operation = rng.randrange(8)
        direction = rng.choice(DIRECTIONS)
        if operation == 0:
            actions.append("MiscDirection.WAIT")
        elif operation == 1:
            actions.append(rng.choice(DIRECTIONS))
        elif operation == 2:
            actions.append("Command.SEARCH")
        elif operation == 3:
            actions.extend(("Command.FIGHT", direction))
        elif operation == 4:
            actions.extend(("Command.OPEN", direction))
        elif operation == 5:
            actions.extend(("Command.CLOSE", direction))
        elif operation == 6:
            actions.extend(("Command.SEETRAP", direction))
        else:
            actions.extend(("Command.UNTRAP", direction))
    return actions


def rich_randomized_tape(seed: int) -> list[object]:
    """Exercise prompts, item effects, rendering, and actor turns together."""

    rng = random.Random(seed ^ 0xA11CE)
    actions: list[object] = []
    for _ in range(18):
        operation = rng.randrange(16)
        direction = rng.choice(DIRECTIONS)
        if operation == 0:
            actions.append("MiscDirection.WAIT")
        elif operation == 1:
            actions.append(direction)
        elif operation == 2:
            actions.append("Command.SEARCH")
        elif operation == 3:
            actions.extend(("Command.FIGHT", direction))
        elif operation == 4:
            actions.extend(("Command.OPEN", direction))
        elif operation == 5:
            actions.extend(("Command.CLOSE", direction))
        elif operation == 6:
            actions.extend(("Command.SEETRAP", direction))
        elif operation == 7:
            actions.extend(("Command.UNTRAP", direction))
        elif operation == 8:
            actions.append("Command.INVENTORY")
        elif operation == 9:
            actions.extend(("Command.QUAFF", 24))
        elif operation == 10:
            actions.extend(("Command.READ", 24))
        elif operation == 11:
            actions.extend(("Command.EAT", 25))
        elif operation == 12:
            actions.extend(("Command.WIELD", 24))
        elif operation == 13:
            actions.extend(("Command.DROP", 24))
        elif operation == 14:
            actions.extend(("Command.ZAP", 24, direction))
        else:
            actions.extend(("Command.THROW", 24, direction))
    return actions


class RandomizedGenericParityTests(unittest.TestCase):
    def test_source_population_wheel_spawns_and_matches_after_fifty_turns(self) -> None:
        table = PROCEDURAL_POPULATION_TABLE
        self.assertEqual("nle-0.9.0/src/monst.c", table["source"])
        self.assertEqual(36, table["selector_bound"])
        profiles = [procedural_population_profile(selector) for selector in range(36)]
        self.assertEqual(20, len({profile["name"] for profile in profiles}))
        self.assertEqual("giant ant", profiles[0]["name"])
        self.assertEqual("grid bug", profiles[-1]["name"])
        self.assertEqual(115, profiles[-1]["species_id"])
        self.assertTrue(profiles[-1]["no_corpse"])
        task = {
            "task_id": "random-population-spawn",
            "seed": 1234,
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 6},
            "actions": ["MiscDirection.WAIT"] * 50,
        }
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual(python["events"], rust["events"])
        spawned = [monster for monster in python["readout"]["private"]["monsters"] if monster["id"].startswith("procedural-monster-")]
        self.assertEqual(1, len(spawned))
        self.assertEqual("giant rat", spawned[0]["name"])
        self.assertEqual(88, spawned[0]["species_id"])

    def test_every_source_population_selector_survives_an_adjacent_attack_tape(self) -> None:
        terrain = [[" "] * 79 for _ in range(21)]
        for x in range(2, 10):
            terrain[4][x] = "."
        for selector in range(PROCEDURAL_POPULATION_TABLE["selector_bound"]):
            with self.subTest(selector=selector):
                profile = deepcopy(procedural_population_profile(selector))
                profile.update({
                    "id": f"population-profile-{selector}",
                    "position": {"x": 6, "y": 4},
                    "hp": 100,
                    # Exercise every profile's authored attack list in the
                    # first actor pass; movement-point scheduling is covered
                    # separately by the 50-turn procedural spawn tape.
                    "movement": "stationary",
                })
                profile.pop("base_speed", None)
                profile.pop("movement_points", None)
                task = {
                    "task_id": f"population-profile-attack-{selector}",
                    "seed": 4000 + selector,
                    "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 6},
                    "level_dump": {
                        "terrain": ["".join(row) for row in terrain],
                        "hero": {"x": 5, "y": 4},
                        "monsters": [profile],
                        "metadata": {"hp": 20, "hp_max": 20, "ac": 0, "hunger": 900},
                    },
                    "actions": ["MiscDirection.WAIT"],
                }
                python = run_python(task)
                rust = run_rust(task)
                self.assertEqual(python["readout"], rust["readout"])
                self.assertEqual(python["events"], rust["events"])

    def test_fixture_free_tapes_match_across_both_lanes(self) -> None:
        for seed in (2, 7, 19, 31, 47, 89, 144, 233):
            with self.subTest(seed=seed):
                task = {
                    "task_id": f"random-generated-{seed}",
                    "seed": seed,
                    "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
                    "actions": randomized_tape(seed),
                }
                python = run_python(task)
                rust = run_rust(task)
                self.assertEqual(python["readout"], rust["readout"])
                self.assertEqual(python["events"], rust["events"])

    def test_richer_fixture_free_tapes_match_across_many_arbitrary_seeds(self) -> None:
        for seed in range(24):
            with self.subTest(seed=seed):
                task = {
                    "task_id": f"rich-random-generated-{seed}",
                    "seed": seed * 7919 - 23,
                    "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
                    "actions": rich_randomized_tape(seed),
                }
                python = run_python(task)
                rust = run_rust(task)
                self.assertEqual(python["readout"], rust["readout"])
                self.assertEqual(python["events"], rust["events"])

    def test_randomized_authored_nutrition_lifecycles_match_across_both_lanes(self) -> None:
        for seed in range(12):
            with self.subTest(seed=seed):
                base = resolve_task({"task_id": f"nutrition-base-{seed}", "seed": seed})
                level = deepcopy(base["level_dump"])
                actor = level["monsters"][seed % len(level["monsters"])]
                actor.update({
                    "id": f"nutrition-actor-{seed}",
                    "name": f"nutrition actor {seed}",
                    "movement": "stationary",
                    "pet": True,
                    "eat": True,
                    "hunger": 1 + (seed % 4),
                    "hunger_max": 800 + seed,
                    "hunger_drain": 1 + (seed % 3),
                    "eat_threshold": 100 + seed,
                })
                actor_position = deepcopy(actor["position"])
                level["objects"] = [{
                    "id": f"nutrition-ration-{seed}",
                    "kind": "%",
                    "name": f"a ration {seed}",
                    "position": actor_position,
                    "nutrition": 120 + seed,
                }]
                task = {
                    "task_id": f"random-authored-nutrition-{seed}",
                    "seed": seed * 104729 + 17,
                    "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
                    "level_dump": level,
                    "actions": ["MiscDirection.WAIT"] * (1 + seed % 4),
                }
                python = run_python(task)
                rust = run_rust(task)
                self.assertEqual(python["readout"], rust["readout"])
                self.assertEqual(python["events"], rust["events"])

    def test_randomized_initiative_order_tapes_match_across_both_lanes(self) -> None:
        for seed in range(10):
            with self.subTest(seed=seed):
                base = resolve_task({"task_id": f"initiative-base-{seed}", "seed": seed + 900})
                level = deepcopy(base["level_dump"])
                for index, monster in enumerate(level["monsters"]):
                    # The generated bootstrap now opts these actors into the
                    # persistent movement-point schedule. This tape targets
                    # the legacy period scheduler, so remove that explicit
                    # schedule before adding legacy speed.
                    monster.pop("base_speed", None)
                    monster.pop("movement_points", None)
                    monster["initiative"] = ((seed * 7 + index * 11) % 19) - 9
                    monster["movement"] = "wander" if index % 2 == 0 else "chase"
                    monster["speed"] = 1 + ((seed + index) % 2)
                task = {
                    "task_id": f"random-initiative-{seed}",
                    "seed": seed * 65537 + 101,
                    "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
                    "level_dump": level,
                    "actions": ["MiscDirection.WAIT"] * (3 + seed % 4),
                }
                python = run_python(task)
                rust = run_rust(task)
                self.assertEqual(python["readout"], rust["readout"])
                self.assertEqual(python["events"], rust["events"])

    def test_randomized_authored_boulder_tapes_match_across_both_lanes(self) -> None:
        for seed in range(16):
            with self.subTest(seed=seed):
                rng = random.Random(seed ^ 0xB0)
                terrain = [[" "] * 79 for _ in range(21)]
                for x in range(2, 24):
                    terrain[5][x] = "."
                first = 6 + (seed % 3)
                second = 13 + (seed % 4)
                level = {
                    "terrain": ["".join(row) for row in terrain],
                    "hero": {"x": 4, "y": 5},
                    "objects": [
                        {"id": f"boulder-a-{seed}", "kind": "0", "name": "a boulder", "position": {"x": first, "y": 5}},
                        {"id": f"boulder-b-{seed}", "kind": "0", "name": "a boulder", "position": {"x": second, "y": 5}},
                    ],
                    "metadata": {"hp": 20, "hp_max": 20, "ac": 10, "hunger": 900},
                }
                actions: list[str] = []
                for _ in range(12):
                    if rng.randrange(3) == 0:
                        actions.extend(("Command.KICK", rng.choice(DIRECTIONS)))
                    elif rng.randrange(2) == 0:
                        actions.append(rng.choice(DIRECTIONS))
                    else:
                        actions.append("MiscDirection.WAIT")
                task = {
                    "task_id": f"random-authored-boulder-{seed}",
                    "seed": seed * 65537 + 313,
                    "level_dump": level,
                    "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 8},
                    "actions": actions,
                }
                python = run_python(task)
                rust = run_rust(task)
                self.assertEqual(python["readout"], rust["readout"])
                self.assertEqual(python["events"], rust["events"])


if __name__ == "__main__":
    unittest.main()
