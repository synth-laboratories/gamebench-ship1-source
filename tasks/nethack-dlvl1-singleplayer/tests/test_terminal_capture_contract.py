from __future__ import annotations

import unittest

from scripts.capture_nle_fixture import terminal_reason_for_capture
from gold_python.engine import NethackDlvl1Engine
from shared.task_resolve import resolve_task
import json
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]


def _reset_map_with_stair(*, terrain_type: int, flags: int) -> dict[str, object]:
    terrain = [[24 for _ in range(79)] for _ in range(21)]
    flag_plane = [[0 for _ in range(79)] for _ in range(21)]
    horizontal = [[False for _ in range(79)] for _ in range(21)]
    terrain[2][4] = terrain_type
    flag_plane[2][4] = flags
    return {
        "terrain_type": terrain,
        "terrain_flags": flag_plane,
        "terrain_horizontal": horizontal,
    }


class TerminalCaptureContractTests(unittest.TestCase):
    def test_live_snapshots_are_not_terminal(self) -> None:
        self.assertEqual("", terminal_reason_for_capture(done=False, pending_operation="quit"))

    def test_confirmed_prompt_operation_is_preserved_after_nle_clears_blstats(self) -> None:
        self.assertEqual("quit", terminal_reason_for_capture(done=True, pending_operation="quit"))
        self.assertEqual("saved", terminal_reason_for_capture(done=True, pending_operation="save"))

    def test_unprompted_done_is_death(self) -> None:
        self.assertEqual("death", terminal_reason_for_capture(done=True, pending_operation=""))

    def test_source_reset_map_down_stair_owns_descent_over_rendered_tile(self) -> None:
        entry = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "bootstrap_descend.json").read_text())
        task = {key: value for key, value in entry.items() if key not in {"actions", "expected", "required_nev_kinds"}}
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.state["hero"]["x"], engine.state["hero"]["y"] = 4, 2
        # The public terrain is deliberately not a stair; the immutable
        # source rm.typ/rm.flags receipt is authoritative for doup().
        engine.state["terrain"][2][4] = "."
        engine.state["authoritative_reset_map"] = _reset_map_with_stair(terrain_type=25, flags=2)
        result = engine.step("MiscDirection.DOWN")
        self.assertTrue(result["terminated"])
        self.assertEqual("descended", result["public"]["terminal_reason"])

    def test_source_reset_map_up_stair_rejects_rendered_down_glyph(self) -> None:
        entry = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "bootstrap_descend.json").read_text())
        task = {key: value for key, value in entry.items() if key not in {"actions", "expected", "required_nev_kinds"}}
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.state["hero"]["x"], engine.state["hero"]["y"] = 4, 2
        engine.state["terrain"][2][4] = ">"
        engine.state["authoritative_reset_map"] = _reset_map_with_stair(terrain_type=25, flags=0)
        result = engine.step("MiscDirection.DOWN")
        self.assertFalse(result["terminated"])
        self.assertEqual("You can't go down here.", result["public"]["message"])


if __name__ == "__main__":
    unittest.main()
