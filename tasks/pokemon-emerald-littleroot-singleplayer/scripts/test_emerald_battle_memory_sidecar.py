#!/usr/bin/env python3
"""ROM-free tests for battle-memory parsing and receipt verification."""

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


def load_sidecar():
    mgba = types.ModuleType("mgba")
    core = types.ModuleType("mgba.core")
    log = types.ModuleType("mgba.log")
    mgba.core = core
    mgba.log = log
    prior = {name: sys.modules.get(name) for name in ("mgba", "mgba.core", "mgba.log")}
    sys.modules.update({"mgba": mgba, "mgba.core": core, "mgba.log": log})
    try:
        path = Path(__file__).with_name("emerald_battle_memory_sidecar.py")
        spec = importlib.util.spec_from_file_location("battle_sidecar_test", path)
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


SIDECAR = load_sidecar()
VERIFY_PATH = Path(__file__).with_name("verify_emerald_battle_memory_receipt.py")
VERIFY_SPEC = importlib.util.spec_from_file_location("battle_verify_test", VERIFY_PATH)
assert VERIFY_SPEC and VERIFY_SPEC.loader
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)


class BattleMemorySidecarTest(unittest.TestCase):
    def test_battle_pokemon_offsets(self) -> None:
        raw = bytearray(SIDECAR.BATTLE_MON_SIZE)
        raw[0:2] = (280).to_bytes(2, "little")
        raw[0x0C:0x14] = b"".join(
            move.to_bytes(2, "little") for move in (10, 45, 0, 0)
        )
        raw[0x18:0x20] = bytes([6, 5, 4, 3, 2, 1, 0, 255])
        raw[0x24:0x28] = bytes([35, 40, 0, 0])
        raw[0x28:0x2A] = (19).to_bytes(2, "little")
        raw[0x2A] = 5
        raw[0x2C:0x2E] = (20).to_bytes(2, "little")
        mon = SIDECAR.parse_mon(bytes(raw), 0, 0)
        self.assertEqual(280, mon["species"])
        self.assertEqual([10, 45, 0, 0], mon["moves"])
        self.assertEqual([35, 40, 0, 0], mon["pp"])
        self.assertEqual([6, 5, 4, 3, 2, 1, 0, -1], mon["stat_stages"])
        self.assertEqual((19, 20, 5), (mon["hp"], mon["max_hp"], mon["level"]))

    def test_verifier_accepts_bound_identity_and_subset(self) -> None:
        registry, _ = VERIFY.load_registry()
        identity = {
            "rom_sha256": registry["rom_sha256"],
            "state_sha256": "a" * 64,
            "container_image_id": VERIFY.EXPECTED_IMAGE_ID,
            "script_sha256": VERIFY.file_sha256(VERIFY.SIDECAR_PATH),
            "symbol_manifest_sha256": VERIFY.file_sha256(
                VERIFY.SYMBOL_MANIFEST_PATH
            ),
            "initial_state_advance_frames": 1,
        }
        receipt = {
            "schema": VERIFY.SCHEMA,
            "identity": identity,
            "battle": {
                "battlers_count": 2,
                "mons": [{"species": 280}, {"species": 288}],
            },
        }
        receipt["receipt_sha256"] = hashlib.sha256(
            VERIFY.canonical_json(receipt).encode()
        ).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            result = VERIFY.verify(
                path,
                expected_battle={
                    "battlers_count": 2,
                    "mons": [{"species": 280}, {"species": 288}],
                },
            )
            self.assertEqual("validated", result["status"])
            with self.assertRaisesRegex(
                VERIFY.BattleReceiptError, "species.*mismatch"
            ):
                VERIFY.verify(
                    path, expected_battle={"mons": [{"species": 1}]}
                )


if __name__ == "__main__":
    unittest.main()
