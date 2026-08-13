from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.verify_entity_overlay_restoration import restoration_report


def source_transition(*, x: int, y: int, restored: str = ".") -> dict[str, object]:
    overlay = {"x": x, "y": y, "char": "f", "glyph": 413, "color": 15}
    return {
        "step": 2,
        "entities": {
            "moved": [
                {
                    "from": overlay,
                    "to": {**overlay, "x": x + 1},
                    "identity_status": "presentation_continuity_only",
                }
            ],
            "vacated_cell_restoration": [
                {
                    "vacated": overlay,
                    "restored_static": {"x": x, "y": y, "char": restored, "glyph": 2378, "color": 7, "provenance": "observed_surface_static"},
                }
            ],
        },
    }


class EntityOverlayRestorationTests(unittest.TestCase):
    def test_three_source_cases_establish_visible_vacated_static_restoration(self) -> None:
        run = {
            "reports": [
                {"fixture_id": f"fuzz-case-{seed}", "lanes": [{"visibility_entity_transition_oracle_v1": {"transitions": [source_transition(x=index, y=4)]}}]}
                for index, seed in enumerate((101, 102, 103))
            ]
        }

        report = restoration_report(run)

        self.assertEqual("pass", report["status"])
        self.assertEqual(3, report["distinct_source_cases"])
        self.assertEqual(3, len(report["visible_vacated_restorations"]))
        self.assertIn("no entity identity", report["identity_claim"])

    def test_nonvisible_vacating_motion_is_reported_not_called_a_restoration_failure(self) -> None:
        transition = source_transition(x=3, y=2)
        transition["entities"]["vacated_cell_restoration"] = []  # type: ignore[index]
        run = {"reports": [{"fixture_id": "fuzz-case-101", "lanes": [{"visibility_entity_transition_oracle_v1": {"transitions": [transition]}}]}]}

        report = restoration_report(run, min_distinct_seeds=1)

        self.assertEqual("insufficient_source_evidence", report["status"])
        self.assertEqual(1, len(report["not_visible_after_presentation_motion"]))


if __name__ == "__main__":
    unittest.main()
