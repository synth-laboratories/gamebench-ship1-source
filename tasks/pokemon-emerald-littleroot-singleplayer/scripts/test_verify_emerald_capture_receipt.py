#!/usr/bin/env python3
"""ROM-free integrity tests for resumable Emerald snapshot receipts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("verify_emerald_capture_receipt.py")
SPEC = importlib.util.spec_from_file_location("emerald_receipt", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
RECEIPT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RECEIPT
SPEC.loader.exec_module(RECEIPT)


class ReceiptVerificationTest(unittest.TestCase):
    def test_validates_receipt_trace_and_relocated_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            state = directory / "checkpoint.state"
            state.write_bytes(b"raw mGBA state")
            state_sha = hashlib.sha256(state.read_bytes()).hexdigest()
            trace = {
                "schema": RECEIPT.TRACE_SCHEMA,
                "capture_tape_sha256": "a" * 64,
                "source_identity": {"rom_sha256": "b" * 64, "source_state_sha256": "c" * 64},
                "terminal_snapshot_state_sha256": state_sha,
                "terminal_source_position": {"map_group": 1, "map_number": 2, "player_x": 3, "player_y": 4},
            }
            trace["trace_sha256"] = hashlib.sha256(RECEIPT.canonical_json(trace).encode()).hexdigest()
            trace_path = directory / "trace.json"
            trace_path.write_text(json.dumps(trace), encoding="utf-8")
            receipt = {
                "schema": RECEIPT.RECEIPT_SCHEMA,
                "round_trip": "exact_no_input_continuation",
                "capture_tape_sha256": "a" * 64,
                "source_identity": trace["source_identity"],
                "snapshot_state_sha256": state_sha,
                "snapshot_state_path": str(directory / "missing-original.state"),
                "capture_trace_path": str(trace_path),
                "capture_trace_sha256": trace["trace_sha256"],
                "terminal_source_position": trace["terminal_source_position"],
                "from_checkpoint": "bedroom_idle",
                "promote_checkpoint": None,
            }
            receipt["receipt_sha256"] = hashlib.sha256(RECEIPT.canonical_json(receipt).encode()).hexdigest()
            receipt_path = directory / "receipt.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            result = RECEIPT.verify(receipt_path, state)
            self.assertEqual("validated", result["status"])
            self.assertEqual("validated", result["trace"])

    def test_rejects_tampered_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            state = directory / "checkpoint.state"
            state.write_bytes(b"tampered")
            receipt = {
                "schema": RECEIPT.RECEIPT_SCHEMA, "round_trip": "exact_no_input_continuation",
                "capture_tape_sha256": "a" * 64,
                "source_identity": {"rom_sha256": "b" * 64, "source_state_sha256": "c" * 64},
                "snapshot_state_sha256": "a" * 64, "snapshot_state_path": str(state),
                "terminal_source_position": {"map_group": 1, "map_number": 1, "player_x": 1, "player_y": 1},
            }
            receipt["receipt_sha256"] = hashlib.sha256(RECEIPT.canonical_json(receipt).encode()).hexdigest()
            path = directory / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(RECEIPT.ReceiptError, "SHA-256"):
                RECEIPT.verify(path)

    def test_superseded_v7_is_audit_only_with_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            state = directory / "checkpoint.state"
            state.write_bytes(b"preserved v7 state")
            receipt = {
                "schema": RECEIPT.RECEIPT_SCHEMA,
                "round_trip": "exact_no_input_continuation",
                "capture_tape_sha256": "a" * 64,
                "source_identity": {
                    "rom_sha256": "b" * 64,
                    "source_state_sha256": "c" * 64,
                    "config": {
                        "adapter_source_sha256":
                            "f7102b2fbf66f8e96f26dd77f2054b9bfd20fdc60e7a8886c74a2408afd815cf"
                    },
                },
                "snapshot_state_sha256": hashlib.sha256(
                    state.read_bytes()
                ).hexdigest(),
                "snapshot_state_path": str(state),
                "terminal_source_position": {
                    "map_group": 0, "map_number": 9, "player_x": 14, "player_y": 8,
                },
            }
            receipt["receipt_sha256"] = hashlib.sha256(
                RECEIPT.canonical_json(receipt).encode()
            ).hexdigest()
            path = directory / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(RECEIPT.ReceiptError, "audit-only"):
                RECEIPT.verify(path)
            result = RECEIPT.verify(
                path, allow_superseded_identity=True
            )
            self.assertEqual("audit_only", result["status"])


if __name__ == "__main__":
    unittest.main()
