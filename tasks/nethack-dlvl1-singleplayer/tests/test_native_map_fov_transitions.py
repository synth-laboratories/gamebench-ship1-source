"""Unit coverage for source-only native map/FOV transition classification."""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from inspect import signature, getsource
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.nle_native_map_fov import OBS_COLNO, PINNED_BINARY_SHA256, ROWNO
from scripts.verify_native_map_fov_transitions import (
    GATE_SCHEMA,
    SCHEMA,
    audit,
    capture_case,
    classify_transition,
    public_render_summary,
)


def plane(value: object) -> list[list[object]]:
    return [[value for _ in range(OBS_COLNO)] for _ in range(ROWNO)]


def native_export(*, visible: bool = False, could: bool = False, memory_glyph: int = 2378, seenv: int = 0, flags: int = 0, horizontal: bool = False) -> dict:
    return {
        "schema": "gamebench.nethack.native_map_fov_snapshot.v1",
        "provenance": "read_only_hash_verified_live_nle_v0_9_0_macho_level_and_viz_array",
        "binary_sha256": PINNED_BINARY_SHA256,
        "full_map_terrain": plane(24),
        "full_map_terrain_flags": plane(flags),
        "full_map_terrain_horizontal": plane(horizontal),
        "fov_visibility_mask": plane(visible),
        "fov_could_see_mask": plane(could),
        "map_memory": {"glyph": plane(memory_glyph), "seenv": plane(seenv)},
    }


def public(*, char: str = " ", glyph: int = 2359, hero: tuple[int, int] = (1, 1)) -> dict:
    chars, glyphs, colors = plane(ord(char)), plane(glyph), plane(0)
    chars[hero[1]][hero[0]], glyphs[hero[1]][hero[0]], colors[hero[1]][hero[0]] = ord("@"), 340, 15
    return {"chars": chars, "glyphs": glyphs, "colors": colors, "blstats": [hero[0], hero[1]]}


class Glyphs:
    @staticmethod
    def glyph_is_cmap(glyph: int) -> bool:
        return 2300 <= glyph < 2400


