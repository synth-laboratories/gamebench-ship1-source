"""Parity coverage for opt-in authored movement-point scheduling."""

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


def scheduler_task(monsters: list[dict[str, object]], actions: list[object]) -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for y in range(3, 8):
        for x in range(2, 22):
            terrain[y][x] = "."
    return {
        "task_id": "generic-movement-points",
        "seed": 731,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 8},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 3, "y": 5},
            "monsters": monsters,
            "metadata": {"hp": 100, "hp_max": 100, "ac": 100, "hunger": 900},
        },
        "actions": actions,
    }


def actor(actor_id: str, x: int, *, points: int, base_speed: int, initiative: int = 0) -> dict[str, object]:
    return {
        "id": actor_id,
        "name": actor_id,
        "char": "g",
        "position": {"x": x, "y": 5},
        "hp": 20,
        "attack": 1,
        "movement": "chase",
        "vision": 30,
        "base_speed": base_speed,
        "movement_points": points,
        "initiative": initiative,
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
            "cargo", "run", "--quiet", "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin", "scenario", "--", "--checkpoint-replay-stdin",
        ],
        input=json.dumps({"checkpoint": checkpoint.decode("utf-8"), "actions": actions}),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


class GenericMovementPointTests(unittest.TestCase):
    def test_zero_points_allocate_only_after_the_first_drained_turn(self) -> None:
        task = scheduler_task([actor("slow", 12, points=0, base_speed=12)], ["MiscDirection.WAIT"])
        first = assert_lanes_match(self, task)
        monster = first["readout"]["private"]["monsters"][0]
        self.assertEqual({"x": 12, "y": 5}, monster["position"])
        self.assertEqual(12, monster["movement_points"])

        task["actions"].append("MiscDirection.WAIT")
        second = assert_lanes_match(self, task)
        monster = second["readout"]["private"]["monsters"][0]
        self.assertNotEqual({"x": 12, "y": 5}, monster["position"])
        self.assertEqual(12, monster["movement_points"])

    def test_queue_interleaves_fast_actor_passes_by_initiative(self) -> None:
        task = scheduler_task(
            [
                actor("actor-a", 14, points=24, base_speed=0, initiative=2),
                actor("actor-b", 18, points=12, base_speed=0, initiative=1),
            ],
            ["MiscDirection.WAIT"],
        )
        result = assert_lanes_match(self, task)
        moves = [event for event in result["events"] if "MonsterMove(" in event]
        self.assertEqual(["actor-a", "actor-b", "actor-a"], [next(name for name in ("actor-a", "actor-b") if name in event) for event in moves])
        self.assertEqual([0, 0], [monster["movement_points"] for monster in result["readout"]["private"]["monsters"]])

    def test_fast_adjacent_hostile_takes_two_complete_attack_actions(self) -> None:
        monster = actor("fast-attacker", 4, points=24, base_speed=0)
        monster.update({
            "combat_model": "d20",
            "armor_class": 10,
            "level": 1,
            "to_hit": 100,
            "damage_dice": 1,
            "damage_sides": 1,
        })
        result = assert_lanes_match(self, scheduler_task([monster], ["MiscDirection.WAIT"]))
        attacks = [event for event in result["events"] if "MonsterAttack(fast-attacker)" in event]
        self.assertEqual(2, len(attacks))
        self.assertEqual(98, result["readout"]["private"]["hp"])

    def test_legacy_schedule_combinations_are_rejected(self) -> None:
        for conflicting in ("speed", "turn_period", "turn_offset"):
            with self.subTest(conflicting=conflicting):
                monster = actor("invalid", 10, points=0, base_speed=12)
                monster[conflicting] = 1
                with self.assertRaises(ValueError):
                    resolve_task(scheduler_task([monster], []))

    def test_checkpoint_preserves_points_and_zero_turn_inputs_do_not_allocate(self) -> None:
        task = scheduler_task([actor("checkpoint-actor", 12, points=0, base_speed=12)], [])
        zero_turn = assert_lanes_match(self, {**task, "actions": ["Command.INVENTORY"]})
        self.assertEqual(0, zero_turn["readout"]["private"]["monsters"][0]["movement_points"])

        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("MiscDirection.WAIT")
        self.assertEqual(12, engine.state["monsters"][0]["movement_points"])
        checkpoint = engine.checkpoint_bytes()
        continuation = ["MiscDirection.WAIT", "MiscDirection.WAIT"]
        for action in continuation:
            engine.step(action)
        restored = rust_restore(checkpoint, continuation)
        self.assertEqual(engine.symbolic_readout(), restored["projection"])


if __name__ == "__main__":
    unittest.main()
