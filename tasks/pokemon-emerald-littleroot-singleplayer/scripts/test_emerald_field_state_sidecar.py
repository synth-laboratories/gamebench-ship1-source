#!/usr/bin/env python3
"""ROM-free fail-closed tests for field-state receipt verification."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("verify_emerald_field_state_receipt.py")
SPEC = importlib.util.spec_from_file_location("field_receipt", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFY
SPEC.loader.exec_module(VERIFY)


class EmeraldFieldStateReceiptTest(unittest.TestCase):
    def receipt(self) -> dict:
        registry, _ = VERIFY.load_registry()
        value = {
            "schema": VERIFY.SCHEMA,
            "identity": {
                "rom_sha256": registry["rom_sha256"],
                "state_sha256": "1" * 64,
                "container_image_id": VERIFY.EXPECTED_IMAGE_ID,
                "script_sha256": VERIFY.file_sha256(VERIFY.SIDECAR_PATH),
                "symbol_manifest_sha256": VERIFY.file_sha256(VERIFY.MANIFEST_PATH),
                "initial_state_advance_frames": 1,
            },
            "field_state": {
                "save_block1_ptr": "0x02025a18",
                "flags": {
                    "FLAG_RECEIVED_RUNNING_SHOES": {
                        "flag_id": "0x112",
                        "address": "0x02026caa",
                        "raw_byte": 4,
                        "mask": "0x04",
                        "set": True,
                    },
                    "FLAG_SYS_B_DASH": {
                        "flag_id": "0x8c0",
                        "address": "0x02026da0",
                        "raw_byte": 1,
                        "mask": "0x01",
                        "set": True,
                    },
                },
            },
        }
        value["receipt_sha256"] = hashlib.sha256(
            VERIFY.canonical_json(value).encode("utf-8")
        ).hexdigest()
        return value

    def write(self, directory: str, value: dict) -> Path:
        path = Path(directory) / "receipt.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_valid_receipt_proves_both_independent_flags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = VERIFY.verify(self.write(directory, self.receipt()))
        self.assertEqual(
            {
                "FLAG_RECEIVED_RUNNING_SHOES": True,
                "FLAG_SYS_B_DASH": True,
            },
            result["flags"],
        )

    def test_receipt_digest_tampering_fails_closed(self) -> None:
        value = self.receipt()
        value["field_state"]["flags"]["FLAG_SYS_B_DASH"]["raw_byte"] = 0
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(VERIFY.FieldReceiptError, "receipt_sha256"):
                VERIFY.verify(self.write(directory, value))

    def test_rehashed_false_received_flag_fails_closed(self) -> None:
        value = self.receipt()
        value["field_state"]["flags"]["FLAG_RECEIVED_RUNNING_SHOES"]["set"] = False
        value.pop("receipt_sha256")
        value["receipt_sha256"] = hashlib.sha256(
            VERIFY.canonical_json(value).encode("utf-8")
        ).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                VERIFY.FieldReceiptError, "FLAG_RECEIVED_RUNNING_SHOES is not set"
            ):
                VERIFY.verify(self.write(directory, value))


if __name__ == "__main__":
    unittest.main()
