"""Broad parity coverage for the arbitrary-seed authored bootstrap."""

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
from shared.task_resolve import procedural_species_profile, resolve_task


def generated_task(seed: int, actions: list[object] | None = None) -> dict[str, object]:
    return {
        "task_id": f"procedural-seed-{seed}",
        "seed": seed,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 6},
        "actions": list(actions or []),
    }


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


class ProceduralSeedBootstrapTests(unittest.TestCase):
    def test_seeded_levels_vary_causal_actor_and_light_inputs(self) -> None:
        resolved = [resolve_task(generated_task(seed)) for seed in range(600, 616)]
        positions = {
            tuple(
                (monster["id"], monster["position"]["x"], monster["position"]["y"])
                for monster in task["level_dump"]["monsters"]
            )
            for task in resolved
        }
        self.assertGreater(len(positions), 1)
        self.assertTrue(all(any(monster.get("pet") for monster in task["level_dump"]["monsters"]) for task in resolved))
        self.assertTrue(all(any(monster.get("corpse") for monster in task["level_dump"]["monsters"]) for task in resolved))
        self.assertGreater(
            len({task["level_dump"]["light_sources"][0]["radius"] for task in resolved}),
            1,
        )
        self.assertGreater(
            len({task["level_dump"]["monsters"][-1]["base_speed"] for task in resolved}),
            1,
        )
        self.assertTrue(
            all(
                monster["name"] in {"sewer rat", "newt", "fox"}
                and monster["species_id"] in {13, 87, 318}
                and monster["movement_points"] == 0
                for task in resolved
                for monster in task["level_dump"]["monsters"][:3]
            )
        )
        self.assertTrue(
            all(
                task["level_dump"]["light_sources"][0]["follow"] == "generated-dog"
                for task in resolved
            )
        )

    def test_species_selector_covers_every_weighted_interval(self) -> None:
        profiles = [procedural_species_profile(selector) for selector in range(16)]
        self.assertEqual(["sewer rat"] * 6, [profile["name"] for profile in profiles[:6]])
        self.assertEqual(["newt"] * 5, [profile["name"] for profile in profiles[6:11]])
        self.assertEqual(["fox"] * 5, [profile["name"] for profile in profiles[11:]])
        self.assertEqual({6, 12, 15}, {profile["base_speed"] for profile in profiles})
        self.assertEqual(
            [(161, 1, 20, False), (37, 5, 10, False), (33, 1, 300, False)],
            [
                (
                    profile["geno"],
                    profile["generation_frequency"],
                    profile["corpse_weight"],
                    profile["no_corpse"],
                )
                for profile in (profiles[0], profiles[6], profiles[11])
            ],
        )
        with self.assertRaises(ValueError):
            procedural_species_profile(16)

    def test_arbitrary_seed_gameplay_tapes_match_in_both_lanes(self) -> None:
        tape = [
            "MiscDirection.WAIT",
            "MiscDirection.WAIT",
            "Command.EAT",
            25,
            "CompassDirection.E",
            "CompassDirection.S",
            "Command.SEARCH",
            "MiscDirection.WAIT",
            "Command.INVENTORY",
            "ESC",
            "Command.OPEN",
            "CompassDirection.E",
            "MiscDirection.WAIT",
        ]
        for seed in range(616, 628):
            with self.subTest(seed=seed):
                python = run_python(generated_task(seed, tape))
                rust = run_rust(generated_task(seed, tape))
                self.assertEqual(python["readout"], rust["readout"])
                self.assertEqual(python["events"], rust["events"])

    def test_python_checkpoint_continues_a_generated_pet_economy_in_rust(self) -> None:
        task = generated_task(628)
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("MiscDirection.WAIT")
        engine.step("MiscDirection.WAIT")
        checkpoint = engine.checkpoint_bytes()
        continuation = ["Command.EAT", 25, "MiscDirection.WAIT", "CompassDirection.E"]
        for action in continuation:
            engine.step(action)
        restored = rust_restore(checkpoint, continuation)
        self.assertEqual(engine.symbolic_readout(), restored["projection"])
        self.assertTrue(
            any(
                "MonsterEat(dog,a pet ration)" in event.get("message", "")
                for event in engine.nev.export()
            )
        )


if __name__ == "__main__":
    unittest.main()
