"""Gold runtime must retain the reset-entity source boundary across checkpoints."""

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
from scripts.oracle_tape import sha256_json
from scripts.portable_reset_map import portable_reset_map_projection
from shared.task_resolve import resolve_task


def task() -> dict[str, object]:
    terrain = [[" "] * 79 for _ in range(21)]
    for x in range(3, 8):
        terrain[4][x] = "."
    return {
        "task_id": "python-reset-entity-runtime-boundary",
        "seed": 71,
        "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 0},
        "level_dump": {"terrain": ["".join(row) for row in terrain], "hero": {"x": 5, "y": 4}},
    }


def portable_reset_entities() -> dict[str, object]:
    projection: dict[str, object] = {
        "schema": "gamebench.nethack.authoritative_reset_entities.v1",
        "capture_boundary": {"kind": "reset", "action_step": 0, "before_action_step": 1},
        "source_state_sha256": "a" * 64,
        "source_turn": {"moves": 0, "monstermoves": 0},
        "turn_queue": [],
        "entities": [],
        "player": {"x": 5, "y": 4, "source_turn": 0},
    }
    projection["projection_sha256"] = sha256_json(projection)
    return projection


def authoritative_task() -> dict[str, object]:
    result = task()
    level = result["level_dump"]
    assert isinstance(level, dict)
    level["metadata"] = {"nle_blstats": [5, 4] + [0] * 25}
    level["authoritative_reset_entities"] = portable_reset_entities()
    return result


def authoritative_map_with_boulder() -> dict[str, object]:
    source = {
        "schema": "gamebench.nethack.native_map_fov_snapshot.v1",
    }
    # Keep the map fixture source-shaped while using the task's pinned binary
    # identity; the portable projection validates all reset-only fields.
    from scripts.nle_native_entities import EXPECTED_BINARY_SHA256
    source.update({
        "binary_sha256": EXPECTED_BINARY_SHA256,
        "source_export_eligible": True,
        "gold_implementation_eligible": False,
        "full_map_terrain": [[24] * 79 for _ in range(21)],
        "full_map_terrain_flags": [[0] * 79 for _ in range(21)],
        "full_map_terrain_horizontal": [[False] * 79 for _ in range(21)],
    })
    boulder = [[False] * 79 for _ in range(21)]
    boulder[4][7] = True
    source["dynamic_vision_blockers"] = {
        "boulder": boulder,
        "visible_mimic": [[False] * 79 for _ in range(21)],
        "effective": [list(row) for row in boulder],
        "records": [{"kind": "boulder", "x": 7, "y": 4, "native_x": 8, "object_id": 1, "object_type": 447}],
    }
    projection = portable_reset_map_projection(source)
    result = task()
    level = result["level_dump"]
    assert isinstance(level, dict)
    level["authoritative_reset_map"] = projection
    return result


