#!/usr/bin/env python3
"""ROM-free provenance tests for the full-scope coverage orchestrator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("emerald_coverage_orchestrator.py")
SPEC = importlib.util.spec_from_file_location("emerald_orchestrator", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ORCHESTRATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ORCHESTRATOR
SPEC.loader.exec_module(ORCHESTRATOR)


ROM = "a" * 64
STATE = "b" * 64
RGB = "c" * 64


class CoverageOrchestratorTest(unittest.TestCase):
    def test_validates_plan_provenance_roundtrip_and_trace_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            plan_path = directory / "plan.json"
            plan = {
                "schema": ORCHESTRATOR.SOURCE_PLAN_SCHEMA,
                "tapes": [{"id": "rival-run", "checkpoint": "rival_command", "status": "capture_ready"}],
            }
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            plans, diagnostics = ORCHESTRATOR.load_source_plans([plan_path])
            self.assertEqual([], diagnostics)
            registry = {"rom_sha256": ROM, "oracle": {"emulator": {"core": "mGBA"}, "config": {"audio": False}}}
            trace = {
                "schema": ORCHESTRATOR.SOURCE_TRACE_SCHEMA,
                "comparison": {"kind": "source_only", "rust_compared": False},
                "tape": {"id": "rival-run", "provenance": {
                    "plan_tape_id": "rival-run", "plan_manifest_sha256": ORCHESTRATOR.file_sha256(plan_path),
                    "checkpoint": "rival_command", "savestate_roundtrip": {
                        "status": "authenticated", "state_sha256": STATE, "initial_rgb_sha256": RGB,
                    },
                }},
                "source_identity": {"rom_sha256": ROM, "state_sha256": STATE, "emulator": {"core": "mGBA"}, "config": {"audio": False}},
                "initial_frame_rgb_sha256": RGB,
                "frame_count": 1,
                "frames": [{"vblank": 0, "source_state": {"map_group": 1}}],
            }
            trace["trace_sha256"] = ORCHESTRATOR.sha256_bytes(
                ORCHESTRATOR.canonical_json(trace).encode("utf-8")
            )
            trace_path = directory / "trace.json"
            trace_path.write_text(json.dumps(trace), encoding="utf-8")
            self.assertEqual(("rival-run", None), ORCHESTRATOR.validate_source_trace(trace_path, plans, registry))

    def test_rejects_trace_without_roundtrip_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            plan_path = directory / "plan.json"
            plan_path.write_text(json.dumps({"schema": ORCHESTRATOR.SOURCE_PLAN_SCHEMA, "tapes": [{"id": "x", "checkpoint": "x"}]}), encoding="utf-8")
            plans, _ = ORCHESTRATOR.load_source_plans([plan_path])
            trace = {
                "schema": ORCHESTRATOR.SOURCE_TRACE_SCHEMA,
                "comparison": {"kind": "source_only", "rust_compared": False},
                "tape": {"id": "x", "provenance": {"plan_tape_id": "x", "plan_manifest_sha256": ORCHESTRATOR.file_sha256(plan_path), "checkpoint": "x"}},
            }
            trace_path = directory / "trace.json"
            trace_path.write_text(json.dumps(trace), encoding="utf-8")
            tape_id, error = ORCHESTRATOR.validate_source_trace(trace_path, plans, {"rom_sha256": ROM, "oracle": {"emulator": {}, "config": {}}})
            self.assertIsNone(tape_id)
            self.assertIn("round-trip", error or "")


if __name__ == "__main__":
    unittest.main()
