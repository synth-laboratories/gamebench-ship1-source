#!/usr/bin/env python3
"""ROM-free integrity tests for the full-PPU receipt verifier."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

MODULE_PATH = Path(__file__).with_name("verify_emerald_ppu_receipt.py")
SPEC = importlib.util.spec_from_file_location("emerald_ppu_verify", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFY
SPEC.loader.exec_module(VERIFY)


class PpuReceiptVerifierTest(unittest.TestCase):
    def test_rejects_missing_full_register_surface_before_any_render_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = {"schema": VERIFY.SCHEMA, "source_identity": {}}
            path = root / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(VERIFY.ReceiptError, "trusted v8 identity"):
                VERIFY.verify(path)

    def test_raw_file_hash_mismatch_fails_closed(self) -> None:
        # The existing trusted registry lets this fixture reach file checking
        # without a ROM, state, or live emulator.
        registry = Path(__file__).parents[1] / "fixtures" / "gold" / "oracle_registry.json"
        raw = json.loads(registry.read_text(encoding="utf-8"))
        checkpoint = next(row for row in raw["checkpoints"] if row["id"] == "starter_battle")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {}
            for name, size in VERIFY.REQUIRED_FILES.items():
                path = root / f"{name}.bin"
                path.write_bytes(bytes(size))
                files[name] = {"path": path.name, "bytes": size, "sha256": hashlib.sha256(bytes(size)).hexdigest()}
            files["vram"]["sha256"] = "0" * 64
            source_state = {"state_sha256": "a" * 64}
            receipt = {
                "schema": VERIFY.SCHEMA,
                "source_identity": {"checkpoint": "starter_battle", "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(), "rom_sha256": raw["rom_sha256"], "state_sha256": checkpoint["source"]["state_sha256"], "adapter_source_sha256": raw["oracle"]["config"]["adapter_source_sha256"], "observability_source_sha256": raw["oracle"]["config"]["observability_source_sha256"]},
                "fresh_replay": {"status": "exact", "frame_rgb_sha256": "b" * 64, "source_state_sha256": "a" * 64},
                "frame_rgb_sha256": "b" * 64, "source_state": source_state, "files": files,
                "registers": {key: 0 for key in ("dispcnt", "bgcnt", "bg_offsets", "bg2_affine", "bg3_affine", "win0h", "win1h", "win0v", "win1v", "winin", "winout", "mosaic", "bldcnt", "bldalpha", "bldy")},
            }
            path = root / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(VERIFY.ReceiptError, "vram hash"):
                VERIFY.verify(path, registry)


if __name__ == "__main__":
    unittest.main()
