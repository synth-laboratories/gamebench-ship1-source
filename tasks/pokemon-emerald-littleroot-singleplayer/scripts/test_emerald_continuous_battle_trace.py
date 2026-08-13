#!/usr/bin/env python3
"""ROM-free contracts for continuous Emerald battle tracing."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


def load_trace():
    mgba = types.ModuleType("mgba")
    core = types.ModuleType("mgba.core")
    log = types.ModuleType("mgba.log")
    mgba.core = core
    mgba.log = log
    prior = {name: sys.modules.get(name) for name in ("mgba", "mgba.core", "mgba.log")}
    sys.modules.update({"mgba": mgba, "mgba.core": core, "mgba.log": log})
    try:
        path = Path(__file__).with_name("emerald_continuous_battle_trace.py")
        spec = importlib.util.spec_from_file_location("continuous_trace_test", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        with mock.patch.object(importlib.metadata, "version", return_value="test"):
            spec.loader.exec_module(module)
        return module
    finally:
        for name, value in prior.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


TRACE = load_trace()
VERIFY_PATH = Path(__file__).with_name("verify_emerald_continuous_battle_trace.py")
VERIFY_SPEC = importlib.util.spec_from_file_location("continuous_verify_test", VERIFY_PATH)
assert VERIFY_SPEC and VERIFY_SPEC.loader
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)


class ContinuousBattleTraceTest(unittest.TestCase):
    def test_tape_expansion_preserves_every_vblank_and_markers(self) -> None:
        ticks, markers = TRACE.expand_tape({
            "program": [
                {"buttons": ["a"], "frames": 2, "marker": "confirm"},
                {"buttons": [], "frames": 3},
            ],
            "markers": [{"vblank": 0, "label": "initial"}, {"vblank": 5, "label": "terminal"}],
        })
        self.assertEqual([["a"], ["a"], [], [], []], ticks)
        self.assertEqual(
            {0: ["initial"], 2: ["confirm"], 5: ["terminal"]}, markers
        )

    def test_invalid_tapes_fail_before_core_access(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid buttons"):
            TRACE.expand_tape({
                "program": [{"buttons": ["turbo"], "frames": 1}]
            })
        with self.assertRaisesRegex(ValueError, "outside tape"):
            TRACE.expand_tape({
                "program": [{"buttons": [], "frames": 1}],
                "markers": [{"vblank": 2, "label": "bad"}],
            })

    def test_mon_parser_tracks_mutable_battle_fields(self) -> None:
        raw = bytearray(TRACE.BATTLE_MON_SIZE)
        raw[0:2] = (280).to_bytes(2, "little")
        raw[0x24:0x28] = bytes([34, 40, 0, 0])
        raw[0x28:0x2A] = (17).to_bytes(2, "little")
        raw[0x2C:0x2E] = (19).to_bytes(2, "little")
        raw[0x4C:0x50] = (8).to_bytes(4, "little")
        mon = TRACE.parse_mon(bytes(raw), 0, 0)
        self.assertEqual(280, mon["species"])
        self.assertEqual([34, 40, 0, 0], mon["pp"])
        self.assertEqual((17, 19, 8), (mon["hp"], mon["max_hp"], mon["status1"]))

    def test_verifier_requires_one_load_and_contiguous_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            input_state = directory / "input.state"
            terminal_state = directory / "terminal.state"
            input_state.write_bytes(b"input")
            terminal_state.write_bytes(b"terminal")
            registry, _ = VERIFY.load_registry()
            receipt = {
                "schema": VERIFY.SCHEMA,
                "identity": {
                    "rom_sha256": registry["rom_sha256"],
                    "input_state_sha256": VERIFY.file_sha256(input_state),
                    "terminal_state_sha256": VERIFY.file_sha256(terminal_state),
                    "container_image_id": VERIFY.EXPECTED_IMAGE_ID,
                    "script_sha256": VERIFY.file_sha256(VERIFY.TRACE_SCRIPT),
                    "symbol_manifest_sha256": VERIFY.file_sha256(
                        VERIFY.SYMBOL_MANIFEST
                    ),
                    "tape_sha256": "a" * 64,
                    "initial_state_advance_frames": 1,
                    "core_load_count": 1,
                    "intermediate_reload_count": 0,
                },
                "tape": {"vblank_count": 1, "marker_count": 0},
                "sample_count": 2,
                "samples": [
                    {"vblank": 0, "battle": {"battlers_count": 2}},
                    {"vblank": 1, "battle": {"battlers_count": 2}},
                ],
            }
            receipt["receipt_sha256"] = hashlib.sha256(
                VERIFY.canonical_json(receipt).encode()
            ).hexdigest()
            path = directory / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            result = VERIFY.verify(path, input_state, terminal_state)
            self.assertEqual("validated_continuous", result["status"])

            receipt["identity"]["intermediate_reload_count"] = 1
            receipt["receipt_sha256"] = hashlib.sha256(
                VERIFY.canonical_json({
                    key: value for key, value in receipt.items()
                    if key != "receipt_sha256"
                }).encode()
            ).hexdigest()
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(
                VERIFY.ContinuousTraceError, "intermediate reload"
            ):
                VERIFY.verify(path, input_state, terminal_state)


if __name__ == "__main__":
    unittest.main()
