"""Parity coverage for explicit generic terrain interactions."""

from __future__ import annotations

import unittest

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust


def terrain_task(seed: int = 101, *, effect: str = "healing", explicit: bool = True) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(2, 14):
        terrain[4][x] = "."
    terrain[4][5] = "{"
    metadata: dict[str, object] = {
        "hp": 5,
        "hp_max": 12,
        "energy": 2,
        "energy_max": 8,
        "hunger": 900,
    }
    if explicit:
        metadata["terrain_interactions"] = [{
            "id": "authored-fountain",
            "position": {"x": 5, "y": 4},
            "command": "SIT",
            "effect": effect,
            "amount": 4,
            "duration": 3,
            "message": "You use the authored terrain.",
        }]
    return {
        "task_id": f"generic-terrain-{seed}-{effect}-{explicit}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 4},
            "metadata": metadata,
            "monsters": [{
                "id": "stationary-watcher",
                "name": "stationary watcher",
                "char": "w",
                "position": {"x": 10, "y": 4},
                "hp": 4,
                "peaceful": True,
                "movement": "stationary",
            }],
        },
    }


class GenericTerrainInteractionTests(unittest.TestCase):
    def test_authored_sit_applies_effect_message_and_turn_in_both_lanes(self) -> None:
        task = terrain_task()
        task["actions"] = ["Command.SIT"]
        python = run_python(task)
        rust = run_rust(task)
        self.assertEqual(python["readout"], rust["readout"])
        self.assertEqual("You use the authored terrain.", python["readout"]["public"]["message"])
        self.assertEqual(9, python["readout"]["private"]["hp"])
        self.assertEqual(1, python["readout"]["public"]["blstats_named"]["time"])
        self.assertTrue(any("TerrainInteract(SIT,authored-fountain)" in event for event in python["events"]))

    def test_standard_terrain_symbols_have_deterministic_sit_fallbacks(self) -> None:
        for tile, expected in (("{", "You sit beside the fountain."), ("}", "You sit beside the sink."), ("_", "You sit on the altar."), ("\\", "You sit on the throne."), (".", "You sit down.")):
            task = terrain_task(seed=102, explicit=False)
            row = list(task["level_dump"]["terrain"][4])
            row[5] = tile
            task["level_dump"]["terrain"][4] = "".join(row)
            task["task_id"] = f"generic-terrain-fallback-{tile}"
            task["actions"] = ["Command.SIT"]
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"])
            self.assertEqual(expected, python["readout"]["public"]["message"])
            self.assertEqual(1, python["readout"]["public"]["blstats_named"]["time"])

    def test_randomized_terrain_effect_tapes_match_across_both_lanes(self) -> None:
        effects = ("healing", "energy", "poison", "speed", "invisibility", "confusion", "blind", "mapping")
        for offset, seed in enumerate(range(110, 126)):
            task = terrain_task(seed=seed, effect=effects[offset % len(effects)])
            task["actions"] = ["Command.SIT", "MiscDirection.WAIT", "Command.SIT"]
            python = run_python(task)
            rust = run_rust(task)
            self.assertEqual(python["readout"], rust["readout"], f"seed {seed}")
            self.assertEqual(python["events"], rust["events"], f"events seed {seed}")


if __name__ == "__main__":
    unittest.main()
