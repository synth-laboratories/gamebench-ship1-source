from __future__ import annotations

import ctypes
import sys
import unittest
from copy import deepcopy
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.nle_native_player import (
    EXPECTED_PROP_SIZE,
    EXPECTED_ROLE_SIZE,
    EXPECTED_YOU_SIZE,
    KICKING_BOOTS,
    NativePlayerSnapshot,
    NativeYou,
    PM_MONK,
    PM_SAMURAI,
    PM_SASQUATCH,
    PinnedNlePlayerReader,
    _assert_layout,
    dokick_martial_predicate,
)


class NativePlayerLayoutTests(unittest.TestCase):
    def test_dokick_martial_predicate_includes_every_pinned_source_arm(self) -> None:
        self.assertFalse(dokick_martial_predicate(340, 340, None)["effective"])
        self.assertTrue(dokick_martial_predicate(PM_MONK, 340, None)["effective"])
        self.assertTrue(dokick_martial_predicate(PM_SAMURAI, 340, None)["effective"])
        self.assertTrue(dokick_martial_predicate(340, PM_SASQUATCH, None)["effective"])
        self.assertTrue(dokick_martial_predicate(340, 340, KICKING_BOOTS)["effective"])

    def test_pinned_player_layout_is_explicit(self) -> None:
        self.assertEqual(EXPECTED_YOU_SIZE, ctypes.sizeof(NativeYou))
        self.assertEqual(24, EXPECTED_PROP_SIZE)
        self.assertEqual(288, EXPECTED_ROLE_SIZE)
        _assert_layout()

    def test_live_player_snapshot_is_read_only_publicly_checked_and_tamper_detected(self) -> None:
        if sys.platform != "darwin":
            self.skipTest("pinned native reader targets the macOS NLE wheel")
        try:
            import nle
            from nle import nethack
        except ModuleNotFoundError:
            self.skipTest("NLE unavailable")
        env = nle.env.NLE(
            character="val-hum-fem-law",
            observation_keys=("blstats", "inv_letters", "inv_oclasses"),
            actions=tuple(nethack.ACTIONS),
            allow_all_modes=True,
            allow_all_yn_questions=True,
        )
        try:
            env.seed(core=123, disp=456, reseed=False)
            observation = env.reset()
            reader = PinnedNlePlayerReader(env.nethack)
            snapshot = reader.snapshot()
            self.assertEqual(snapshot.public_record(), reader.snapshot().public_record())
            controls = reader.validate_against_public_pre_action(snapshot, observation)
            self.assertEqual(16, controls["verified_blstats"])
            self.assertGreater(controls["verified_inventory_entries"], 0)
            self.assertTrue(snapshot.player["completeness"]["reset_wall_kick"]["complete"])
            self.assertFalse(snapshot.player["completeness"]["reset_wall_kick_portable"]["complete"])
            self.assertEqual(600, snapshot.player["exercise_state"]["next_attrib_check"])
            self.assertEqual(0, snapshot.player["exercise_state"]["aexe"]["dexterity"])
            self.assertFalse(snapshot.player["completeness"]["basic_melee"]["complete"])
            martial = snapshot.player["combat"]["martial"]
            self.assertEqual(
                martial["effective"],
                martial["role_bonus"] or martial["sasquatch_form"] or martial["kicking_boots"],
            )

            tampered_player = deepcopy(snapshot.player)
            tampered_player["resources"]["hp"] += 1
            tampered = NativePlayerSnapshot(snapshot.binary_sha256, snapshot.source_turn, tampered_player)
            with self.assertRaisesRegex(RuntimeError, "blstats disagreement"):
                reader.validate_against_public_pre_action(tampered, observation)
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
