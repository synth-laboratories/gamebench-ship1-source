"""Fail-closed tests for the NLE full-map/FOV source-capability audit."""

from __future__ import annotations

import ctypes
import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.audit_nle_map_fov_contract import (
    EXPECTED_OBSERVATION_SHAPES,
    assert_pinned_schema,
    full_map_fov_applicability,
)
from scripts.nle_native_map_fov import IN_SIGHT, NativeMapFovSnapshot, OBS_COLNO, ROWNO, Rm


def source_record(seed: int, *, fields: list[str] | None = None, native: bool = False) -> dict:
    return {
        "seed": seed,
        "boundary": "reset_before_any_action",
        "replayed_exactly": True,
        "authoritative_fields_present": [] if fields is None else fields,
        "authoritative_export": ({
            "provenance": "read_only_hash_verified_live_nle_v0_9_0_macho_level_and_viz_array",
            "full_map_terrain": [],
            "full_map_terrain_flags": [],
            "full_map_terrain_horizontal": [],
            "fov_visibility_mask": [],
            "map_memory": {},
        } if native else {}),
    }


class AuthoritativeMapFovAuditTests(unittest.TestCase):
    def test_pinned_schema_rejects_a_new_unreviewed_plane(self) -> None:
        schema = {key: {"shape": shape} for key, shape in EXPECTED_OBSERVATION_SHAPES.items()}
        assert_pinned_schema(schema)
        schema["full_map_terrain"] = {"shape": (21, 79)}
        with self.assertRaisesRegex(AssertionError, "observation keys changed"):
            assert_pinned_schema(schema)

    def test_rendered_map_does_not_become_full_map_or_fov_authority(self) -> None:
        report = full_map_fov_applicability([source_record(10), source_record(11), source_record(12)])
        self.assertEqual("blocked", report["status"])
        codes = {reason["code"] for reason in report["reasons"]}
        self.assertIn("missing_authoritative_source_planes", codes)
        self.assertIn("unverified_native_source", codes)

    def test_current_or_future_frame_is_not_accepted_as_pre_action(self) -> None:
        records = [source_record(10), source_record(11), source_record(12)]
        records[2]["boundary"] = "after_action_step_1"
        report = full_map_fov_applicability(records)
        self.assertEqual("blocked", report["status"])
        self.assertIn("not_pre_action", {reason["code"] for reason in report["reasons"]})

    def test_three_distinct_replayed_source_cases_are_required(self) -> None:
        report = full_map_fov_applicability([source_record(10), source_record(10), source_record(11)])
        self.assertEqual("blocked", report["status"])
        self.assertIn("insufficient_distinct_seed_cases", {reason["code"] for reason in report["reasons"]})

    def test_future_api_can_pass_only_with_three_distinct_direct_planes(self) -> None:
        fields = ["full_map_terrain", "full_map_terrain_flags", "full_map_terrain_horizontal", "fov_visibility_mask", "map_memory"]
        report = full_map_fov_applicability([
            source_record(10, fields=fields, native=True),
            source_record(11, fields=fields, native=True),
            source_record(12, fields=fields, native=True),
        ])
        self.assertEqual("eligible", report["status"])
        self.assertTrue(report["source_export_eligible"])
        self.assertFalse(report["gold_implementation_eligible"])

    def test_native_export_keeps_terrain_fov_and_memory_as_distinct_planes(self) -> None:
        grid = lambda value: tuple(tuple(value for _ in range(OBS_COLNO)) for _ in range(ROWNO))
        snapshot = NativeMapFovSnapshot(
            terrain_type=grid(24),
            terrain_flags=grid(0),
            terrain_horizontal=grid(False),
            map_memory_glyph=grid(2378),
            map_memory_seenv=grid(0),
            visibility_bits=grid(IN_SIGHT),
            binary_sha256="pinned",
        )
        record = snapshot.public_record()
        self.assertTrue(record["source_export_eligible"])
        self.assertFalse(record["gold_implementation_eligible"])
        self.assertEqual(ROWNO, len(record["full_map_terrain"]))
        self.assertEqual(OBS_COLNO, len(record["full_map_terrain"][0]))
        self.assertEqual(0, record["full_map_terrain_flags"][0][0])
        self.assertFalse(record["full_map_terrain_horizontal"][0][0])
        self.assertEqual("full_map_terrain_flags is struct rm.flags (five bits)", record["semantic_terrain_contract"]["raw_flags"])
        self.assertTrue(record["fov_visibility_mask"][0][0])
        self.assertFalse(record["fov_could_see_mask"][0][0])
        self.assertEqual(2378, record["map_memory"]["glyph"][0][0])
        self.assertEqual("NLE screen [y][x] maps to native level.locations[x+1][y]; native boundary x=0 is excluded", record["coordinate_contract"])
        self.assertEqual(8, ctypes.sizeof(Rm))


if __name__ == "__main__":
    unittest.main()
