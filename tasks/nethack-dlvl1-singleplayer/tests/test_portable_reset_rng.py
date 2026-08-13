"""Portable reset ISAAC64 projection and cross-language checkpoint guards."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from scripts.portable_reset_rng import (
    EXPECTED_CONTEXT_SIZE,
    encode_context,
    portable_reset_rng_projection,
    replay_projection,
    validate_portable_reset_rng_projection,
)
from shared.task_resolve import resolve_task


def _snapshot() -> dict[str, object]:
    context = encode_context({"n": 0, "r": [0] * 256, "m": [0] * 256, "a": 0, "b": 0, "c": 0})
    raw = bytes.fromhex(context)
    lane = {
        "n": 0,
        "byte_length": EXPECTED_CONTEXT_SIZE,
        "state_hex": context,
        "state_sha256": hashlib.sha256(raw).hexdigest(),
    }
    return {
        "schema": "gamebench.nethack.authoritative_rng_snapshot.v1",
        "binary_sha256": "7ac1270dfd5fa0a5fb2f715ef6a7151058f06cda595e4b722ac6d070ce0f2057",
        "core": lane,
        "display": dict(lane),
    }


def _task_with_rng() -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(3, 8):
        terrain[4][x] = "."
    level = {
        "terrain": ["".join(row) for row in terrain],
        "hero": {"x": 5, "y": 4},
        "metadata": {"nle_blstats": [5, 4] + [0] * 25},
        "authoritative_reset_rng": portable_reset_rng_projection(_snapshot()),
    }
    return {"task_id": "portable-reset-rng", "seed": 7, "rules": {"max_steps": 0}, "level_dump": level}


class PortableResetRngTests(unittest.TestCase):
    def test_exact_projection_replay_is_deterministic_and_tamper_evident(self) -> None:
        projection = portable_reset_rng_projection(_snapshot())
        self.assertEqual([], validate_portable_reset_rng_projection(projection))
        values_a, state_a = replay_projection(projection, "core", 300)
        values_b, state_b = replay_projection(projection, "core", 300)
        self.assertEqual(values_a, values_b)
        self.assertEqual(state_a, state_b)
        tampered = json.loads(json.dumps(projection))
        tampered["lanes"]["core"]["n"] = 1
        self.assertTrue(validate_portable_reset_rng_projection(tampered))

    def test_python_checkpoint_preserves_reset_rng_projection(self) -> None:
        resolved = resolve_task(_task_with_rng())
        engine = NethackDlvl1Engine()
        engine.reset(resolved)
        payload = json.loads(engine.checkpoint_bytes())
        self.assertEqual(resolved["level_dump"]["authoritative_reset_rng"], payload["sim"]["authoritative_reset_rng"])

    def test_rust_accepts_the_same_python_reset_rng_checkpoint(self) -> None:
        resolved = resolve_task(_task_with_rng())
        engine = NethackDlvl1Engine()
        engine.reset(resolved)
        completed = subprocess.run(
            ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--", "--checkpoint-stdin"],
            input=engine.checkpoint_bytes().decode(), text=True, capture_output=True, check=True,
        )
        checkpoint = json.loads(json.loads(completed.stdout)["checkpoint"])
        self.assertEqual(resolved["level_dump"]["authoritative_reset_rng"], checkpoint["sim"]["authoritative_reset_rng"])


if __name__ == "__main__":
    unittest.main()
