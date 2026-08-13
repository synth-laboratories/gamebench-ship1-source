from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from gold_python.source_pager import (
    PINNED_BINARY_SHA256,
    PINNED_SOURCE_COMMIT,
    SOURCE_PAGER_SCHEMA,
    validate_source_pager_contract,
)
from shared.nle_specials import SOURCE_COMMIT
from shared.task_resolve import resolve_task


def captured_grid_bug_pager() -> dict[str, object]:
    page = "The kitten misses the grid bug.  The grid bug bites!  You get zapped!"
    return {
        "schema": SOURCE_PAGER_SCHEMA,
        "fixture_id": "fuzz-case-0006-seed-20260731",
        "source_commit": PINNED_SOURCE_COMMIT,
        "binary_sha256": PINNED_BINARY_SHA256,
        "trigger": {"step": 15, "action": "CompassDirection.SE"},
        "before": {
            "source_turn": 14,
            "nle_time": 14,
            "message": "The kitten misses the grid bug.",
            "queue": [27, 10],
        },
        "page": {"message": page, "tty_message": page + "--More--", "input_mode": "more", "source_state_sha256": "749e8b0a340371d5f423ff1c53a870c6a54ade58a28864e4934a66e49774e470"},
        "continuation": {
            "action": "MiscAction.MORE",
            "source_turn": 15,
            "nle_time": 15,
            "message": "The kitten bites the grid bug.  The grid bug is killed!",
            "queue": [27],
            "input_mode": "normal",
            "consumes_player_turn": False,
            "source_state_sha256": "e215f11678e326c7995d70bd40f1a5f283e3ef9aaa1dfda9023f4207ecc4dbd8",
        },
    }


class SourcePagerTests(unittest.TestCase):
    def test_mark_more_replays_deferred_movement_smudge_before_scheduler(self) -> None:
        class RecordingScheduler:
            def __init__(self) -> None:
                self.calls: list[tuple[object, ...]] = []

            def _rnd(self, bound: int) -> int:
                self.calls.append(("rnd", bound))
                return 1

            def _wipe_engraving_at(self, reset_map: dict, x: int, y: int, *, count: int) -> None:
                self.calls.append(("wipe", x, y, count))

        engine = NethackDlvl1Engine.__new__(NethackDlvl1Engine)
        scheduler = RecordingScheduler()
        engine._scheduler = scheduler
        engine.state = {
            "authoritative_reset_map": {
                "engravings": [{
                    "native_x": 10,
                    "y": 14,
                    "engr_type": 4,
                    "engr_time": 0,
                    "engr_lth": 2,
                    "text": "x",
                }],
            },
        }
        engine._resume_mark_movement_smudge({
            "smudge_from": {"x": 8, "y": 14},
            "smudge_to": {"x": 9, "y": 14},
        })
        self.assertEqual([("rnd", 5), ("wipe", 9, 14, 1)], scheduler.calls)

    def test_pager_source_identity_matches_shared_pinned_commit(self) -> None:
        self.assertEqual(PINNED_SOURCE_COMMIT, SOURCE_COMMIT)
        self.assertEqual(40, len(PINNED_SOURCE_COMMIT))

    def test_captured_more_continuation_is_exact_and_non_combat(self) -> None:
        contract = captured_grid_bug_pager()
        self.assertEqual(contract, validate_source_pager_contract(contract))
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task({"fixture_id": "val-east-seed-20260725", "seed": 20260725}))
        engine.state["time"] = 14
        engine.state["step_index"] = 14
        engine.state["message"] = "The kitten misses the grid bug."
        engine.state["message_raw"] = list(engine.state["message"].encode())
        hp_before = engine.state["hp"]
        rng_before = engine.state["rng"]
        engine.arm_source_pager(contract)
        self.assertEqual("more", engine.public_projection()["input_mode"]["kind"])
        self.assertTrue(engine.public_projection()["terminal_ui_pager"])
        self.assertEqual(0, engine.state["time"] - 14)
        engine.step("MiscAction.MORE")
        public = engine.public_projection()
        self.assertEqual("The kitten bites the grid bug. The grid bug is killed!", public["message"])
        self.assertEqual("The kitten bites the grid bug.  The grid bug is killed!", engine.state["message"])
        self.assertEqual("normal", public["input_mode"]["kind"])
        self.assertFalse(public["terminal_ui_pager"])
        self.assertEqual(15, engine.state["time"])
        self.assertEqual(hp_before, engine.state["hp"])
        self.assertEqual(rng_before, engine.state["rng"])
        self.assertEqual([27], engine.state["source_pager"]["queue"])

    def test_wrong_more_key_and_preconditions_fail_hard(self) -> None:
        contract = captured_grid_bug_pager()
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task({"fixture_id": "val-east-seed-20260725", "seed": 20260725}))
        with self.assertRaises(RuntimeError):
            engine.arm_source_pager(contract)
        engine.state["time"] = 14
        engine.state["step_index"] = 14
        engine.state["message"] = "The kitten misses the grid bug."
        engine.arm_source_pager(contract)
        with self.assertRaises(RuntimeError):
            engine.step("CompassDirection.N")

    def test_contract_tampering_is_rejected_before_runtime(self) -> None:
        contract = captured_grid_bug_pager()
        contract["continuation"]["queue"] = [27, 10, 99]
        with self.assertRaises(ValueError):
            validate_source_pager_contract(contract)
        contract = captured_grid_bug_pager()
        contract["continuation"]["consumes_player_turn"] = True
        with self.assertRaises(ValueError):
            validate_source_pager_contract(contract)


if __name__ == "__main__":
    unittest.main()
