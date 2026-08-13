from __future__ import annotations

import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.nle_rng_state import (
    EXPECTED_CONTEXT_SIZE,
    EXPECTED_ENTRY_SIZE,
    EXPECTED_STATE_OFFSET,
    Isaac64Context,
    PinnedNleRngReader,
    RngEntry,
    bounded_call_count,
    validate_rng_record,
)


class NleRngLayoutTests(unittest.TestCase):
    def test_pinned_isaac64_layout(self) -> None:
        import ctypes

        self.assertEqual(EXPECTED_CONTEXT_SIZE, ctypes.sizeof(Isaac64Context))
        self.assertEqual(EXPECTED_ENTRY_SIZE, ctypes.sizeof(RngEntry))
        self.assertEqual(EXPECTED_STATE_OFFSET, RngEntry.state.offset)

    def test_live_reader_is_stable_and_search_advances_core(self) -> None:
        if sys.platform != "darwin":
            self.skipTest("pinned native RNG reader currently targets the macOS wheel")
        try:
            from nle import nethack
        except ModuleNotFoundError:
            self.skipTest("NLE is not installed")

        game = nethack.Nethack(observation_keys=("program_state",), copy=True, ttyrec=None)
        try:
            game.set_initial_seeds(123, 456, False)
            observation = game.reset()
            while not observation[0][3]:
                observation, _ = game.step(13)
            reader = PinnedNleRngReader(game)
            before = reader.snapshot()
            self.assertEqual(before, reader.snapshot(), "read-only capture advanced RNG state")
            self.assertEqual([], validate_rng_record(before.public_record()))
            tampered = before.public_record()
            tampered["core"]["state_hex"] = "00" + tampered["core"]["state_hex"][2:]
            self.assertTrue(validate_rng_record(tampered))
            game.step(ord("s"))
            after = reader.snapshot()
            self.assertGreater(bounded_call_count(before, after, "core"), 0)
            self.assertEqual(0, bounded_call_count(before, after, "display"))
            exact = reader.exact_call_count(before, after, "core")
            self.assertEqual(bounded_call_count(before, after, "core"), exact)
            self.assertEqual(after, reader.replay_draws(before, "core", exact))
            # Full post-state matching, not the n-index alone, prevents a
            # zero-draw conclusion from accepting a changed ISAAC block.
            with self.assertRaisesRegex(ValueError, "unjudgeable"):
                reader.exact_call_count(before, after, "core", max_draws=0)
        finally:
            game.close()

    def test_independent_same_seed_snapshots_match(self) -> None:
        if sys.platform != "darwin":
            self.skipTest("pinned native RNG reader currently targets the macOS wheel")
        try:
            from nle import nethack
        except ModuleNotFoundError:
            self.skipTest("NLE is not installed")

        snapshots = []
        for _ in range(2):
            game = nethack.Nethack(observation_keys=("program_state",), copy=True, ttyrec=None)
            try:
                game.set_initial_seeds(321, 654, False)
                observation = game.reset()
                while not observation[0][3]:
                    observation, _ = game.step(13)
                snapshots.append(PinnedNleRngReader(game).snapshot())
            finally:
                game.close()
        self.assertEqual(snapshots[0], snapshots[1])


if __name__ == "__main__":
    unittest.main()
