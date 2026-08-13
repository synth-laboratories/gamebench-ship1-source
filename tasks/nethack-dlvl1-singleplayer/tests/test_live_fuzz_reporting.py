from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.fuzz_nle_differential import (
    causal_level_dump,
    action_source_eligibility,
    comparison_eligibility,
    choose_terminal_probe_action,
    lane_report,
    live_level_dumps,
    inferred_input_mode,
    layered_transition_report,
    mismatch_class,
    mismatch_records,
    native_bootstrap_level_dump,
    native_bootstrap_negative_controls,
    native_bootstrap_comparison_summary,
    native_surface_for_terrain,
    observed_hero_underlay,
    visible_cell_layers,
)


class LiveFuzzReportingTests(unittest.TestCase):
    def test_native_door_bootstrap_uses_doormask_and_orientation(self) -> None:
        # rm.typ==DOOR with D_NODOOR is the open doorway cmap (floor dot),
        # while doormask/orientation select the four actual door glyphs.
        self.assertEqual((".", 2371), native_surface_for_terrain(22, 0, False))
        self.assertEqual(("+", 2375), native_surface_for_terrain(22, 4, False))
        self.assertEqual(("+", 2374), native_surface_for_terrain(22, 4, True))
        self.assertEqual(("|", 2373), native_surface_for_terrain(22, 2, False))
        self.assertEqual(("-", 2372), native_surface_for_terrain(22, 2, True))

    def test_native_bootstrap_freezes_reset_source_and_keeps_hidden_cells_unrendered(self) -> None:
        width, height = 79, 21
        chars = [[ord(" ")] * width for _ in range(height)]
        glyphs = [[2359] * width for _ in range(height)]
        colors = [[0] * width for _ in range(height)]
        chars[1][1], glyphs[1][1], colors[1][1] = ord("@"), 340, 15
        causal = {
            "schema": "gamebench.nethack.level_dump.v1",
            "terrain": [" "] * height,
            "glyphs": glyphs,
            "colors": colors,
            "seen": [[False] * width for _ in range(height)],
            "unseen": {"chars": chars, "glyphs": glyphs, "colors": colors},
            "hero": {"x": 1, "y": 1, "glyph": 340, "color": 15},
            "metadata": {}, "objects": [], "inventory": [], "monsters": [], "traps": [],
        }
        native = {
            "provenance": "read_only_hash_verified_live_nle_v0_9_0_macho_level_and_viz_array",
            "binary_sha256": "pinned",
            "coordinate_contract": "screen x maps to native x+1",
            "full_map_terrain": [[24] * width for _ in range(height)],
            "fov_visibility_mask": [[False] * width for _ in range(height)],
            "map_memory": {"glyph": [[2378] * width for _ in range(height)], "seenv": [[0] * width for _ in range(height)]},
            "plane_sha256": {},
        }

        class Glyphs:
            @staticmethod
            def glyph_is_cmap(_glyph: int) -> bool:
                return False

        initial = {"chars": chars, "glyphs": glyphs, "colors": colors, "blstats": [1, 1]}
        dump = native_bootstrap_level_dump(causal, initial, native, nethack=Glyphs())
        self.assertEqual(".", dump["terrain"][0][0])
        self.assertFalse(dump["seen"][0][0])
        task = {"task_id": "native-bootstrap-test", "seed": 1, "rules": {"max_steps": 0}, "level_dump": dump}
        controls = native_bootstrap_negative_controls(task, initial, native)
        self.assertEqual("pass", controls["status"])
        self.assertGreater(controls["reset_hidden_render_controls"], 1)

    def test_native_bootstrap_summary_requires_three_heldout_lane_traces(self) -> None:
        metric = {
            "strict_snapshot_v1": {"status": "diverged", "first_difference": {"step": 1, "path": "$.chars[0][0]"}},
            "first_divergent_step_census_v1": {"mismatch_count": 2},
            "visibility_entity_transition_oracle_v1": {"comparisons": 1, "error_count": 1, "unjudgeable_surface_record_count": 0},
            "lane": "python",
        }
        reports = [{"fixture_id": "a", "lanes": [metric], "native_reset_bootstrap_navigation_v1": [{"metrics": {"first_divergence_step": 1, "first_divergence_mismatch_count": 1, "visibility_errors": 0, "visibility_comparisons": 1, "visibility_unjudgeable_surface_records": 0}}]}]
        summary = native_bootstrap_comparison_summary(reports, heldout_fixture_ids={"a"})
        self.assertEqual("not_met", summary["promotion_gate"]["status"])
        self.assertEqual(1, summary["heldout"]["lane_traces"])

    def test_layered_transition_reports_static_visibility_and_vacated_restoration(self) -> None:
        expected = [
            {"chars": [".d"], "glyphs": [[2371, 301]], "colors": [[7, 6]]},
            {"chars": [".."], "glyphs": [[2371, 2371]], "colors": [[7, 7]]},
        ]
        actual = [
            {"chars": [".d"], "glyphs": [[2371, 301]], "colors": [[7, 6]]},
            {"chars": [".d"], "glyphs": [[2371, 301]], "colors": [[7, 6]]},
        ]

        report = layered_transition_report(expected, actual)

        self.assertEqual(1, report["comparisons"])
        self.assertEqual("errors_found", report["status"])
        transition = report["transitions"][0]
        self.assertEqual(
            [{"x": 1, "y": 0, "char": "d", "glyph": 301, "color": 6, "provenance": "observed_surface_overlay", "identity_status": "unavailable_from_nle_presentation", "underlay_provenance": "unknown"}],
            transition["entities"]["disappeared"],
        )
        self.assertEqual(1, len(transition["entities"]["vacated_cell_restoration"]))
        self.assertEqual(1, len(transition["static"]["missed_current"]))
        self.assertEqual("$.visibility_entity.static.current.missed", report["first_error"]["path"])

    def test_layered_transition_marks_motion_as_presentation_only(self) -> None:
        expected = [
            {"chars": [".d."], "glyphs": [[2371, 301, 2371]], "colors": [[7, 6, 7]]},
            {"chars": ["..d"], "glyphs": [[2371, 2371, 301]], "colors": [[7, 7, 6]]},
        ]

        report = layered_transition_report(expected, expected)

        transition = report["transitions"][0]
        self.assertEqual("pass", report["status"])
        self.assertEqual("presentation_continuity_only", transition["entities"]["moved"][0]["identity_status"])
        self.assertIn("do not provide stable entity ids", transition["identity_limits"]["note"])

    def test_visibility_quarantines_later_reset_hero_underlay_instead_of_scoring_it_as_fov(self) -> None:
        expected = [
            {"chars": ["@"], "glyphs": [[340]], "colors": [[15]]},
            {"chars": ["<"], "glyphs": [[2382]], "colors": [[7]]},
        ]
        actual = [
            {"chars": ["@"], "glyphs": [[340]], "colors": [[15]]},
            {"chars": [" "], "glyphs": [[2359]], "colors": [[0]]},
        ]

        report = layered_transition_report(
            expected,
            actual,
            reset_level={"hero": {"x": 0, "y": 0}, "terrain": [" "], "seen": [[True]]},
        )

        self.assertEqual("partial_unjudgeable", report["status"])
        self.assertEqual(0, report["error_count"])
        self.assertEqual(2, report["unjudgeable_surface_record_count"])
        self.assertEqual([{"x": 0, "y": 0, "source_state": "reset_hero_underlay_unknown"}], report["causal_unknown_coordinates"])
        self.assertEqual("reset_hero_underlay_unknown", report["source_state_limits"][0]["source_state"])

    def test_visibility_quarantines_expired_reset_overlay_underlay(self) -> None:
        expected = [
            {"chars": ["d"], "glyphs": [[413]], "colors": [[15]]},
            {"chars": ["."], "glyphs": [[2371]], "colors": [[7]]},
        ]
        actual = [
            {"chars": ["d"], "glyphs": [[413]], "colors": [[15]]},
            {"chars": [" "], "glyphs": [[2359]], "colors": [[0]]},
        ]
        overlay = {
            "x": 0, "y": 0, "char": "d", "glyph": 413, "color": 15,
            "provenance": "nle_reset_presentation", "presentation_class": "pet_presentation",
            "identity_status": "unavailable_from_nle_presentation",
        }

        report = layered_transition_report(
            expected,
            actual,
            reset_level={"hero": {"x": 1, "y": 0}, "terrain": ["  "], "seen": [[True, True]], "presentation_overlays": [overlay]},
        )

        self.assertEqual(0, report["error_count"])
        self.assertTrue(any(entry["source_state"] == "reset_presentation_overlay_underlay_unknown" for entry in report["source_state_limits"]))

    def test_layered_transition_distinguishes_reveal_retain_and_forget(self) -> None:
        expected = [
            {"chars": [" ."], "glyphs": [[2359, 2371]], "colors": [[0, 7]]},
            {"chars": [".."], "glyphs": [[2371, 2371]], "colors": [[7, 7]]},
            {"chars": [" ."], "glyphs": [[2359, 2371]], "colors": [[0, 7]]},
        ]

        report = layered_transition_report(expected, expected)

        self.assertEqual("pass", report["status"])
        self.assertEqual([{"x": 0, "y": 0, "char": ".", "glyph": 2371, "color": 7, "provenance": "observed_surface_static"}], report["transitions"][0]["static"]["newly_revealed"])
        self.assertEqual([{"x": 0, "y": 0, "char": ".", "glyph": 2371, "color": 7, "provenance": "observed_surface_static"}], report["transitions"][1]["static"]["forgotten"])

    def test_visible_layers_expose_reset_underlay_provenance_without_guessing_identity(self) -> None:
        layers = visible_cell_layers(
            {"chars": ["@d"], "glyphs": [[340, 301]], "colors": [[15, 6]]},
            reset_level={"terrain": [".."], "seen": [[True, True]]},
        )

        self.assertEqual("reset_observed_static", layers["unknown"][0]["underlay_provenance"])
        self.assertEqual("reset_observed_static", layers["overlays"][(1, 0)]["underlay_provenance"])
        self.assertEqual("unavailable_from_nle_presentation", layers["overlays"][(1, 0)]["identity_status"])

    def test_inventory_end_page_is_recovered_as_a_display_mode(self) -> None:
        class Rows:
            def tolist(self) -> list[list[int]]:
                line = "                               (end)".ljust(80)
                return [[ord(character) for character in line]]

        self.assertEqual("inventory_display", inferred_input_mode({"tty_chars": Rows(), "message": []}))

    def test_causal_level_dump_never_hydrates_reset_with_future_observations(self) -> None:
        """A live case may retain a future tape, but its reset starts source-causal."""

        reset = {
            "chars": [[ord("@"), ord(" ")]],
            "glyphs": [[340, 2359]],
            "colors": [[15, 0]],
            "blstats": [0, 0],
            "message": [],
            "inv_letters": [],
            "inv_glyphs": [],
            "inv_oclasses": [],
            "inv_strs": [],
        }

        dump = causal_level_dump(reset, {}, unseen_glyph=2359)

        self.assertEqual(" ", dump["terrain"][0][1])
        self.assertFalse(dump["seen"][0][1])
        self.assertEqual(ord(" "), dump["unseen"]["chars"][0][1])

    def test_hero_underlay_is_limited_to_static_terrain_at_the_reset_hero_cell(self) -> None:
        reset = {
            "chars": [[ord("@"), ord(" ")]],
            "glyphs": [[340, 2359]],
            "colors": [[15, 0]],
            "blstats": [0, 0],
        }
        exposed = {
            "chars": [[ord("<"), ord(".")]],
            "glyphs": [[2382, 2371]],
            "colors": [[7, 7]],
            "blstats": [1, 0],
        }

        self.assertEqual(
            [{"x": 0, "y": 0, "char": "<", "glyph": 2382, "color": 7}],
            observed_hero_underlay(reset, [reset, exposed], unseen_glyph=2359),
        )

        annotated, heldout = live_level_dumps(reset, {}, [reset, exposed], unseen_glyph=2359)
        # A post-action exposure is diagnostic evidence, not reset state.
        self.assertEqual(annotated, heldout)

    def test_future_reveal_cannot_make_the_current_pickup_judgeable(self) -> None:
        reset = {
            "chars": [[ord("@")]],
            "glyphs": [[340]],
            "colors": [[15]],
            "blstats": [0, 0],
        }
        future = {
            "chars": [[ord("<")]],
            "glyphs": [[2382]],
            "colors": [[7]],
            "blstats": [1, 0],
        }

        eligibility = action_source_eligibility(
            "Command.PICKUP", [reset, future], step=1, unseen_glyph=2359
        )

        self.assertEqual("unjudgeable", eligibility["status"])
        self.assertEqual("unknown", eligibility["requirements"][0]["provenance"])
        self.assertEqual("hero_cell_occluded", eligibility["requirements"][0]["reason"])

    def test_explicit_capture_annotations_can_supply_all_pickup_preconditions(self) -> None:
        reset = {
            "chars": [[ord("@")]],
            "glyphs": [[340]],
            "colors": [[15]],
            "blstats": [0, 0],
        }
        eligibility = action_source_eligibility(
            "Command.PICKUP",
            [reset],
            step=1,
            unseen_glyph=2359,
            source_annotations={
                "terrain_underlay": [{"x": 0, "y": 0, "char": "<"}],
                "floor_objects": [{"x": 0, "y": 0, "objects": []}],
            },
        )

        self.assertEqual("eligible", eligibility["status"])
        self.assertEqual(
            ["capture-annotation", "capture-annotation"],
            [entry["provenance"] for entry in eligibility["requirements"]],
        )

    def test_unjudgeable_action_is_not_reported_as_equal_or_diverged(self) -> None:
        expected = [
            {"chars": ["@"], "blstats": [0, 0], "done": False},
            {"chars": ["<"], "blstats": [0, 0], "done": False},
        ]
        actual = [
            {"chars": ["@"], "blstats": [0, 0], "done": False},
            {"chars": ["."], "blstats": [0, 0], "done": False},
        ]
        actions = [{"action_name": "Command.PICKUP", "source_state_eligibility": {"status": "unjudgeable", "requirements": [{"key": "hero_terrain_underlay", "provenance": "unknown"}]}}]

        report = lane_report("python", expected, actual, actions, strict_baseline=True)

        self.assertEqual("unjudgeable", report["strict_snapshot_v1"]["status"])
        self.assertIsNone(report["strict_snapshot_v1"]["first_difference"])
        self.assertEqual(0, report["source_state_eligibility_v1"]["judgeable_action_steps"])
        self.assertEqual(1, report["source_state_eligibility_v1"]["unjudgeable_action_steps"])
        self.assertEqual([], report["first_divergent_step_census_v1"]["mismatches"])

    def test_one_unknown_transition_taints_later_action_comparisons(self) -> None:
        report = comparison_eligibility(
            [
                {"action_name": "Command.PICKUP", "source_state_eligibility": {"status": "unjudgeable", "requirements": []}},
                {"action_name": "CompassDirection.E", "source_state_eligibility": {"status": "eligible", "requirements": []}},
            ]
        )
        self.assertEqual(1, report["first_unjudgeable_step"])
        self.assertEqual(["unknown_required_source_state", "prior_unjudgeable_transition"], [step["reason"] for step in report["steps"]])

    def test_invalid_or_future_provenance_fails_hard(self) -> None:
        with self.assertRaisesRegex(AssertionError, "unsupported source-state provenance"):
            comparison_eligibility(
                [
                    {
                        "action_name": "Command.PICKUP",
                        "source_state_eligibility": {
                            "status": "eligible",
                            "requirements": [{"key": "hero_terrain_underlay", "provenance": "future-observed"}],
                        },
                    }
                ]
            )

    def test_mismatch_records_enumerates_character_cells_and_state_leaves(self) -> None:
        expected = {
            "chars": ["abc", "def"],
            "blstats": [1, 2],
            "message": "oracle",
        }
        actual = {
            "chars": ["axc", "dez"],
            "blstats": [1, 3],
            "message": "gold",
        }

        records = list(mismatch_records(expected, actual))

        self.assertEqual(
            [
                "$.chars[0][1]",
                "$.chars[1][2]",
                "$.blstats[1]",
                "$.message",
            ],
            [record["path"] for record in records],
        )

    def test_terminal_character_rows_are_counted_per_cell(self) -> None:
        records = list(
            mismatch_records(
                {"char_rows": ["abc"]},
                {"char_rows": ["axz"]},
                path="$.terminal_ui",
            )
        )

        self.assertEqual(
            ["$.terminal_ui.char_rows[0][1]", "$.terminal_ui.char_rows[0][2]"],
            [record["path"] for record in records],
        )

    def test_mismatch_classes_keep_terminal_pixels_separate_from_state(self) -> None:
        self.assertEqual("pixel", mismatch_class("$.terminal_ui.char_rows[0][4]"))
        self.assertEqual("pixel", mismatch_class("$.glyphs[1][2]"))
        self.assertEqual("special", mismatch_class("$.specials[1][2]"))
        self.assertEqual("mode", mismatch_class("$.input_mode.kind"))
        self.assertEqual("turn", mismatch_class("$.turn_effect.time_delta"))
        self.assertEqual("state", mismatch_class("$.blstats[4]"))

    def test_lane_report_census_is_only_the_first_divergent_step(self) -> None:
        expected = [
            {"chars": ["abc"], "blstats": [1], "done": False},
            {"chars": ["abc"], "blstats": [2], "done": False},
            {"chars": ["abc"], "blstats": [3], "done": False},
        ]
        actual = [
            {"chars": ["abc"], "blstats": [1], "done": False},
            {"chars": ["axc"], "blstats": [9], "done": False},
            {"chars": ["zzz"], "blstats": [99], "done": False},
        ]
        actions = [
            {"action_id": 1, "action_name": "one"},
            {"action_id": 2, "action_name": "two"},
        ]

        report = lane_report(
            "python",
            expected,
            actual,
            actions,
            strict_baseline=True,
        )
        census = report["first_divergent_step_census_v1"]

        self.assertEqual(1, census["step"])
        self.assertEqual(2, census["mismatch_count"])
        self.assertEqual({"pixel": 1, "state": 1}, census["counts_by_class"])
        self.assertEqual(
            ["$.chars[0][1]", "$.blstats[0]"],
            [record["path"] for record in census["mismatches"]],
        )
        self.assertNotIn("$.chars[0][0]", [record["path"] for record in census["mismatches"]])

    def test_lane_report_with_no_oracle_metadata_marks_extended_checks_unexercised(self) -> None:
        snapshots = [{"chars": ["abc"], "blstats": [1], "done": False}]
        report = lane_report("rust", snapshots, snapshots, [], strict_baseline=True)

        for contract in (
            "prompt_mode_oracle_v1",
            "turn_consumption_oracle_v1",
            "terminal_ui_oracle_v1",
            "specials_oracle_v1",
            "terminal_boundary_oracle_v1",
        ):
            self.assertEqual("not_exercised", report[contract]["status"])

    def test_sparse_specials_gap_does_not_truncate_other_oracle_layers(self) -> None:
        expected = [{"chars": ["d"], "blstats": [1], "specials": [[8]], "done": False}]
        actual = [{"chars": ["d"], "blstats": [1], "specials": [[0]], "done": False}]

        report = lane_report("python", expected, actual, [], strict_baseline=True)

        self.assertEqual("equal", report["strict_snapshot_v1"]["status"])
        self.assertEqual("partially_unjudgeable", report["specials_oracle_v1"]["status"])
        self.assertEqual(1, report["specials_oracle_v1"]["unmaterialized_pet_cells"])

    def test_core_equality_masks_only_source_unknown_reset_overlay_coordinate(self) -> None:
        expected = [{"chars": ["d."], "glyphs": [[397, 2371]], "colors": [[15, 7]], "blstats": [1], "done": False}]
        actual = [{"chars": [" x"], "glyphs": [[2359, 999]], "colors": [[0, 1]], "blstats": [1], "done": False}]
        reset_level = {
            "presentation_overlays": [{"x": 0, "y": 0}],
            "hero": {"x": 1, "y": 0},
            "terrain": [" ."],
        }

        report = lane_report("python", expected, actual, [], strict_baseline=True, reset_level=reset_level)

        self.assertEqual("$.chars[0][1]", report["strict_snapshot_v1"]["first_difference"]["path"])
        self.assertEqual([{"x": 0, "y": 0}], report["strict_snapshot_v1"]["source_unknown_surface_coordinates"])

    def test_terminal_boundary_is_checked_after_an_earlier_semantic_difference(self) -> None:
        expected = [
            {"message": "", "done": False, "terminal_reason": ""},
            {"message": "NLE prompt", "done": False, "terminal_reason": ""},
            {"message": "", "done": True, "terminal_reason": "nle_done_unknown"},
        ]
        actual = [
            {"message": "", "done": False, "terminal_reason": ""},
            {"message": "gold prompt", "done": False, "terminal_reason": ""},
            {"message": "", "done": False, "terminal_reason": ""},
        ]

        report = lane_report("python", expected, actual, [{}, {}], strict_baseline=True)

        terminal = report["terminal_boundary_oracle_v1"]
        self.assertEqual(1, terminal["comparisons"])
        self.assertEqual("errors_found", terminal["status"])
        self.assertEqual("$.terminal.done", terminal["errors"][0]["path"])

    def test_terminal_campaign_uses_quit_then_raw_yes(self) -> None:
        table = [
            [7, "CompassDirection.NW", 121],
            [19, "MiscAction.MORE", 13],
            [38, "Command.ESC", 27],
            [65, "Command.QUIT", 241],
        ]
        with patch("scripts.fuzz_nle_differential.inferred_input_mode", return_value="normal"):
            normal = choose_terminal_probe_action({}, table, __import__("random").Random(0))
        with patch("scripts.fuzz_nle_differential.inferred_input_mode", return_value="ynq"):
            confirmed = choose_terminal_probe_action({}, table, __import__("random").Random(0))
        self.assertEqual((65, "terminal_quit", [65]), normal)
        self.assertEqual((7, "terminal_confirm_yes", [7]), confirmed)


if __name__ == "__main__":
    unittest.main()
