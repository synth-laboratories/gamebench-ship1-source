"""Parity coverage for fixture-free arbitrary-seed Level-1 bootstrap."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario as run_python
from scripts.rust_scenario import run_scenario as run_rust
from shared.task_resolve import resolve_task


class ProceduralBootstrapTests(unittest.TestCase):
    def test_arbitrary_seeds_start_a_playable_level_in_both_lanes(self) -> None:
        for seed in (-17, 0, 1, 23, 20260806, 0x7FFFFFFF):
            with self.subTest(seed=seed):
                task = {
                    "task_id": f"generated-{seed}",
                    "seed": seed,
                    "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
                    "actions": [
                        "MiscDirection.WAIT",
                        "CompassDirection.E",
                        "Command.SEARCH",
                        "Command.INVENTORY",
                    ],
                }
                resolved = resolve_task(task)
                level = resolved["level_dump"]
                self.assertEqual(1, level["dungeon_level"])
                terrain = "".join(level["terrain"])
                self.assertIn(">", terrain)
                self.assertIn("+", "".join(level["terrain"]))
                self.assertGreaterEqual(len(level["objects"]), 2)
                self.assertGreaterEqual(len(level["inventory"]), 2)
                self.assertGreaterEqual(len(level["monsters"]), 3)
                self.assertGreaterEqual(len(level["traps"]), 1)

                python = run_python(task)
                rust = run_rust(task)
                self.assertEqual(python["readout"], rust["readout"])
                self.assertFalse(python["readout"]["terminated"])
                self.assertEqual(4, python["readout"]["private"]["step_index"])


if __name__ == "__main__":
    unittest.main()
