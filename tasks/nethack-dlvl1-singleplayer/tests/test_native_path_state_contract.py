from __future__ import annotations

import unittest

from scripts.native_path_state_contract import SCHEMA, validate_native_path_state


def complete_snapshot() -> dict[str, object]:
    return {
        "schema": "gamebench.nethack.native_entity_snapshot.v1",
        "turn_queue": [7],
        "entities": [
            {
                "entity_id": 7,
                "x": 12,
                "y": 8,
                "native_x": 13,
                "allegiance": "tame",
                "scheduler": {"iteration_order": 0},
                "path_state": {
                    "apparent_hero_native": {"x": 14, "y": 8},
                    "mtrack_native": [{"x": 0, "y": 0}] * 4,
                    "strategy": 0,
                    "trap_seen_mask": 0,
                    "last_monster_move": 0,
                    "status": {
                        "cancelled": False, "can_see": True, "invisible": False, "undetected": False,
                        "flee_timeout": 0, "blind_timeout": 0, "stunned": False, "frozen_timeout": 0,
                        "confused": False, "trapped": False, "leashed": False, "is_minion": False,
                        "eating_timeout": 0,
                    },
                    "edog": {
                        "droptime": 0, "dropdist": 10000, "apport": 9, "whistletime": 0,
                        "hungrytime": 1001, "ogoal_native": {"x": -1, "y": -1}, "abuse": 0,
                        "revivals": 0, "mhpmax_penalty": 0, "killed_by_u": False,
                    },
                },
            }
        ],
    }


class NativePathStateContractTests(unittest.TestCase):
    def test_complete_abi_extension_is_source_assertion_only(self) -> None:
        report = validate_native_path_state(complete_snapshot())

        self.assertEqual(SCHEMA, report["schema"])
        self.assertEqual("pass", report["status"])
        self.assertEqual(1, report["comparison_count"])
        self.assertTrue(report["source_assertion_eligible"])
        self.assertFalse(report["gold_scheduler_pathing_eligible"])

    def test_legacy_all_absent_extension_is_valid_but_has_no_path_coverage(self) -> None:
        snapshot = complete_snapshot()
        entity = snapshot["entities"][0]  # type: ignore[index]
        entity.pop("path_state")
        report = validate_native_path_state(snapshot)

        self.assertEqual("pass", report["status"])
        self.assertEqual("legacy_extension_absent_nonempty_entities", report["extension_status"])
        self.assertEqual(0, report["comparison_count"])
        self.assertFalse(report["source_assertion_eligible"])

    def test_partial_or_corrupt_extension_fails_closed(self) -> None:
        cases: list[tuple[str, dict[str, object], str]] = []
        partial = complete_snapshot()
        partial["entities"].append({"entity_id": 8, "x": 13, "y": 8, "native_x": 14, "allegiance": "hostile", "scheduler": {"iteration_order": 1}})  # type: ignore[index]
        partial["turn_queue"].append(8)  # type: ignore[index]
        cases.append(("partial", partial, "partial_path_extension"))
        duplicate = complete_snapshot()
        duplicate["entities"][0]["entity_id"] = 0  # type: ignore[index]
        cases.append(("id", duplicate, "invalid_stable_entity_id"))
        bad_queue = complete_snapshot()
        bad_queue["turn_queue"] = []
        cases.append(("queue", bad_queue, "turn_queue_mismatch"))
        bad_coordinate = complete_snapshot()
        bad_coordinate["entities"][0]["native_x"] = 12  # type: ignore[index]
        cases.append(("coordinate", bad_coordinate, "invalid_entity_coordinate"))
        bad_target = complete_snapshot()
        bad_target["entities"][0]["path_state"]["apparent_hero_native"] = {"x": "bad", "y": 8}  # type: ignore[index]
        cases.append(("target", bad_target, "invalid_apparent_target"))
        missing_edog = complete_snapshot()
        missing_edog["entities"][0]["path_state"]["edog"] = None  # type: ignore[index]
        cases.append(("edog", missing_edog, "missing_tame_edog"))
        for name, snapshot, code in cases:
            with self.subTest(name=name):
                report = validate_native_path_state(snapshot)
                self.assertEqual("rejected", report["status"])
                self.assertIn(code, {issue["code"] for issue in report["issues"]})

    def test_zero_entity_frame_cannot_claim_positive_path_coverage(self) -> None:
        report = validate_native_path_state({"schema": "gamebench.nethack.native_entity_snapshot.v1", "entities": []})

        self.assertEqual("pass", report["status"])
        self.assertEqual(0, report["comparison_count"])
        self.assertFalse(report["source_assertion_eligible"])


if __name__ == "__main__":
    unittest.main()
