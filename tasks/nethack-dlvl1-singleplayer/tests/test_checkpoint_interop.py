"""Regression coverage for canonical inventory classes across checkpoints."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from scripts.judge_nle_tapes import layers as judge_layers
from shared.task_resolve import resolve_task


def rust_scenario(arguments: list[str], payload: Any) -> dict[str, Any]:
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
            *arguments,
        ],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


class CheckpointInteropTests(unittest.TestCase):
    def test_canonical_oclass_survives_rust_reset_and_python_checkpoint_restore(self) -> None:
        """NLE's numeric class must not be replaced by the item's ASCII kind."""

        task = {
            "task_id": "checkpoint-canonical-oclass",
            "fixture_id": "val-east-seed-20260725",
            "seed": 20260725,
        }
        resolved = resolve_task(task)
        expected_oclass = resolved["level_dump"]["inventory"][0]["oclass"]
        self.assertEqual(2, expected_oclass)
        self.assertNotEqual(ord(resolved["level_dump"]["inventory"][0]["kind"]), expected_oclass)

        python = NethackDlvl1Engine()
        python.reset(resolved)
        checkpoint = python.checkpoint_bytes().decode("utf-8")
        # The Rust lane deliberately requires materialized fixtures.  Passing
        # the already resolved level also exercises its canonical-item input.
        rust_task = {**task, "level_dump": resolved["level_dump"]}

        direct_rust = rust_scenario([], rust_task)["readout"]["public"]
        restored_rust = rust_scenario(["--checkpoint-stdin"], checkpoint)["projection"]["public"]
        self.assertEqual(expected_oclass, direct_rust["inventory"]["items"][0]["oclass"])
        self.assertEqual(expected_oclass, restored_rust["inventory"]["items"][0]["oclass"])
        self.assertEqual(direct_rust["inventory"]["items"], restored_rust["inventory"]["items"])

    def test_confirmed_quit_matches_nle_cleared_primary_observation_but_keeps_private_cause(self) -> None:
        """NLE clears primary planes after quit while retaining its TTY score screen."""

        task = {
            "task_id": "quit-terminal-observation",
            "fixture_id": "val-east-seed-20260725",
            "seed": 20260725,
        }
        resolved = resolve_task(task)
        actions = ["Command.QUIT", "CompassDirection.NW"]  # raw `y` in NLE's y/n prompt

        python = NethackDlvl1Engine()
        python.reset(resolved)
        inventory_before = python.public_projection()["inventory"]
        for action in actions:
            python.step(action)
        python_readout = python.symbolic_readout()

        rust_task = {**task, "level_dump": resolved["level_dump"], "actions": actions}
        rust_readout = rust_scenario([], rust_task)["readout"]
        for readout in (python_readout, rust_readout):
            public = readout["public"]
            self.assertTrue(public["done"])
            self.assertEqual("quit", public["terminal_reason"])
            self.assertEqual(["\0" * 79] * 21, public["chars"])
            self.assertEqual([[0] * 79] * 21, public["colors"])
            self.assertEqual([[2359] * 79] * 21, public["glyphs"])
            self.assertEqual([0] * 27, public["blstats"])
            self.assertEqual("", public["message"])
            self.assertEqual([0] * 256, public["message_raw"])
            self.assertEqual(inventory_before, public["inventory"])
            self.assertEqual("quit", readout["private"]["terminal_reason"])
            terminal_tty = public["terminal_tty"]
            self.assertEqual([6, 77], terminal_tty["cursor_yx"])
            self.assertEqual(" No  Points     Name                                                   Hp [max] ", terminal_tty["char_rows"][1])
            self.assertEqual("            0  Agent-Val-Hum-Fem-Law quit in The Dungeons of Doom on            ", terminal_tty["char_rows"][3])
            self.assertEqual("              level 1.                                               16  [16]   ", terminal_tty["char_rows"][5])
            expected_snapshot = {
                "projection": {
                    "tty_chars": [[ord(character) for character in row] for row in terminal_tty["char_rows"]],
                    "tty_colors": terminal_tty["color_rows"],
                    "tty_cursor_yx": terminal_tty["cursor_yx"],
                }
            }
            self.assertEqual(judge_layers(expected_snapshot, public)["terminal_ui"][0], judge_layers(expected_snapshot, public)["terminal_ui"][1])


if __name__ == "__main__":
    unittest.main()
