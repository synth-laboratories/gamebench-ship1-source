from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine, RESET_UNDERLAY_SURFACES
from scripts.fuzz_nle_differential import observed_entity_annotations
from shared.task_resolve import resolve_task


def overlay_task() -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    seen = [[False] * 79 for _ in range(21)]
    for x in range(3, 10):
        terrain[4][x] = "."
        seen[4][x] = True
    return {
        "task_id": "presentation-overlay-inert",
        "seed": 17,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 0},
        "level_dump": {
            "terrain": ["".join(row) for row in terrain],
            "hero": {"x": 5, "y": 4},
            "seen": seen,
            "presentation_overlays": [
                {
                    "x": 6,
                    "y": 4,
                    "char": "d",
                    "glyph": 413,
                    "color": 15,
                    "provenance": "nle_reset_presentation",
                    "presentation_class": "monster_presentation",
                    "identity_status": "unavailable_from_nle_presentation",
                }
            ],
        },
    }


class PresentationOverlayTests(unittest.TestCase):
    def test_source_reset_wait_has_nle_empty_message(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-wait-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("MiscDirection.WAIT")
        self.assertEqual("", engine.public_projection()["message"])

    def test_source_extended_command_uses_hash_prompt_and_clears_on_escape(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-extcmd-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.EXTCMD")
        self.assertEqual("#", engine.public_projection()["message"])
        self.assertEqual("string", engine.public_projection()["input_mode"]["kind"])
        engine.step("Command.ESC")
        self.assertEqual("", engine.public_projection()["message"])
        self.assertEqual("normal", engine.public_projection()["input_mode"]["kind"])

    def test_source_engrave_prompt_lists_weapon_letters_and_cancels(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-engrave-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.ENGRAVE")
        self.assertEqual("What do you want to write with? [- ab or ?*]", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("Never mind.", engine.public_projection()["message"])

    def test_source_drop_prompt_lists_all_inventory_letters(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-drop-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.DROP")
        self.assertEqual("What do you want to drop? [abcde or ?*]", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("Never mind.", engine.public_projection()["message"])

    def test_source_wear_without_another_armor_is_empty_cancel_path(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-wear-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.WEAR")
        self.assertEqual("You don't have anything else to wear.", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("", engine.public_projection()["message"])

    def test_source_puton_without_accessories_is_empty_cancel_path(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-puton-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.PUTON")
        self.assertEqual("You don't have anything else to put on.", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("", engine.public_projection()["message"])

    def test_source_takeoff_updates_ac_inventory_text_and_consumes_turn(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-takeoff-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        before = engine.public_projection()["blstats"][20]
        engine.step("Command.TAKEOFF")
        projection = engine.public_projection()
        self.assertEqual(before + 1, projection["blstats"][20])
        self.assertEqual(10, projection["blstats"][16])
        self.assertEqual("an uncursed +3 small shield", projection["inventory"]["inv_strs"][2])
        engine.step("Command.ESC")
        self.assertEqual("", engine.public_projection()["message"])

    def test_source_quaff_without_potion_is_empty_cancel_path(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-quaff-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.QUAFF")
        self.assertEqual("You don't have anything to drink.", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("", engine.public_projection()["message"])

    def test_source_read_without_scroll_is_empty_cancel_path(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-read-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.READ")
        self.assertEqual("You don't have anything to read.", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("", engine.public_projection()["message"])

    def test_source_fire_without_quiver_redirects_to_throw_prompt(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-fire-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.FIRE")
        self.assertEqual("You have no ammunition readied.", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("What do you want to throw? [ab or ?*]", engine.public_projection()["message"])

    def test_source_throw_prompt_lists_weapon_letters(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-throw-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.THROW")
        self.assertEqual("What do you want to throw? [ab or ?*]", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("Never mind.", engine.public_projection()["message"])

    def test_source_zap_without_wand_clears_on_escape(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-zap-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.ZAP")
        self.assertEqual("You don't have anything to zap.", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("", engine.public_projection()["message"])

    def test_source_quiver_prompt_excludes_current_weapon(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-quiver-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.QUIVER")
        self.assertEqual("What do you want to ready? [- b or ?*]", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("Never mind.", engine.public_projection()["message"])

    def test_source_remove_prompt_with_no_accessories(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-remove-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.REMOVE")
        self.assertEqual("What do you want to remove? [*]", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("Never mind.", engine.public_projection()["message"])

    def test_source_invoke_prompt_with_no_invokable_item(self) -> None:
        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-invoke-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        task = {
            "task_id": meta["fixture_id"],
            "seed": meta["seed"],
            "character": meta["character"],
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
            "level_dump": json.loads((fixture / "level_dump.json").read_text()),
        }
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step("Command.INVOKE")
        self.assertEqual("What do you want to invoke? [*]", engine.public_projection()["message"])
        engine.step("Command.ESC")
        self.assertEqual("Never mind.", engine.public_projection()["message"])

    def test_reset_entity_underlay_restores_only_pinned_static_surface(self) -> None:
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(overlay_task()))
        engine.state["terrain"][4][6] = " "
        engine.state["base_glyphs"][4][6] = 0
        engine.state["base_colors"][4][6] = 0
        engine._apply_reset_entity_underlays({"entities": [{"x": 6, "y": 4, "underlay": {"terrain_memory_glyph": 2378}}]})
        self.assertEqual((".", 2378, 7), (engine.state["terrain"][4][6], engine.state["base_glyphs"][4][6], engine.state["base_colors"][4][6]))

        engine.state["terrain"][4][7] = " "
        engine.state["base_glyphs"][4][7] = 0
        engine.state["base_colors"][4][7] = 0
        engine._apply_reset_entity_underlays({"entities": [{"x": 7, "y": 4, "underlay": {"terrain_memory_glyph": 9999}}]})
        self.assertEqual((" ", 0, 0), (engine.state["terrain"][4][7], engine.state["base_glyphs"][4][7], engine.state["base_colors"][4][7]))
        engine.state["terrain"][3][7] = " "
        engine.state["base_glyphs"][3][7] = 0
        engine.state["base_colors"][3][7] = 0
        engine._apply_reset_entity_underlays({"entities": [{"x": 7, "y": 3, "underlay": {"terrain_memory_glyph": 2378}}]})
        self.assertEqual((" ", 0, 0), (engine.state["terrain"][3][7], engine.state["base_glyphs"][3][7], engine.state["base_colors"][3][7]))
        self.assertEqual((".", 2378), RESET_UNDERLAY_SURFACES[2378])

    def test_blocked_movement_does_not_consume_a_turn_in_both_gold_lanes(self) -> None:
        """NLE's wall bump has zero time delta; it is not a scheduler tick."""

        terrain = [[" "] * 79 for _ in range(21)]
        seen = [[False] * 79 for _ in range(21)]
        for x, tile in ((2, "|"), (3, "."), (4, ".")):
            terrain[4][x] = tile
            seen[4][x] = True
        task = {
            "task_id": "blocked-move-no-turn",
            "seed": 19,
            "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 0},
            "level_dump": {
                "terrain": ["".join(row) for row in terrain],
                "seen": seen,
                "hero": {"x": 3, "y": 4},
                "metadata": {"nle_blstats": [3, 4] + [0] * 25},
            },
            "actions": ["CompassDirection.W"],
        }
        resolved = resolve_task(task)
        python = NethackDlvl1Engine()
        python.reset(resolved)
        before_time = python.public_projection()["blstats"][20]
        python.step("CompassDirection.W")
        self.assertEqual(before_time, python.public_projection()["blstats"][20])
        self.assertEqual([3, 4], python.public_projection()["blstats"][:2])

        rust_trace = subprocess.run(
            ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--", "--trace-stdin"],
            input=json.dumps(task),
            text=True,
            capture_output=True,
            check=True,
        )
        rust_snapshot = json.loads(rust_trace.stdout)["snapshots"][1]
        self.assertEqual(python.public_projection(), rust_snapshot)

    def test_live_annotation_does_not_invent_monsters_objects_or_pet_identity(self) -> None:
        annotation = observed_entity_annotations(
            {"chars": [[ord("@"), ord("d")]], "glyphs": [[340, 413]], "colors": [[15, 15]]}
        )

        self.assertEqual({"presentation_overlays"}, set(annotation))
        overlay = annotation["presentation_overlays"][0]
        self.assertEqual("unavailable_from_nle_presentation", overlay["identity_status"])
        self.assertNotIn("pet", overlay)
        self.assertNotIn("peaceful", overlay)

    def test_source_glyph_classification_beats_character_heuristics_and_excludes_hero(self) -> None:
        observation = {
            "chars": [[ord("@"), ord("d"), ord("+")]],
            "glyphs": [[340, 5607, 2252]],
            "colors": [[15, 7, 3]],
            "blstats": [0, 0],
        }
        with patch(
            "scripts.fuzz_nle_differential.glyph_presentation_class",
            side_effect=lambda glyph: {340: "normal_monster_presentation", 5607: "statue_presentation", 2252: "object_presentation"}[glyph],
        ):
            annotation = observed_entity_annotations(observation)

        overlays = annotation["presentation_overlays"]
        self.assertEqual([(1, "d", "statue_presentation"), (2, "+", "object_presentation")], [(item["x"], item["char"], item["presentation_class"]) for item in overlays])
        self.assertFalse(any(item["char"] == "@" for item in overlays))

    def test_overlay_is_rendered_but_has_no_collision_combat_or_pickup_semantics(self) -> None:
        task = overlay_task()
        resolved = resolve_task(task)
        python = NethackDlvl1Engine()
        python.reset(resolved)

        initial = python.public_projection()
        self.assertEqual("d", initial["chars"][4][6])
        self.assertEqual([], python.private_projection()["monsters"])
        self.assertEqual([], python.private_projection()["floor_items"])

        # The first consumed turn expires reset-only evidence rather than
        # letting it masquerade as a stationary source entity.
        python.step("CompassDirection.E")
        self.assertEqual([6, 4], python.public_projection()["blstats"][:2])
        self.assertEqual([], python.private_projection()["presentation_overlays"])
        python.step("CompassDirection.E")
        after = python.public_projection()
        self.assertEqual([7, 4], after["blstats"][:2])
        self.assertEqual(".", after["chars"][4][6])
        self.assertEqual([], python.private_projection()["monsters"])
        self.assertEqual([], python.private_projection()["floor_items"])

    def test_rust_and_python_keep_the_marker_inert_and_identical(self) -> None:
        task = overlay_task()
        resolved = resolve_task(task)
        python = NethackDlvl1Engine()
        python.reset(resolved)
        for action in ("CompassDirection.E", "CompassDirection.E"):
            python.step(action)
        completed = subprocess.run(
            ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--"],
            input=json.dumps({**task, "level_dump": resolved["level_dump"], "actions": ["CompassDirection.E", "CompassDirection.E"]}),
            text=True,
            capture_output=True,
            check=True,
        )
        rust = json.loads(completed.stdout)["readout"]
        self.assertEqual(python.symbolic_readout(), rust)

    def test_reset_pet_marker_survives_zero_turn_prompt_then_expires_with_checkpoint_parity(self) -> None:
        task = overlay_task()
        level = task["level_dump"]  # type: ignore[assignment]
        level["presentation_overlays"][0]["presentation_class"] = "pet_presentation"  # type: ignore[index]
        level["pet_interaction_markers"] = [{  # type: ignore[index]
            "id": "nle-reset-pet", "name": "little dog", "x": 6, "y": 4,
            "char": "d", "glyph": 413, "color": 15,
            "provenance": "nle_reset_pet_glyph", "identity_source": "glyph_to_mon_permonst",
        }]
        resolved = resolve_task(task)
        python = NethackDlvl1Engine()
        python.reset(resolved)
        self.assertEqual(8, python.public_projection()["specials"][4][6])

        python.step("Command.INVENTORY")  # display/message command: no turn
        self.assertEqual(8, python.public_projection()["specials"][4][6])
        checkpoint = python.checkpoint_bytes().decode("utf-8")

        python.step("CompassDirection.E")
        expected = python.symbolic_readout()
        self.assertEqual(0, expected["public"]["specials"][4][6])
        self.assertEqual([], expected["private"]["presentation_overlays"])
        self.assertEqual([], expected["private"]["pet_interaction_markers"])

        completed = subprocess.run(
            ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--", "--checkpoint-replay-stdin"],
            input=json.dumps({"checkpoint": checkpoint, "actions": ["CompassDirection.E"]}),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(expected["public"], json.loads(completed.stdout)["projection"]["public"])

    def test_source_pet_marker_has_one_stationary_search_hold_then_expires(self) -> None:
        """The hold is visual-only and bounded to the NLE-probed action family."""

        task = overlay_task()
        level = task["level_dump"]  # type: ignore[assignment]
        level["presentation_overlays"][0]["presentation_class"] = "pet_presentation"  # type: ignore[index]
        level["pet_interaction_markers"] = [{  # type: ignore[index]
            "id": "nle-reset-pet", "name": "little dog", "x": 6, "y": 4,
            "char": "d", "glyph": 413, "color": 15,
            "provenance": "nle_reset_pet_glyph", "identity_source": "glyph_to_mon_permonst",
        }]
        resolved = resolve_task(task)
        python = NethackDlvl1Engine()
        python.reset(resolved)

        python.step("Command.SEARCH")
        held = python.symbolic_readout()
        self.assertEqual("d", held["public"]["chars"][4][6])
        self.assertEqual(8, held["public"]["specials"][4][6])
        self.assertEqual([], held["private"]["monsters"])
        self.assertTrue(held["private"]["pet_interaction_markers"])

        rust_trace = subprocess.run(
            ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--", "--trace-stdin"],
            input=json.dumps({**task, "actions": ["Command.SEARCH"]}),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(held["public"], json.loads(rust_trace.stdout)["snapshots"][1])

        checkpoint = python.checkpoint_bytes().decode("utf-8")
        python.step("Command.SEARCH")
        expected = python.symbolic_readout()
        self.assertEqual(".", expected["public"]["chars"][4][6])
        self.assertEqual(0, expected["public"]["specials"][4][6])
        self.assertEqual([], expected["private"]["pet_interaction_markers"])

        completed = subprocess.run(
            ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--", "--checkpoint-replay-stdin"],
            input=json.dumps({"checkpoint": checkpoint, "actions": ["Command.SEARCH"]}),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(expected["public"], json.loads(completed.stdout)["projection"]["public"])

    def test_pet_hold_does_not_generalize_to_a_movement_turn(self) -> None:
        task = overlay_task()
        level = task["level_dump"]  # type: ignore[assignment]
        level["presentation_overlays"][0]["presentation_class"] = "pet_presentation"  # type: ignore[index]
        level["pet_interaction_markers"] = [{  # type: ignore[index]
            "id": "nle-reset-pet", "name": "little dog", "x": 6, "y": 4,
            "char": "d", "glyph": 413, "color": 15,
            "provenance": "nle_reset_pet_glyph", "identity_source": "glyph_to_mon_permonst",
        }]
        python = NethackDlvl1Engine()
        python.reset(resolve_task(task))
        python.step("CompassDirection.E")
        self.assertEqual([], python.private_projection()["pet_interaction_markers"])
        self.assertEqual([], python.private_projection()["presentation_overlays"])
        self.assertEqual("@", python.public_projection()["chars"][4][6])

    def test_semantic_fields_are_rejected(self) -> None:
        task = overlay_task()
        marker = task["level_dump"]["presentation_overlays"][0]  # type: ignore[index]
        marker["pet"] = True  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "unsupported semantic fields"):
            resolve_task(task)

    def test_terrain_looking_object_character_is_valid_when_glyph_classified(self) -> None:
        task = overlay_task()
        marker = task["level_dump"]["presentation_overlays"][0]  # type: ignore[index]
        marker.update({"char": "+", "glyph": 2252, "presentation_class": "object_presentation"})  # type: ignore[index]
        self.assertEqual("+", resolve_task(task)["level_dump"]["presentation_overlays"][0]["char"])


if __name__ == "__main__":
    unittest.main()
