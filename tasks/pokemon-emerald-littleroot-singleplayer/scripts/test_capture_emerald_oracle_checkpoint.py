#!/usr/bin/env python3
"""ROM-free tests for snapshot-capture parsing and registry promotion guards."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("capture_emerald_oracle_checkpoint.py")
SPEC = importlib.util.spec_from_file_location("emerald_capture", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
CAPTURE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CAPTURE
SPEC.loader.exec_module(CAPTURE)


class EmeraldOracleCaptureTest(unittest.TestCase):
    def test_empty_bedroom_validation_tape_is_concrete_and_deterministic(self) -> None:
        tape = (
            Path(__file__).parents[1]
            / "fixtures"
            / "gold"
            / "oracle_capture_tapes"
            / "bedroom_idle_empty.json"
        )
        ticks, digest = CAPTURE.expand_program(tape)
        self.assertEqual([], ticks)
        self.assertEqual(64, len(digest))

    def test_promotion_requires_an_unpromoted_target(self) -> None:
        source = json.loads(CAPTURE.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
        target_id = next(
            row["id"]
            for row in source["checkpoints"]
            if row["status"] == "capture_required"
        )
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "registry.json"
            registry_path.write_text(json.dumps(source), encoding="utf-8")
            CAPTURE.promote(
                registry_path=registry_path,
                target_id=target_id,
                source_state_sha256="a" * 64,
                initial_rgb_sha256="b" * 64,
                initial_source_state={
                    "player_x": 10,
                    "player_y": 14,
                    "map_group": 0,
                    "map_number": 16,
                },
                from_checkpoint="birch_lab_exterior",
                tape_sha256="c" * 64,
                snapshot_frame_number=42,
            )
            promoted = json.loads(registry_path.read_text(encoding="utf-8"))
            row = next(row for row in promoted["checkpoints"] if row["id"] == target_id)
            self.assertEqual("authenticated", row["status"])
            self.assertEqual("a" * 64, row["source"]["state_sha256"])
            with self.assertRaisesRegex(CAPTURE.CaptureError, "not an unpromoted"):
                CAPTURE.promote(
                    registry_path=registry_path,
                    target_id=target_id,
                    source_state_sha256="a" * 64,
                    initial_rgb_sha256="b" * 64,
                    initial_source_state={"player_x": 10, "player_y": 14, "map_group": 0, "map_number": 16},
                    from_checkpoint="birch_lab_exterior",
                    tape_sha256="c" * 64,
                    snapshot_frame_number=42,
                )

    def test_terminal_source_assertions_gate_position_and_observability(self) -> None:
        metadata = {
            "source_assertions": {
                "terminal_source_position": {
                    "map_group": 0, "map_number": 9, "player_x": 14, "player_y": 8,
                },
                "terminal_observability": {
                    "story_vars": {"littleroot_rival_state": 3},
                    "palette_fade": {"active": False},
                },
                "minimum_dialogue_pages": 13,
            }
        }
        source_state = {
            "map_group": 0, "map_number": 9, "player_x": 14, "player_y": 8,
            "observability": {
                "story_vars": {"littleroot_rival_state": 3},
                "palette_fade": {"active": False},
            },
        }
        CAPTURE.validate_terminal_source_assertions(metadata, source_state)
        self.assertEqual(
            ["minimum_dialogue_pages"],
            metadata["assertion_validation"]["unverified_keys"],
        )
        source_state["observability"]["story_vars"]["littleroot_rival_state"] = 2
        with self.assertRaisesRegex(CAPTURE.CaptureError, "rival_state.*mismatch"):
            CAPTURE.validate_terminal_source_assertions(metadata, source_state)


if __name__ == "__main__":
    unittest.main()
