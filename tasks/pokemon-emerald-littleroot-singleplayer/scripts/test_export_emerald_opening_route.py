#!/usr/bin/env python3
"""ROM-free tests for bounded opening replay candidate export."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).with_name("export_emerald_opening_route.py")
SPEC = importlib.util.spec_from_file_location("emerald_opening_export", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
EXPORT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EXPORT
SPEC.loader.exec_module(EXPORT)


class OpeningRouteExportTest(unittest.TestCase):
    def test_clock_index_exports_concrete_candidate_not_evidence(self) -> None:
        candidate = EXPORT.build_candidate(
            EXPORT.BEDROOM_CLOCK_TAPE_INDEX,
            EXPORT.BEDROOM_CLOCK_TAPE_INDEX + 2,
            "bedroom_idle", "clock", "new_home_clock_tv",
        )
        self.assertEqual("candidate_unvalidated", candidate["status"])
        self.assertEqual("new_home_clock_tv", candidate["coverage_segment"])
        self.assertEqual(EXPORT.BEDROOM_CLOCK_TAPE_INDEX, candidate["program"][0]["opening_flat_step"])
        self.assertTrue(all(set(step["buttons"]) <= EXPORT.BUTTONS for step in candidate["program"]))

    def test_invalid_interval_fails(self) -> None:
        with self.assertRaises(ValueError):
            EXPORT.concrete_steps(4, 4)


if __name__ == "__main__":
    unittest.main()
