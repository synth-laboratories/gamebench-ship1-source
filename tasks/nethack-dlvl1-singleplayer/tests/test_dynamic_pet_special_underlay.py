"""Regression guard for stale MG_PET specials after a promoted pet moves."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine


class _Scheduler:
    entities = [
        {
            "entity_id": 7,
            "species_id": 32,
            "allegiance": "tame",
            "lifecycle": "alive",
            "x": 28,
            "y": 6,
        }
    ]


class DynamicPetSpecialUnderlayTests(unittest.TestCase):
    def test_sync_moves_pet_overlay_instead_of_first_reset_overlay(self) -> None:
        engine = NethackDlvl1Engine.__new__(NethackDlvl1Engine)
        engine._scheduler = _Scheduler()
        engine.state = {
            "reset_floor_objects": [],
            "reset_floor_objects_enabled": False,
            "presentation_overlays": [
                {
                    "presentation_class": "normal_monster_presentation",
                    "x": 28,
                    "y": 5,
                    "special": 0,
                },
                {
                    "presentation_class": "pet_presentation",
                    "x": 28,
                    "y": 7,
                    "special": 8,
                },
            ],
            "pet_interaction_markers": [
                {
                    "id": "pet",
                    "name": "kitten",
                    "position": {"x": 28, "y": 7},
                    "x": 28,
                    "y": 7,
                    "pet": True,
                }
            ],
            "safe_pet_runtime": [{"position": {"x": 28, "y": 7}}],
            "seen": [[True] * 79 for _ in range(21)],
            "monsters": [],
            "dynamic_pet_runtime_enabled": False,
        }

        engine._sync_dynamic_pet_presentation()

        self.assertEqual((28, 5), (engine.state["presentation_overlays"][0]["x"], engine.state["presentation_overlays"][0]["y"]))
        self.assertEqual((28, 6), (engine.state["presentation_overlays"][1]["x"], engine.state["presentation_overlays"][1]["y"]))
        position = engine.state["pet_interaction_markers"][0]["position"]
        self.assertEqual((28, 6), (position["x"], position["y"]))
        specials = engine._render_specials()
        self.assertEqual([0, 8], [specials[7][28], specials[6][28]])

    def test_lichen_corpse_uses_source_body_glyph(self) -> None:
        engine = NethackDlvl1Engine.__new__(NethackDlvl1Engine)
        engine.state = {
            "authoritative_scheduler_runtime": {
                "dynamic_object_stacks": [{
                    "id": "dynamic-corpse-8",
                    "x": 29,
                    "y": 6,
                    "objects": [{
                        "object_id": 30,
                        "object_type": 240,
                        "quantity": 1,
                        "display_mode": "normal",
                        "display_object_type": 240,
                        "display_glyph": 1299,
                        "display_class": 7,
                        "display_color": 10,
                        "corpsenm": 155,
                        "source_order": -1,
                    }],
                }],
            },
        }
        projected = engine._dynamic_floor_objects()
        self.assertEqual(1, len(projected))
        self.assertEqual(1299, projected[0]["glyph"])
        self.assertEqual("%", projected[0]["kind"])


if __name__ == "__main__":
    unittest.main()