class PythonResetEntityRuntimeTests(unittest.TestCase):
    def reset(self) -> NethackDlvl1Engine:
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(task()))
        return engine

    def authoritative_reset(self) -> NethackDlvl1Engine:
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(authoritative_task()))
        return engine

    def test_portable_reset_entities_are_validated_initialized_and_checkpointed_without_a_transition(self) -> None:
        engine = self.authoritative_reset()
        snapshot = engine.authoritative_scheduler_snapshot()
        self.assertEqual("initialized_reset_only", snapshot["status"])
        self.assertEqual([], snapshot["turn_queue"])
        self.assertEqual(0, snapshot["entity_count"])
        self.assertFalse(snapshot["scheduler_transition_applied"])
        before = engine.public_projection()
        engine.step("CompassDirection.E")
        self.assertEqual("initialized_reset_only", engine.authoritative_scheduler_snapshot()["status"])
        self.assertEqual(before["blstats"][20] + 1, engine.public_projection()["blstats"][20])

        restored = NethackDlvl1Engine()
        restored.restore_checkpoint(engine.checkpoint_bytes())
        self.assertEqual(engine.authoritative_scheduler_snapshot(), restored.authoritative_scheduler_snapshot())

    def test_complete_reset_blstats_supply_scheduler_stat_defaults(self) -> None:
        # Fuzz level dumps carry the validated public reset stats in
        # ``nle_blstats`` but do not duplicate every stat in metadata.  The
        # source scheduler must use that reset-bound value (DEX=15 here) for
        # allmain.c's stat-dependent engraving gate instead of silently
        # falling back to the legacy default DEX=10.
        entry = authoritative_task()
        level = entry["level_dump"]
        assert isinstance(level, dict)
        level["metadata"]["nle_blstats"] = [5, 4, 18, 0, 15, 18, 7, 10, 7] + [0] * 18
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(entry))
        self.assertEqual(15, engine.state["dexterity"])
        self.assertEqual(85, 40 + 3 * engine.state["dexterity"])

    def test_portable_projection_digest_and_checkpoint_immutability_fail_closed(self) -> None:
        bad_task = authoritative_task()
        level = bad_task["level_dump"]
        assert isinstance(level, dict)
        projection = level["authoritative_reset_entities"]
        assert isinstance(projection, dict)
        projection["player"] = {"x": 4, "y": 4, "source_turn": 0}
        with self.assertRaisesRegex(ValueError, "authoritative_reset_entities"):
            resolve_task(bad_task)

        engine = self.authoritative_reset()
        checkpoint = json.loads(engine.checkpoint_bytes())
        checkpoint["sim"]["authoritative_reset_entities"]["source_turn"]["moves"] = 1
        with self.assertRaisesRegex(ValueError, "differs from immutable"):
            NethackDlvl1Engine().restore_checkpoint(json.dumps(checkpoint).encode())

    def test_native_reset_receipt_is_rejected_even_when_the_caller_claims_it_is_valid(self) -> None:
        engine = self.reset()
        with self.assertRaisesRegex(ValueError, "assertion-only"):
            engine.ingest_native_reset_entity_state({"schema": "gamebench.nethack.native_reset_entity_scheduler_state.v1"})

    def test_joined_tame_reset_entity_replays_hack_c_safepet_rng_guard(self) -> None:
        """The source ``rn2(7)`` guard rejects this reset's pet move."""

        fixture = TASK_DIR / "fixtures" / "nle_oracle" / "val-read-seed-20260725"
        meta = json.loads((fixture / "meta.json").read_text())
        engine = NethackDlvl1Engine()
        engine.reset(
            resolve_task(
                {
                    "task_id": meta["fixture_id"],
                    "seed": meta["seed"],
                    "character": meta["character"],
                    "rules": {"max_steps": 0, "autopickup": False, "auto_more": "raw_explicit", "vision_radius": 5},
                    "level_dump": json.loads((fixture / "level_dump.json").read_text()),
                }
            )
        )
        self.assertEqual(1, len(engine.state["safe_pet_runtime"]), engine.state["safe_pet_runtime"])
        result = engine.step("CompassDirection.NE")["public"]
        self.assertEqual([34, 17], result["blstats"][:2])
        self.assertEqual("You stop. Your kitten is in the way!", result["message"])
        self.assertEqual("f", result["chars"][16][35])
        self.assertEqual(8, result["specials"][16][35])
        self.assertEqual({"x": 35, "y": 16}, engine.state["safe_pet_runtime"][0]["position"])
        restored = NethackDlvl1Engine()
        restored.restore_checkpoint(engine.checkpoint_bytes())
        self.assertEqual(engine.symbolic_readout(), restored.symbolic_readout())
        self.assertEqual(
            engine.state["authoritative_scheduler_runtime"],
            restored.state["authoritative_scheduler_runtime"],
        )

    def test_checkpoint_round_trip_preserves_the_sidecar_boundary(self) -> None:
        engine = self.reset()
        checkpoint = engine.checkpoint_bytes()
        restored = NethackDlvl1Engine()
        restored.restore_checkpoint(checkpoint)
        self.assertEqual(engine.symbolic_readout(), restored.symbolic_readout())

    def test_reset_boulder_blocker_is_one_shot_and_kick_expires_it(self) -> None:
        engine = NethackDlvl1Engine()
        engine.reset(resolve_task(authoritative_map_with_boulder()))
        self.assertTrue(engine.state["reset_dynamic_vision_boulders_available"])
        self.assertEqual([(7, 4)], engine._reset_dynamic_vision_boulders())
        engine.step("Command.KICK")
        engine.step("CompassDirection.E")
        self.assertFalse(engine.state["reset_dynamic_vision_boulders_available"])
        self.assertEqual([], engine._reset_dynamic_vision_boulders())

    def test_checkpoint_sidecar_and_future_frame_hydration_fail_closed(self) -> None:
        engine = self.reset()
        payload = json.loads(engine.checkpoint_bytes())
        sidecar = deepcopy(payload)
        sidecar["sim"]["native_reset_entity_state"] = {"state": {"entities": []}}
        with self.assertRaisesRegex(ValueError, "forbidden source-sidecar"):
            NethackDlvl1Engine().restore_checkpoint(json.dumps(sidecar).encode())

        future = deepcopy(payload)
        future["sim"]["future_frames"] = [{"step": 1}]
        with self.assertRaisesRegex(ValueError, "forbidden source-sidecar"):
            NethackDlvl1Engine().restore_checkpoint(json.dumps(future).encode())

    def test_resolved_task_sidecar_alias_is_rejected_before_state_copy(self) -> None:
        resolved = resolve_task(task())
        resolved["native_reset_entity_state"] = {"state": {"entities": []}}
        with self.assertRaisesRegex(ValueError, "forbidden source-sidecar"):
            NethackDlvl1Engine().reset(resolved)

    def test_rust_preserves_validated_projection_and_accepts_python_checkpoint(self) -> None:
        resolved = resolve_task(authoritative_task())
        python = NethackDlvl1Engine()
        python.reset(resolved)
        checkpoint = python.checkpoint_bytes().decode("utf-8")
        completed = subprocess.run(
            [
                "cargo", "run", "--quiet", "--manifest-path",
                str(TASK_DIR / "gold_rust" / "Cargo.toml"),
                "--bin", "scenario", "--", "--checkpoint-stdin",
            ],
            input=checkpoint,
            text=True,
            capture_output=True,
            check=True,
        )
        projection = json.loads(completed.stdout)["projection"]
        self.assertEqual(python.symbolic_readout(), projection)
        rust_checkpoint = json.loads(json.loads(completed.stdout)["checkpoint"])
        self.assertEqual(
            resolved["level_dump"]["authoritative_reset_entities"],
            rust_checkpoint["sim"]["authoritative_reset_entities"],
        )
        self.assertEqual(
            python.state["authoritative_reset_entity_blstats"],
            rust_checkpoint["sim"]["authoritative_reset_entity_blstats"],
        )

    def test_rust_preserves_reset_boulder_gate(self) -> None:
        resolved = resolve_task(authoritative_map_with_boulder())
        python = NethackDlvl1Engine()
        python.reset(resolved)
        checkpoint = python.checkpoint_bytes().decode("utf-8")
        completed = subprocess.run(
            [
                "cargo", "run", "--quiet", "--manifest-path",
                str(TASK_DIR / "gold_rust" / "Cargo.toml"),
                "--bin", "scenario", "--", "--checkpoint-stdin",
            ],
            input=checkpoint,
            text=True,
            capture_output=True,
            check=True,
        )
        rust_checkpoint = json.loads(json.loads(completed.stdout)["checkpoint"])
        self.assertTrue(rust_checkpoint["sim"]["reset_dynamic_vision_boulders_available"])
        self.assertEqual(
            resolved["level_dump"]["authoritative_reset_map"],
            rust_checkpoint["sim"]["authoritative_reset_map"],
        )
        completed_after_kick = subprocess.run(
            [
                "cargo", "run", "--quiet", "--manifest-path",
                str(TASK_DIR / "gold_rust" / "Cargo.toml"),
                "--bin", "scenario", "--", "--checkpoint-replay-stdin",
            ],
            input=json.dumps({"checkpoint": checkpoint, "actions": ["Command.KICK", "CompassDirection.E"]}),
            text=True,
            capture_output=True,
            check=True,
        )
        rust_after_kick = json.loads(json.loads(completed_after_kick.stdout)["checkpoint"])
        self.assertFalse(rust_after_kick["sim"]["reset_dynamic_vision_boulders_available"])

    def test_rust_rejects_scheduler_inventory_surface_tampering(self) -> None:
        python = NethackDlvl1Engine()
        python.reset(resolve_task(authoritative_task()))
        checkpoint = json.loads(python.checkpoint_bytes())
        checkpoint["sim"]["authoritative_scheduler_runtime"] = {
            "schema": "gamebench.nethack.reset_owned_scheduler.v1",
            "player_inventory": [],
        }
        completed = subprocess.run(
            [
                "cargo", "run", "--quiet", "--manifest-path",
                str(TASK_DIR / "gold_rust" / "Cargo.toml"),
                "--bin", "scenario", "--", "--checkpoint-stdin",
            ],
            input=json.dumps(checkpoint),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("player_inventory differs", completed.stderr)


if __name__ == "__main__":
    unittest.main()
