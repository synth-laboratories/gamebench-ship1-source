#!/usr/bin/env python3
"""ROM-free validation tests for the named Emerald source-oracle registry."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("emerald_oracle_registry.py")
SPEC = importlib.util.spec_from_file_location("emerald_registry", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
REGISTRY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = REGISTRY
SPEC.loader.exec_module(REGISTRY)


class EmeraldOracleRegistryTest(unittest.TestCase):
    def test_bedroom_identity_and_projection_are_authenticated(self) -> None:
        root, checkpoint = REGISTRY.resolve_checkpoint("bedroom_idle")
        self.assertEqual("bedroom_idle", root["default_checkpoint"])
        self.assertTrue(checkpoint.authenticated)
        self.assertEqual(
            {
                "player": {"x": 1, "y": 1},
                "map": "mays_house2_f",
            },
            REGISTRY.normalize_source_semantics(
                checkpoint,
                {"map_group": 1, "map_number": 3, "player_x": 1, "player_y": 3},
            ),
        )

    def test_mays_house_transition_boundaries_are_current_v8_oracles(self) -> None:
        for checkpoint_id, map_group, map_number, player_x, player_y in (
            ("mays_house_1f", 1, 2, 2, 8),
            ("mays_house_2f", 1, 3, 1, 2),
        ):
            _, checkpoint = REGISTRY.resolve_checkpoint(checkpoint_id)
            self.assertTrue(checkpoint.authenticated)
            self.assertEqual(
                {
                    "map_group": map_group,
                    "map_number": map_number,
                    "player_x": player_x,
                    "player_y": player_y,
                },
                checkpoint.source["initial_state"],
            )
            self.assertEqual(
                "fresh adapter reload matched one no-input continuation frame and source_state",
                checkpoint.capture["provenance"]["round_trip"],
            )
            self.assertIn("superseded_provenance", checkpoint.capture)

    def test_pending_checkpoint_fails_closed(self) -> None:
        _, checkpoint = REGISTRY.resolve_checkpoint("route103_rival_battle")
        with self.assertRaisesRegex(REGISTRY.RegistryError, "capture_required"):
            REGISTRY.require_authenticated(checkpoint)

    def test_clock_tv_boundary_is_quarantined_until_v7_recapture(self) -> None:
        _, checkpoint = REGISTRY.resolve_checkpoint("clock_tv_downstairs")
        self.assertFalse(checkpoint.authenticated)
        with self.assertRaisesRegex(REGISTRY.RegistryError, "capture_required"):
            REGISTRY.require_authenticated(checkpoint)

    def test_mislabeled_checkpoint_is_validated_but_cannot_be_used_as_oracle(self) -> None:
        _, checkpoint = REGISTRY.resolve_checkpoint(
            "route103_wild_turn1_move_menu_legacy_mislabeled"
        )
        self.assertEqual("quarantined_mislabeled", checkpoint.status)
        self.assertIsNotNone(checkpoint.source)
        self.assertFalse(checkpoint.authenticated)
        with self.assertRaisesRegex(REGISTRY.RegistryError, "quarantined_mislabeled"):
            REGISTRY.require_authenticated(checkpoint)

    def test_continuous_route103_victory_is_promoted_from_its_authenticated_input(self) -> None:
        _, checkpoint = REGISTRY.resolve_checkpoint("route103_rival_victory_field")
        self.assertTrue(checkpoint.authenticated)
        trace = checkpoint.capture["continuous_battle_trace_output"]
        self.assertEqual("route103_rival_battle_command", trace["source_checkpoint"])
        self.assertEqual(checkpoint.source["state_sha256"], trace["terminal_state_sha256"])
        self.assertEqual(0, trace["intermediate_reload_count"])
        self.assertEqual(trace["vblank_count"] + 1, trace["sample_count"])
        self.assertEqual(checkpoint, REGISTRY.require_authenticated(checkpoint))

    def test_continuous_route103_victory_rejects_unbound_output_state(self) -> None:
        raw = json.loads(REGISTRY.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
        altered = copy.deepcopy(raw)
        checkpoint = next(
            value for value in altered["checkpoints"]
            if value["id"] == "route103_rival_victory_field"
        )
        checkpoint["capture"]["continuous_battle_trace_output"][
            "terminal_state_sha256"
        ] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "registry.json"
            registry_path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(REGISTRY.RegistryError, "terminal differs from source"):
                REGISTRY.load_registry(registry_path)

    def test_authenticated_rows_require_current_receipt_identity(self) -> None:
        raw = json.loads(REGISTRY.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
        altered = copy.deepcopy(raw)
        checkpoint = next(
            value for value in altered["checkpoints"] if value["id"] == "route103_wild_command"
        )
        checkpoint["capture"]["provenance"].pop("receipt_sha256")
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "registry.json"
            registry_path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(REGISTRY.RegistryError, "without a receipt identity"):
                REGISTRY.load_registry(registry_path)

    def test_authenticated_rows_reject_superseded_or_self_quarantined_evidence(self) -> None:
        raw = json.loads(REGISTRY.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
        altered = copy.deepcopy(raw)
        checkpoint = next(
            value for value in altered["checkpoints"] if value["id"] == "route103_wild_command"
        )
        checkpoint["capture"]["provenance"]["evidence_status"] = (
            "audit_only_superseded_adapter_identity"
        )
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "registry.json"
            registry_path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(REGISTRY.RegistryError, "superseded adapter evidence"):
                REGISTRY.load_registry(registry_path)

    def test_running_shoes_field_receipts_are_bound_to_checkpoint_states(self) -> None:
        for checkpoint_id in ("running_shoes_granted", "running_shoes_departure"):
            _, checkpoint = REGISTRY.resolve_checkpoint(checkpoint_id)
            assertion = checkpoint.capture["field_state_assertion"]
            self.assertEqual(
                checkpoint.source["state_sha256"], assertion["state_sha256"]
            )
            self.assertEqual(
                {
                    "FLAG_RECEIVED_RUNNING_SHOES": True,
                    "FLAG_SYS_B_DASH": True,
                },
                assertion["expected_flags"],
            )

    def test_v9_registry_is_trusted_and_legacy_adapter_hashes_are_quarantined(self) -> None:
        registry, _ = REGISTRY.load_registry()
        self.assertIsNone(REGISTRY.oracle_quarantine_reason(registry))
        self.assertEqual("9", registry["oracle"]["config"]["adapter_version"])
        self.assertIn(
            "observability_source_sha256", registry["oracle"]["config"]
        )
        self.assertIn(
            "8644c09a3e3e479521de51133912e96e417c523e221512cd334f8694922227bb",
            REGISTRY.QUARANTINED_ADAPTER_SOURCE_SHA256,
        )
        self.assertIn(
            "f7102b2fbf66f8e96f26dd77f2054b9bfd20fdc60e7a8886c74a2408afd815cf",
            REGISTRY.SUPERSEDED_ADAPTER_SOURCE_SHA256,
        )

    def test_unknown_checkpoint_lists_known_choices(self) -> None:
        with self.assertRaisesRegex(REGISTRY.RegistryError, "available:.*bedroom_idle"):
            REGISTRY.resolve_checkpoint("not_a_checkpoint")

    def test_capture_required_row_cannot_smuggle_source_hashes(self) -> None:
        raw = json.loads(REGISTRY.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
        altered = copy.deepcopy(raw)
        pending = next(
            value for value in altered["checkpoints"] if value["id"] == "title_menu"
        )
        pending["source"] = {
            "state_sha256": "0" * 64,
            "initial_rgb_sha256": "0" * 64,
            "initial_state": {"map_group": 0},
        }
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "registry.json"
            registry_path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(REGISTRY.RegistryError, "must not contain source identity"):
                REGISTRY.load_registry(registry_path)


if __name__ == "__main__":
    unittest.main()
