"""Parity coverage for explicit actor-to-actor hunt movement."""

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


def hunt_task(*, seed: int, waits: int = 5, speed: int = 1, wall_x: int = 7) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for y in range(3, 8):
        for x in range(2, 15):
            terrain[y][x] = "."
    terrain[5][wall_x] = "|"
    return {
        "task_id": f"generic-actor-hunt-{seed}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 8},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 3, "y": 5},
            "monsters": [
                {
                    "id": "hunting-pet",
                    "name": "hunting pet",
                    "char": "d",
                    "position": {"x": 5, "y": 5},
                    "hp": 8,
                    "attack": 2,
                    "pet": True,
                    "attack_monsters": True,
                    "movement": "hunt",
                    "speed": speed,
                    "vision": 20,
                },
                {
                    "id": "hunted-target",
                    "name": "hunted target",
                    "char": "g",
                    "position": {"x": 10, "y": 5},
                    "hp": 2,
                    "attack": 0,
                    "movement": "stationary",
                },
            ],
            "metadata": {"hp": 20, "hp_max": 20, "ac": 100, "hunger": 900},
        },
        "actions": ["MiscDirection.WAIT"] * waits,
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


class GenericActorHuntingTests(unittest.TestCase):
    def test_pet_routes_around_wall_and_attacks_the_hunted_actor(self) -> None:
        result = assert_lanes_match(self, hunt_task(seed=501, waits=6))
        private = result["readout"]["private"]
        self.assertEqual(1, len(private["monsters"]))
        hunter = private["monsters"][0]
        self.assertEqual("hunting-pet", hunter["id"])
        self.assertNotEqual({"x": 10, "y": 5}, hunter["position"])
        self.assertTrue(any("MonsterMove(hunting pet" in event for event in result["events"]))
        self.assertTrue(any("MonsterFight(hunting pet,hunted target)" in event for event in result["events"]))
        self.assertTrue(any("MonsterKilled(hunted target)" in event for event in result["events"]))

    def test_hunt_never_overlaps_an_actor_when_target_survives(self) -> None:
        result = assert_lanes_match(self, hunt_task(seed=502, waits=2, speed=2))
        monsters = result["readout"]["private"]["monsters"]
        positions = [(monster["position"]["x"], monster["position"]["y"]) for monster in monsters]
        self.assertEqual(len(positions), len(set(positions)))
        self.assertEqual(2, len(monsters))

    def test_randomized_hunt_routes_preserve_cross_language_state_and_events(self) -> None:
        for seed in range(503, 511):
            with self.subTest(seed=seed):
                result = assert_lanes_match(
                    self,
                    hunt_task(
                        seed=seed,
                        waits=2 + seed % 5,
                        speed=1 + seed % 2,
                        wall_x=6 + seed % 3,
                    ),
                )
                monsters = result["readout"]["private"]["monsters"]
                positions = [(monster["position"]["x"], monster["position"]["y"]) for monster in monsters]
                self.assertEqual(len(positions), len(set(positions)))

    def test_checkpoint_preserves_hunt_target_and_continuation(self) -> None:
        task = hunt_task(seed=511, waits=0)
        resolved = resolve_task(task)
        engine = NethackDlvl1Engine()
        engine.reset(resolved)
        engine.step("MiscDirection.WAIT")
        engine.step("MiscDirection.WAIT")
        checkpoint = engine.checkpoint_bytes()
        for _ in range(3):
            engine.step("MiscDirection.WAIT")
        restored = rust_restore(checkpoint, ["MiscDirection.WAIT"] * 3)
        self.assertEqual(engine.symbolic_readout(), restored["projection"])


if __name__ == "__main__":
    unittest.main()
