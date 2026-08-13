from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.nle_authoritative_entity_contract import (
    NLE_090_OBSERVATION_KEYS,
    SCHEMA,
    evaluate_nle_090_public_surface,
    validate_authoritative_entity_export,
)


def complete_export() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "source_step": 4,
        "captured_before_action": True,
        "turn_queue": ["m-7"],
        "entities": [
            {
                "entity_id": "m-7",
                "species_id": 42,
                "allegiance": "hostile",
                "x": 12,
                "y": 8,
                "hp": 3,
                "hp_max": 5,
                "underlay": {"terrain_glyph": 2378, "terrain_char": ".", "object_stack_complete": True},
                "scheduler": {"speed": 12, "movement_points": 6, "ai_state": "aware", "turn_order": 0},
            }
        ],
    }


class AuthoritativeEntityContractTests(unittest.TestCase):
    def test_complete_pre_action_export_has_a_real_eligible_path(self) -> None:
        report = validate_authoritative_entity_export(complete_export(), expected_source_step=4)
        self.assertEqual("eligible", report["status"])

    def test_glyph_species_and_coordinates_cannot_replace_stable_id_or_hidden_state(self) -> None:
        export = complete_export()
        entity = export["entities"][0]  # type: ignore[index]
        entity.pop("entity_id")
        entity.pop("hp")
        entity["glyph"] = 397
        entity["same_glyph_previous_frame"] = True
        report = validate_authoritative_entity_export(export)
        codes = {reason["code"] for reason in report["reasons"]}
        self.assertEqual("rejected", report["status"])
        self.assertIn("missing_entity_fields", codes)
        self.assertIn("incomplete_entity_identity", codes)

    def test_post_action_capture_and_incomplete_turn_queue_are_rejected(self) -> None:
        export = complete_export()
        export["captured_before_action"] = False
        export["turn_queue"] = []
        report = validate_authoritative_entity_export(export)
        codes = {reason["code"] for reason in report["reasons"]}
        self.assertIn("not_pre_action", codes)
        self.assertIn("turn_queue_not_complete", codes)

    def test_source_underlay_and_scheduler_are_not_optional(self) -> None:
        export = complete_export()
        entity = export["entities"][0]  # type: ignore[index]
        entity["underlay"] = {"terrain_glyph": 2378, "terrain_char": ".", "object_stack_complete": False}
        entity["scheduler"] = {"speed": 12}
        report = validate_authoritative_entity_export(export)
        codes = {reason["code"] for reason in report["reasons"]}
        self.assertIn("invalid_underlay", codes)
        self.assertIn("missing_scheduler_state", codes)

    def test_pinned_public_surface_is_rejected_even_when_repeatable(self) -> None:
        report = evaluate_nle_090_public_surface(
            observation_keys=NLE_090_OBSERVATION_KEYS,
            environment_methods=["close", "get_seeds", "reset", "seed", "step"],
            low_level_methods=["close", "get_seeds", "reset", "set_buffers", "step"],
        )
        self.assertEqual("rejected", report["status"])
        self.assertIn("no_authoritative_entity_export", {reason["code"] for reason in report["reasons"]})

    def test_new_public_entity_export_is_audit_breakage_not_implicit_permission(self) -> None:
        report = evaluate_nle_090_public_surface(
            observation_keys=NLE_090_OBSERVATION_KEYS,
            environment_methods=["entities"],
            low_level_methods=[],
        )
        self.assertEqual("rejected", report["status"])
        self.assertIn("unexpected_entity_export", {reason["code"] for reason in report["reasons"]})

    def test_native_adapter_must_explicitly_remain_assertion_only(self) -> None:
        export = complete_export()
        export["source_adapter"] = "pinned_native_macho_v1"
        report = validate_authoritative_entity_export(export)
        self.assertEqual("rejected", report["status"])
        self.assertIn("native_scope_not_explicit", {reason["code"] for reason in report["reasons"]})


if __name__ == "__main__":
    unittest.main()
