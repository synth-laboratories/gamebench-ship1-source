"""Fail-closed coverage for the explicitly assisted source-static replay lane."""

from __future__ import annotations

from copy import deepcopy
import json
import subprocess
import sys
import unittest
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from scripts.fuzz_nle_differential import python_source_state_trace, rust_source_state_trace, source_static_frame
from shared.task_resolve import resolve_task


def resolved_task() -> dict:
    return resolve_task({"task_id": "source-static-replay", "fixture_id": "val-east-seed-20260725", "seed": 20260725})


def unknown_cell(resolved: dict) -> tuple[int, int]:
    level = resolved["level_dump"]
    for y, row in enumerate(level["terrain"]):
        for x, char in enumerate(row):
            if char == " " and not level["seen"][y][x]:
                return x, y
    raise AssertionError("fixture unexpectedly exposes every cell")


def source_static_snapshot(base: dict, x: int, y: int) -> dict:
    snapshot = deepcopy(base)
    chars = list(snapshot["chars"])
    chars[y] = f"{chars[y][:x]}.{chars[y][x + 1:]}"
    snapshot["chars"] = chars
    snapshot["glyphs"][y][x] = 2378  # pinned NLE cmap floor glyph
    snapshot["colors"][y][x] = 7
    return snapshot


def rust_restore(checkpoint: str) -> dict:
    completed = subprocess.run(
        [
            "cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin", "scenario", "--", "--checkpoint-stdin",
        ],
        input=checkpoint,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)["projection"]


class CausalSourceStaticReplayTests(unittest.TestCase):
    def test_reconciliation_hydrates_only_unknown_static_memory_and_checkpoint_preserves_it(self) -> None:
        resolved = resolved_task()
        x, y = unknown_cell(resolved)
        engine = NethackDlvl1Engine()
        engine.reset(resolved)
        counts = engine.reconcile_source_static_cells([{"x": x, "y": y, "char": ".", "glyph": 2378, "color": 7}])
        self.assertEqual({"hydrated": 1, "already_known": 0, "conflicts": 0}, counts)
        self.assertEqual(".", engine.public_projection()["chars"][y][x])

        # A later contradictory screen cannot rewrite simulator-owned terrain.
        conflict = engine.reconcile_source_static_cells([{"x": x, "y": y, "char": "#", "glyph": 2379, "color": 7}])
        self.assertEqual({"hydrated": 0, "already_known": 0, "conflicts": 1}, conflict)
        self.assertEqual(".", engine.public_projection()["chars"][y][x])

        restored = NethackDlvl1Engine()
        restored.restore_checkpoint(engine.checkpoint_bytes())
        self.assertEqual(engine.public_projection(), restored.public_projection())
        rust = rust_restore(engine.checkpoint_bytes().decode("utf-8"))
        self.assertEqual(".", rust["public"]["chars"][y][x])
        self.assertTrue(rust["private"]["seen"][y][x])

    def test_reconciliation_rejects_overlays_and_duplicate_coordinates(self) -> None:
        engine = NethackDlvl1Engine()
        engine.reset(resolved_task())
        with self.assertRaisesRegex(ValueError, "non-static presentation"):
            engine.reconcile_source_static_cells([{"x": 0, "y": 0, "char": "d", "glyph": 340, "color": 7}])
        with self.assertRaisesRegex(ValueError, "assign a cell twice"):
            engine.reconcile_source_static_cells([
                {"x": 0, "y": 0, "char": ".", "glyph": 2378, "color": 7},
                {"x": 0, "y": 0, "char": ".", "glyph": 2378, "color": 7},
            ])

    def test_prior_frame_ordering_and_python_rust_parity(self) -> None:
        resolved = resolved_task()
        x, y = unknown_cell(resolved)
        seed = NethackDlvl1Engine()
        seed.reset(resolved)
        reset = seed.public_projection()
        later = source_static_snapshot(reset, x, y)
        actions = [{"action_id": 18, "action_name": "MiscDirection.WAIT"}] * 2
        expected = [reset, later, later]

        # Frame zero lacks the target. It must not appear after action one;
        # only frame one may hydrate it before action two.
        python, python_reconciliations, _ = python_source_state_trace(resolved, actions, expected)
        rust, rust_reconciliations, _ = rust_source_state_trace(resolved, actions, expected)
        # Existing fixture inventory canonicalization is intentionally covered
        # elsewhere; this lane asserts the reconciled map/turn behavior that
        # both implementations own here.
        self.assertEqual(
            [(entry["chars"][y][x], entry["glyphs"][y][x], entry["colors"][y][x], entry["blstats"][20]) for entry in python],
            [(entry["chars"][y][x], entry["glyphs"][y][x], entry["colors"][y][x], entry["blstats"][20]) for entry in rust],
        )
        self.assertEqual(" ", python[1]["chars"][y][x])
        self.assertEqual(".", python[2]["chars"][y][x])
        self.assertEqual(1, python_reconciliations[1]["counts"]["hydrated"])
        self.assertEqual(python_reconciliations, rust_reconciliations)

    def test_adapter_requires_glyph_classified_cmap_static_surface(self) -> None:
        resolved = resolved_task()
        engine = NethackDlvl1Engine()
        engine.reset(resolved)
        projection = source_static_snapshot(engine.public_projection(), *unknown_cell(resolved))
        cells, audit = source_static_frame(projection)
        self.assertGreater(audit["static_cmap_cells"], 0)
        self.assertEqual(0, audit["rejected_static_char_non_cmap"])
        self.assertTrue(any(cell["char"] == "." and cell["glyph"] == 2378 for cell in cells))


if __name__ == "__main__":
    unittest.main()