class NativeMapFovTransitionTests(unittest.TestCase):
    def test_visibility_memory_rendering_and_overlays_are_separate(self) -> None:
        before = native_export(visible=False, could=True, memory_glyph=2378, seenv=0)
        after = native_export(visible=True, could=True, memory_glyph=2378, seenv=1)
        before_public = public(char=" ", glyph=2359)
        after_public = public(char=".", glyph=2378)
        before_summary = public_render_summary(before_public, Glyphs.glyph_is_cmap)
        after_summary = public_render_summary(after_public, Glyphs.glyph_is_cmap)

        result = classify_transition(before, after, before_summary, after_summary)

        self.assertEqual(0, result["terrain"]["true_type_changed"])
        self.assertEqual(OBS_COLNO * ROWNO, result["visibility"]["in_sight_gained"])
        self.assertEqual(OBS_COLNO * ROWNO, result["memory"]["seenv_changed"])
        self.assertEqual(0, result["rendering"]["before_direct_static_controls"])
        self.assertEqual(OBS_COLNO * ROWNO - 1, result["rendering"]["after_direct_static_controls"])
        self.assertFalse(result["overlays"]["underlay_or_entity_identity_inferred"])

    def test_adversarial_overlay_is_not_terrain_or_memory_control(self) -> None:
        before = native_export(visible=True, could=True, memory_glyph=2378, seenv=1)
        after = deepcopy(before)
        overlay = public(char="d", glyph=340)
        summary = public_render_summary(overlay, Glyphs.glyph_is_cmap)
        result = classify_transition(before, after, summary, summary)

        self.assertEqual(0, summary["direct_static_count"])
        self.assertEqual(OBS_COLNO * ROWNO - 1, summary["presentation_overlay_count"])
        self.assertEqual([], result["source_assertion_errors"])
        self.assertFalse(result["overlays"]["underlay_or_entity_identity_inferred"])

    def test_static_cmap_mismatch_fails_but_blank_cmap_does_not_become_floor(self) -> None:
        export = native_export(visible=True, could=True, memory_glyph=2378, seenv=1)
        static = public(char=".", glyph=2379)
        blank = public(char=" ", glyph=2359)
        failed = classify_transition(export, export, public_render_summary(static, Glyphs.glyph_is_cmap), public_render_summary(static, Glyphs.glyph_is_cmap))
        blank_result = classify_transition(export, export, public_render_summary(blank, Glyphs.glyph_is_cmap), public_render_summary(blank, Glyphs.glyph_is_cmap))

        self.assertIn("direct_static_public_memory_glyph_mismatch", failed["source_assertion_errors"])
        self.assertEqual([], blank_result["source_assertion_errors"])

    def test_seenv_clear_fails_but_xray_compatible_in_sight_without_could_is_recorded(self) -> None:
        before = native_export(visible=True, could=True, seenv=1)
        after = native_export(visible=True, could=False, seenv=0)
        summary = public_render_summary(public(char=" "), Glyphs.glyph_is_cmap)
        result = classify_transition(before, after, summary, summary)

        # src/vision.c:618-657 can OR IN_SIGHT for x-ray vision without also
        # setting COULD_SEE.  Preserve the fact without treating source
        # evidence as malformed.
        self.assertEqual(OBS_COLNO * ROWNO, result["visibility"]["in_sight_without_could_after"])
        self.assertNotIn("in_sight_not_subset_of_could_see", result["source_assertion_errors"])
        self.assertIn("seenv_bit_cleared", result["source_assertion_errors"])

    def test_open_and_closed_door_glyphs_control_native_doormask_not_raw_type(self) -> None:
        closed = native_export(visible=True, could=True, memory_glyph=2375, flags=4, horizontal=False)
        opened = native_export(visible=True, could=True, memory_glyph=2373, flags=2, horizontal=True)
        for export in (closed, opened):
            export["full_map_terrain"][0][0] = 22
        closed_public = public(char="+", glyph=2375)
        opened_public = public(char="|", glyph=2373)
        # Leave the hero elsewhere so the controlled door pixel is visible.
        result = classify_transition(
            closed,
            opened,
            public_render_summary(closed_public, Glyphs.glyph_is_cmap),
            public_render_summary(opened_public, Glyphs.glyph_is_cmap),
        )

        self.assertEqual(0, result["terrain"]["true_type_changed"])
        self.assertEqual(1, result["terrain"]["door_mask_changed"])
        self.assertEqual(1, result["rendering"]["before_closed_door_controls"])
        self.assertEqual(1, result["rendering"]["after_open_door_controls"])
        self.assertEqual([], result["source_assertion_errors"])

        wrong_orientation = deepcopy(opened)
        wrong_orientation["full_map_terrain_horizontal"][0][0] = False
        rejected = classify_transition(
            closed,
            wrong_orientation,
            public_render_summary(closed_public, Glyphs.glyph_is_cmap),
            public_render_summary(opened_public, Glyphs.glyph_is_cmap),
        )
        self.assertIn("direct_public_door_glyph_doormask_mismatch", rejected["source_assertion_errors"])

    def test_classifier_has_no_seed_or_coordinate_lookup_input(self) -> None:
        before = native_export(visible=False, could=False)
        after = native_export(visible=False, could=False)
        before["fov_visibility_mask"][0][0] = True
        before["fov_could_see_mask"][0][0] = True
        after["fov_visibility_mask"][ROWNO - 1][OBS_COLNO - 1] = True
        after["fov_could_see_mask"][ROWNO - 1][OBS_COLNO - 1] = True
        summary = public_render_summary(public(char=" "), Glyphs.glyph_is_cmap)
        result = classify_transition(before, after, summary, summary)

        self.assertEqual(1, result["visibility"]["in_sight_gained"])
        self.assertEqual(1, result["visibility"]["in_sight_lost"])
        self.assertEqual(
            {"before", "after", "before_public", "after_public"},
            set(signature(classify_transition).parameters),
        )

    def test_audit_cannot_hydrate_gold_reset_or_use_future_input(self) -> None:
        # The live collector can inspect both sides of a completed source
        # action, but neither its classifier nor its return contract accepts
        # a task/reset/gold object into which that later plane could leak.
        classifier_inputs = set(signature(classify_transition).parameters)
        self.assertFalse({"seed", "fixture_id", "reset", "level_dump", "gold_state"} & classifier_inputs)
        implementation = getsource(capture_case) + getsource(audit)
        self.assertNotIn("gold_python", implementation)
        self.assertNotIn("level_dump", implementation)
        self.assertNotIn("reconcile_source", implementation)

    def test_zero_comparison_audit_is_rejected_before_live_capture(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one action"):
            audit([1, 2, 3, 4, 5, 6], character="val-hum-fem-law", steps=0, bootstrap_run=None)

    def test_empty_seed_independent_action_plan_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "action plan"):
            audit([1, 2, 3, 4, 5, 6], character="val-hum-fem-law", steps=1, bootstrap_run=None, action_names=())

    def test_report_schema_carries_distinct_source_and_gold_eligibility(self) -> None:
        self.assertEqual("gamebench.nethack.native_map_fov_transition_audit.v1", SCHEMA)
        self.assertEqual("gamebench.nethack.frontier_promotion_gate.v1", GATE_SCHEMA)


if __name__ == "__main__":
    unittest.main()
