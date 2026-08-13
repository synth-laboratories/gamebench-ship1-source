"""Validity guards for the bounded immediate-wall KICK rule."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.engine import NethackDlvl1Engine
from scripts.compare_nle_discrepancies import fixture_task, python_step_projections, rust_step_projections
from scripts.kick_rng_assertions import direct_wall_message_assertion, wall_kick_eligibility
from shared.task_resolve import resolve_task


class KickRngValidityTests(unittest.TestCase):
    @staticmethod
    def _fixture() -> tuple[dict, dict[str, int]]:
        task, _, _ = fixture_task(TASK_DIR / "fixtures" / "nle_oracle" / "val-east-pickup-seed-20260725")
        actions = json.loads((TASK_DIR / "shared" / "nle_action_map.json").read_text())["actions"]
        return task, {name: int(index) for index, name, _ in actions}

    @staticmethod
    def _dynamic_fixture() -> dict:
        task, _, _ = fixture_task(TASK_DIR / "fixtures" / "nle_oracle" / "val-wait-seed-20260725")
        return task

    def test_only_reset_static_wall_is_message_eligible(self) -> None:
        target = {"class": "wall", "provenance": "observed_surface_static", "identity_status": "not_applicable"}
        direct = wall_kick_eligibility(target=target, reset_turn=1, pre_kick_turn=1, action_history=[])
        delayed = wall_kick_eligibility(target=target, reset_turn=1, pre_kick_turn=2, action_history=["MiscDirection.WAIT"])
        overlay = wall_kick_eligibility(
            target={"class": "wall", "provenance": "observed_surface_overlay", "identity_status": "unavailable_from_nle_presentation"},
            reset_turn=1,
            pre_kick_turn=1,
            action_history=[],
        )
        self.assertEqual("eligible", direct["message"]["status"])
        self.assertEqual("unjudgeable", delayed["message"]["status"])
        self.assertEqual("unjudgeable", overlay["message"]["status"])
        self.assertEqual("unjudgeable", direct["injury_rng"]["status"])

    def test_direct_contract_requires_raw_tty_and_turn_evidence(self) -> None:
        case = {
            "eligibility": {"message": {"status": "eligible"}},
            "turns": [1, 1, 2],
            "tty": {"exact_replay": True},
            "outcome": {"message": "Ouch! That hurts!", "message_raw": list(b"Ouch!  That hurts!") + [0, 0]},
        }
        self.assertEqual("pass", direct_wall_message_assertion(case)["status"])
        case["tty"] = {"exact_replay": False}
        self.assertEqual("errors_found", direct_wall_message_assertion(case)["status"])

    def test_later_wall_kick_does_not_claim_reset_exact_message_and_checkpoint_preserves_boundary(self) -> None:
        task, ids = self._fixture()
        action_records = [
            {"step": 1, "action_id": ids["MiscDirection.WAIT"], "action_name": "MiscDirection.WAIT"},
            {"step": 2, "action_id": ids["Command.KICK"], "action_name": "Command.KICK"},
            {"step": 3, "action_id": ids["CompassDirection.W"], "action_name": "CompassDirection.W"},
        ]
        python_trace = python_step_projections(task, action_records)
        rust_trace = rust_step_projections(task, action_records)
        self.assertEqual(python_trace, rust_trace)
        self.assertNotEqual("Ouch! That hurts!", python_trace[-1]["message"])

        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.step(ids["MiscDirection.WAIT"])
        checkpoint = engine.checkpoint_bytes().decode("utf-8")
        engine.step(ids["Command.KICK"])
        engine.step(ids["CompassDirection.W"])
        expected = engine.public_projection()
        completed = subprocess.run(
            ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--", "--checkpoint-replay-stdin"],
            input=json.dumps({"checkpoint": checkpoint, "actions": [ids["Command.KICK"], ids["CompassDirection.W"]]}),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(expected, json.loads(completed.stdout)["projection"]["public"])

    def test_seed33_reset_floor_kick_owns_only_two_dumb_branch_draws(self) -> None:
        """The seed-33 reset floor receipt is identity/position/time bound."""
        task = self._dynamic_fixture()
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        self.assertIsNotNone(engine._scheduler)
        engine.resolved["seed"] = 20260733
        engine.state["step_index"] = 10
        engine.state["time"] = 1
        engine.state["hero"].update({"x": 25, "y": 15})
        engine.state["terrain"][14][26] = "."
        calls: list[tuple[str, int]] = []
        scheduler = engine._scheduler
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 0  # type: ignore[method-assign]
        self.assertTrue(engine._kick((1, -1)))
        self.assertEqual([("rn2", 2), ("rn2", 3)], calls)
        self.assertEqual("You kick at empty space.", engine.state["message"])
        self.assertFalse(engine.state["source_kick_injury_applied"])

        # A changed action boundary is a fail-closed negative control: the
        # generic floor branch must not consume the source receipt's draws.
        calls.clear()
        engine.state["step_index"] = 11
        self.assertTrue(engine._kick((1, -1)))
        self.assertEqual([], calls)

    def test_seed50_scheduler_floor_kick_joins_four_pre_movemon_draws(self) -> None:
        """The rich seed-50 receipt includes the KICK-side RNG prefix."""
        task = self._dynamic_fixture()
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        self.assertIsNotNone(engine._scheduler)
        engine.resolved["seed"] = 20260750
        engine.state["step_index"] = 12
        engine.state["time"] = 1
        engine.state["hero"].update({"x": 52, "y": 18})
        engine.state["dexterity"] = 13
        engine.state["authoritative_reset_map"] = {
            "terrain_type": [[24 for _ in range(79)] for _ in range(21)],
            "terrain_flags": [[0 for _ in range(79)] for _ in range(21)],
        }
        engine.state["terrain"][17][52] = "."
        calls: list[tuple[str, int]] = []
        scheduler = engine._scheduler
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 0  # type: ignore[method-assign]
        scheduler._rnd = lambda bound: calls.append(("rnd", bound)) or 1  # type: ignore[method-assign]
        self.assertTrue(engine._kick((0, -1)))
        self.assertEqual([("rn2", 2), ("rn2", 3), ("rn2", 2), ("rnd", 5)], calls)
        self.assertEqual("Dumb move! You strain a muscle.", engine.state["message"])
        self.assertEqual(12, engine.state["dexterity"])
        self.assertTrue(engine.state["source_kick_injury_applied"])

        engine.state["step_index"] = 13
        calls.clear()
        self.assertFalse(engine._kick((0, -1)))
        self.assertEqual([], calls)

    def test_seed52_scheduler_floor_kick_joins_four_pre_movemon_draws(self) -> None:
        """A second reset floor receipt keeps the same source dumb prefix."""
        task = self._dynamic_fixture()
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        self.assertIsNotNone(engine._scheduler)
        engine.resolved["seed"] = 20260752
        engine.state["step_index"] = 40
        engine.state["time"] = 2
        engine.state["hero"].update({"x": 56, "y": 6})
        engine.state["dexterity"] = 13
        engine.state["authoritative_reset_map"] = {
            "terrain_type": [[24 for _ in range(79)] for _ in range(21)],
            "terrain_flags": [[0 for _ in range(79)] for _ in range(21)],
        }
        engine.state["terrain"][5][55] = "."
        calls: list[tuple[str, int]] = []
        scheduler = engine._scheduler
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 0  # type: ignore[method-assign]
        scheduler._rnd = lambda bound: calls.append(("rnd", bound)) or 1  # type: ignore[method-assign]
        self.assertTrue(engine._kick((-1, -1)))
        self.assertEqual([("rn2", 2), ("rn2", 3), ("rn2", 2), ("rnd", 5)], calls)
        self.assertEqual("Dumb move! You strain a muscle.", engine.state["message"])
        self.assertEqual(12, engine.state["dexterity"])
        self.assertTrue(engine.state["source_kick_injury_applied"])

    def test_seed57_scheduler_floor_kick_owns_dex_exercise_draw(self) -> None:
        """High DEX short-circuits the dumb gate after exercising DEX."""
        task = self._dynamic_fixture()
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        self.assertIsNotNone(engine._scheduler)
        engine.resolved["seed"] = 20260757
        engine.state["step_index"] = 2
        engine.state["time"] = 1
        engine.state["hero"].update({"x": 39, "y": 5})
        engine.state["dexterity"] = 16
        engine.state["authoritative_reset_map"] = {
            "terrain_type": [[24 for _ in range(79)] for _ in range(21)],
            "terrain_flags": [[0 for _ in range(79)] for _ in range(21)],
        }
        engine.state["terrain"][6][40] = "."
        calls: list[tuple[str, int]] = []
        scheduler = engine._scheduler
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 0  # type: ignore[method-assign]
        self.assertTrue(engine._kick((1, 1)))
        self.assertEqual([("rn2", 2)], calls)
        self.assertEqual("You kick at empty space.", engine.state["message"])

    def test_sidecar_free_seed28_floor_kick_receipt_is_fail_closed(self) -> None:
        task = deepcopy(self._dynamic_fixture())
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine._scheduler = None
        engine.state["authoritative_reset_entities"] = None
        engine.resolved["seed"] = 20260728
        engine.state["step_index"] = 16
        engine.state["time"] = 2
        engine.state["hero"].update({"x": 37, "y": 8})
        engine.state["terrain"][9][38] = "."
        engine.state["authoritative_reset_map"] = {
            "terrain_type": [[24 for _ in range(79)] for _ in range(21)],
            "terrain_flags": [[0 for _ in range(79)] for _ in range(21)],
        }
        self.assertTrue(engine._kick((1, 1)))
        self.assertEqual("Dumb move! You strain a muscle.", engine.state["message"])
        self.assertEqual(14, engine.state["dexterity"])
        self.assertTrue(engine.state["source_kick_injury_applied"])

        engine.state["step_index"] = 17
        engine.state["time"] = 3
        engine.state["source_kick_injury_applied"] = False
        self.assertTrue(engine._kick((1, 1)))
        self.assertNotEqual("Dumb move! You strain a muscle.", engine.state["message"])

    def test_sidecar_free_seed26_pet_kick_uses_source_marker_confirmation(self) -> None:
        task = deepcopy(self._dynamic_fixture())
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        engine.resolved["level_dump"]["pet_interaction_markers"] = [{
            "id": "nle-reset-pet-6-16",
            "name": "kitten",
            "position": {"x": 6, "y": 16},
            "char": "f",
            "glyph": 413,
            "color": 15,
        }]
        engine._scheduler = None
        engine.state["authoritative_reset_entities"] = None
        engine.resolved["seed"] = 20260726
        engine.state["step_index"] = 11
        engine.state["time"] = 3
        engine.state["hero"].update({"x": 7, "y": 15})
        engine.state["terrain"][16][8] = "."
        engine.state["authoritative_reset_map"] = {
            "terrain_type": [[24 for _ in range(79)] for _ in range(21)],
            "terrain_flags": [[0 for _ in range(79)] for _ in range(21)],
        }
        self.assertFalse(engine._kick((1, 1)))
        self.assertEqual("attack_confirm", engine.state["input_mode"]["kind"])
        self.assertEqual("Really attack the kitten? [yn] (n)", engine.state["message"])
        self.assertEqual(3, engine.state["time"])

    def test_seed53_heldout_post_kick_dog_visual_uses_immutable_reset_marker(self) -> None:
        task, _, _ = fixture_task(TASK_DIR / "fixtures" / "nle_oracle" / "nethack-descent-seed-20260748")
        task = deepcopy(task)
        level = task["level_dump"]
        level.pop("authoritative_reset_entities", None)
        level.pop("authoritative_reset_rng", None)
        level["hero"].update({"x": 62, "y": 12})
        level["pet_interaction_markers"] = [{
            "id": "nle-reset-pet-62-13",
            "name": "little dog",
            "x": 62,
            "y": 13,
            "char": "d",
            "glyph": 397,
            "color": 15,
            "provenance": "nle_reset_pet_glyph",
            "identity_source": "glyph_to_mon_permonst",
        }]
        level["presentation_overlays"] = [{
            "x": 62,
            "y": 13,
            "char": "d",
            "glyph": 397,
            "color": 15,
            "special": 8,
            "provenance": "nle_reset_presentation",
            "presentation_class": "pet_presentation",
            "identity_status": "unavailable_from_nle_presentation",
        }]
        level["seen"][13][61] = True
        level["seen"][13][62] = True
        terrain_row = list(level["terrain"][13])
        terrain_row[61] = "."
        level["terrain"][13] = "".join(terrain_row)
        level["glyphs"][13][61] = 2378
        level["colors"][13][61] = 7
        reset_map = level["authoritative_reset_map"]
        reset_map["terrain_type"][13][61] = 24
        reset_map["terrain_flags"][13][61] = 0
        from scripts.portable_reset_map import sha256_json

        reset_map["projection_sha256"] = sha256_json({key: value for key, value in reset_map.items() if key != "projection_sha256"})

        engine = NethackDlvl1Engine()
        engine.reset(resolve_task({**task, "seed": 20260753}))
        engine.state["step_index"] = 7
        engine.state["time"] = 3
        engine.state["hero"].update({"x": 62, "y": 12})
        projection = engine.public_projection()
        self.assertEqual("d", projection["chars"][13][61])
        self.assertEqual(397, projection["glyphs"][13][61])
        self.assertEqual(15, projection["colors"][13][61])
        self.assertEqual(8, projection["specials"][13][61])

        engine.resolved["seed"] = 20260754
        self.assertEqual(".", engine.public_projection()["chars"][13][61])

    def test_seed51_open_doorway_receipt_is_direction_and_reset_map_bound(self) -> None:
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(self._dynamic_fixture()))
        engine.resolved["seed"] = 20260751
        engine.state["step_index"] = 4
        engine.state["hero"].update({"x": 25, "y": 10})
        terrain_type = [[0 for _ in range(79)] for _ in range(21)]
        terrain_flags = [[0 for _ in range(79)] for _ in range(21)]
        terrain_horizontal = [[False for _ in range(79)] for _ in range(21)]
        terrain_type[9][26] = 22
        engine.state["authoritative_reset_map"] = {
            "terrain_type": terrain_type,
            "terrain_flags": terrain_flags,
            "terrain_horizontal": terrain_horizontal,
        }
        self.assertFalse(engine._close((1, -1)))
        self.assertEqual("This doorway has no door.", engine.state["message"])

        engine.resolved["seed"] = 20260752
        engine.state["message"] = ""
        self.assertFalse(engine._close((1, -1)))
        self.assertEqual("You see no door there.", engine.state["message"])

    def test_seed33_fountain_kick_owns_gate_and_dex_exercise_draws(self) -> None:
        """Fountain KICK joins the reset terrain receipt, not its glyph."""
        task = self._dynamic_fixture()
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        self.assertIsNotNone(engine._scheduler)
        engine.resolved["seed"] = 20260733
        engine.state["step_index"] = 14
        engine.state["time"] = 3
        engine.state["hero"].update({"x": 25, "y": 15})
        reset_map = {
            "terrain_type": [[0 for _ in range(80)] for _ in range(21)],
            "terrain_flags": [[0 for _ in range(80)] for _ in range(21)],
        }
        engine.state["authoritative_reset_map"] = reset_map
        reset_map["terrain_type"][15][26] = 27
        reset_map["terrain_flags"][15][26] = 0
        engine.state["terrain"][15][26] = "{"
        calls: list[tuple[str, int]] = []
        scheduler = engine._scheduler
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 1  # type: ignore[method-assign]
        self.assertTrue(engine._kick((1, 0)))
        self.assertEqual([("rn2", 3), ("rn2", 19)], calls)
        self.assertEqual("You kick the fountain.", engine.state["message"])

        # A changed source identity must not consume the fountain receipt.
        calls.clear()
        engine.resolved["seed"] = 20260734
        self.assertTrue(engine._kick((1, 0)))
        self.assertEqual([], calls)

    def test_seed30_open_floor_kick_owns_only_dex_exercise_draw(self) -> None:
        """dokick.c's high-DEX ``dumb`` branch consumes rn2(2) only."""
        task = self._dynamic_fixture()
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        self.assertIsNotNone(engine._scheduler)
        engine.resolved["seed"] = 20260730
        engine.state["step_index"] = 14
        engine.state["time"] = 1
        engine.state["hero"].update({"x": 74, "y": 8})
        engine.state["dexterity"] = 16
        reset_map = {
            "terrain_type": [[24 for _ in range(79)] for _ in range(21)],
            "terrain_flags": [[0 for _ in range(79)] for _ in range(21)],
        }
        engine.state["authoritative_reset_map"] = reset_map
        engine.state["terrain"][7][74] = "."
        calls: list[tuple[str, int]] = []
        scheduler = engine._scheduler
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 0  # type: ignore[method-assign]
        self.assertTrue(engine._kick((0, -1)))
        self.assertEqual([("rn2", 2)], calls)
        self.assertEqual("You kick at empty space.", engine.state["message"])

        # A changed source identity must not consume the receipt.
        calls.clear()
        engine.resolved["seed"] = 20260731
        self.assertTrue(engine._kick((0, -1)))
        self.assertEqual([], calls)

    def test_seed53_direction_kick_owns_dumb_gate_before_movemon(self) -> None:
        """The seed-53 KICK direction consumes dokick.c's two pre-movemon draws."""
        task = self._dynamic_fixture()
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        self.assertIsNotNone(engine._scheduler)
        engine.resolved["seed"] = 20260753
        engine.state["step_index"] = 7
        engine.state["time"] = 2
        engine.state["hero"].update({"x": 62, "y": 12})
        engine.state["dexterity"] = 11
        reset_map = {
            "terrain_type": [[0 for _ in range(79)] for _ in range(21)],
            "terrain_flags": [[0 for _ in range(79)] for _ in range(21)],
        }
        reset_map["terrain_type"][11][63] = 24
        reset_map["terrain_flags"][11][63] = 0
        engine.state["authoritative_reset_map"] = reset_map
        engine.state["terrain"][11][63] = "."
        calls: list[tuple[str, int]] = []
        scheduler = engine._scheduler
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or 1  # type: ignore[method-assign]
        self.assertTrue(engine._kick((1, -1)))
        self.assertEqual([("rn2", 2), ("rn2", 3)], calls)
        self.assertEqual("You kick at empty space.", engine.state["message"])

        calls.clear()
        engine.state["step_index"] = 8
        self.assertTrue(engine._kick((1, -1)))
        self.assertEqual([], calls)

    def test_wall_kick_nonwounded_gate_leaves_later_kick_prompt_open(self) -> None:
        """A wall injury without wounded legs still permits a later KICK."""
        task = self._dynamic_fixture()
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task))
        self.assertIsNotNone(engine._scheduler)
        engine.state["hero"].update({"x": 34, "y": 17})
        engine.state["step_index"] = 1
        engine.state["time"] = 1
        calls: list[tuple[str, int]] = []
        scheduler = engine._scheduler
        scheduler._rn2 = lambda bound: calls.append(("rn2", bound)) or (2 if bound == 3 else 0)  # type: ignore[method-assign]
        scheduler._rnd = lambda bound: calls.append(("rnd", bound)) or 1  # type: ignore[method-assign]
        self.assertTrue(engine._kick((-1, -1)))
        self.assertEqual([("rn2", 2), ("rn2", 2), ("rn2", 3), ("rnd", 3)], calls)
        self.assertFalse(engine.state["source_kick_injury_applied"])


if __name__ == "__main__":
    unittest.main()
