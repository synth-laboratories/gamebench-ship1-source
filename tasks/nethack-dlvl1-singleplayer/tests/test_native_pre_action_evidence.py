from __future__ import annotations

import inspect
import hashlib
import sys
import unittest
from copy import deepcopy
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts import fuzz_nle_differential
from scripts.native_pre_action_evidence import USAGE_POLICY, record_from_exports, validate_records
from scripts.nle_native_player import KICKING_BOOTS, PM_SASQUATCH
from scripts.nle_rng_state import EXPECTED_CONTEXT_SIZE, PINNED_BINARY_SHA256
from scripts.oracle_tape import sha256_json


class NativePreActionEvidenceTests(unittest.TestCase):
    fixture_id = "native-evidence-unit"
    runtime = {"schema": "gamebench.nethack.capture_runtime.v1", "unit": True}
    binary = PINNED_BINARY_SHA256

    def actions(self) -> list[dict[str, object]]:
        return [
            {"step": 1, "action_id": 0, "action_name": "CompassDirection.N", "nle_stepped": True},
            {"step": 2, "action_id": 1, "action_name": "CompassDirection.E", "nle_stepped": True},
        ]

    def exports(self) -> dict[str, dict[str, object]]:
        exact_state = bytes(EXPECTED_CONTEXT_SIZE)
        lane = {
            "n": 0,
            "byte_length": EXPECTED_CONTEXT_SIZE,
            "state_hex": exact_state.hex(),
            "state_sha256": hashlib.sha256(exact_state).hexdigest(),
        }
        player = {
            "coordinates": {"native_x": 1, "native_y": 0, "nle_x": 0, "nle_y": 0},
            "resources": {"experience_level": 1, "hp": 1, "hp_max": 1, "human_hp": 1, "human_hp_max": 1, "energy": 0, "energy_max": 0, "armor_class": 0, "hunger": 0, "hunger_state": 0},
            "attributes": {"effective": {name: 3 for name in ("strength", "intelligence", "wisdom", "dexterity", "constitution", "charisma")}, "components": {name: {"base": 3, "bonus": 0, "temporary": 0} for name in ("strength", "intelligence", "wisdom", "dexterity", "constitution", "charisma")}},
            "combat": {"luck": {"base": 0, "bonus": 0, "total": 0}, "polymorphed": False, "two_weapon": False, "monster_form": {"base_species_id": 340, "current_species_id": 340}, "martial": {"source_macro": "martial_bonus() || is_bigfoot(youmonst.data) || (uarmf && uarmf->otyp == KICKING_BOOTS)", "constants": {"pm_sasquatch": PM_SASQUATCH, "kicking_boots_object_type": KICKING_BOOTS}, "role_species_id": 340, "role_is_monk": False, "role_is_samurai": False, "role_bonus": False, "sasquatch_form": False, "kicking_boots": False, "effective": False}},
            "conditions": {"wounded_legs": {"intrinsic": 0, "extrinsic_sides": 0, "active": False, "left": False, "right": False}},
            "equipment": {"inventory": [], "slots": {slot: None for slot in ("uwep", "uswapwep", "uquiver", "uarm", "uarmu", "uarmc", "uarmh", "uarms", "uarmg", "uarmf")}},
            "completeness": {"reset_wall_kick": {"complete": True, "fields": ["attributes.effective.constitution", "attributes.effective.dexterity", "combat.luck", "conditions.wounded_legs", "resources.hp", "resources.armor_class", "combat.martial.effective"]}, "basic_melee": {"complete": False, "blockers": ["intentionally incomplete"]}},
        }
        return {
            "map_fov": {"schema": "gamebench.nethack.native_map_fov_snapshot.v1", "binary_sha256": self.binary, "plane_sha256": {"terrain": "1"}},
            "entities": {
                "schema": "gamebench.nethack.native_entity_snapshot.v1",
                "binary_sha256": self.binary,
                "source_turn": {"moves": 1, "monstermoves": 1},
                "turn_queue": [],
                "entities": [],
            },
            "player": {"schema": "gamebench.nethack.native_player_combat_snapshot.v1", "source_commit": "2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa", "binary_sha256": self.binary, "source_turn": 1, "player": player},
            "rng": {"schema": "gamebench.nethack.authoritative_rng_snapshot.v1", "binary_sha256": self.binary, "core": lane, "display": deepcopy(lane)},
        }

    def records(self) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        actions = self.actions()
        records = [
            record_from_exports(
                fixture_id=self.fixture_id,
                action=action,
                runtime=self.runtime,
                exports=self.exports(),
                controls={"map_fov": {"checked": 1}, "entities": {"checked": 1}},
            )
            for action in actions
        ]
        return records, actions

    @staticmethod
    def complete_path_entity() -> dict[str, object]:
        """One shape-complete ABI path extension for digest-rebinding tests."""

        return {
            "entity_id": 7,
            "species_id": 3,
            "x": 12,
            "y": 8,
            "native_x": 13,
            "hp": 6,
            "hp_max": 6,
            "allegiance": "tame",
            "underlay": {
                "terrain_type": 24,
                "terrain_memory_glyph": 2378,
                "object_stack": [],
                "object_stack_complete": True,
            },
            "scheduler": {
                "iteration_order": 0,
                "base_speed": 12,
                "movement_points": 12,
                "speed_state": 0,
                "can_move": True,
                "sleeping": False,
                "fleeing": False,
                "strategy": 0,
                "special_cooldown": 0,
            },
            "path_state": {
                "apparent_hero_native": {"x": 14, "y": 8},
                "mtrack_native": [{"x": 0, "y": 0}] * 4,
                "strategy": 0,
                "trap_seen_mask": 0,
                "last_monster_move": 0,
                "status": {
                    "cancelled": False,
                    "can_see": True,
                    "invisible": False,
                    "undetected": False,
                    "flee_timeout": 0,
                    "blind_timeout": 0,
                    "stunned": False,
                    "frozen_timeout": 0,
                    "confused": False,
                    "trapped": False,
                    "leashed": False,
                    "is_minion": False,
                    "eating_timeout": 0,
                },
                "edog": {
                    "droptime": 0,
                    "dropdist": 10000,
                    "apport": 9,
                    "whistletime": 0,
                    "hungrytime": 1001,
                    "ogoal_native": {"x": -1, "y": -1},
                    "abuse": 0,
                    "revivals": 0,
                    "mhpmax_penalty": 0,
                    "killed_by_u": False,
                },
            },
        }

    def record_with_complete_path_entity(self, action: dict[str, object]) -> dict[str, object]:
        exports = self.exports()
        exports["entities"] = {
            **exports["entities"],
            "turn_queue": [7],
            "entities": [self.complete_path_entity()],
        }
        return record_from_exports(
            fixture_id=self.fixture_id,
            action=action,
            runtime=self.runtime,
            exports=exports,
            controls={"map_fov": {"checked": 1}, "entities": {"checked": 1}},
        )

    def failures(self, records: list[dict[str, object]], actions: list[dict[str, object]]) -> list[str]:
        return validate_records(records, actions, fixture_id=self.fixture_id, runtime=self.runtime, require_native=True)

    def test_valid_records_are_boundary_aligned_and_pinned(self) -> None:
        records, actions = self.records()
        self.assertEqual([], self.failures(records, actions))

    def test_zero_missing_and_reordered_records_fail_hard(self) -> None:
        records, actions = self.records()
        self.assertIn("zero pre-action records", "; ".join(self.failures([], actions)))
        self.assertIn("records for 2 actions", "; ".join(self.failures(records[:1], actions)))
        self.assertIn("action binding", "; ".join(self.failures(list(reversed(records)), actions)))

    def test_future_policy_export_hash_and_binary_tampering_fail_hard(self) -> None:
        records, actions = self.records()
        future = deepcopy(records)
        future[0]["usage_policy"] = {**USAGE_POLICY, "captured_before_action_only": False}
        self.assertIn("prohibited hydration", "; ".join(self.failures(future, actions)))

        tampered = deepcopy(records)
        tampered[0]["exports"]["map_fov"]["plane_sha256"]["terrain"] = "tampered"
        self.assertIn("source-state digest", "; ".join(self.failures(tampered, actions)))
        self.assertIn("boundary record digest", "; ".join(self.failures(tampered, actions)))

        mismatched_binary = deepcopy(records)
        mismatched_binary[0]["exports"]["rng"]["binary_sha256"] = "b" * 64
        self.assertIn("binary identity mismatch", "; ".join(self.failures(mismatched_binary, actions)))

    def test_recomputed_outer_hashes_do_not_accept_malformed_player_evidence(self) -> None:
        records, actions = self.records()
        forged = deepcopy(records)
        forged[0]["exports"]["player"]["player"]["resources"]["hp"] = 2
        forged[0]["source_state_sha256"] = sha256_json({"native_identity": forged[0]["native_identity"], "exports": forged[0]["exports"]})
        forged[0]["record_sha256"] = sha256_json({key: value for key, value in forged[0].items() if key != "record_sha256"})
        self.assertIn("player resource contract mismatch", "; ".join(self.failures(forged, actions)))

    def test_recomputed_outer_hashes_do_not_accept_malformed_entity_evidence(self) -> None:
        records, actions = self.records()
        forged = deepcopy(records)
        forged[0]["exports"]["entities"]["source_turn"]["moves"] = "later"
        forged[0]["source_state_sha256"] = sha256_json({"native_identity": forged[0]["native_identity"], "exports": forged[0]["exports"]})
        forged[0]["record_sha256"] = sha256_json({key: value for key, value in forged[0].items() if key != "record_sha256"})
        self.assertIn("native entity export has invalid source turn counters", "; ".join(self.failures(forged, actions)))

    def test_recomputed_outer_hashes_do_not_accept_malformed_path_state_evidence(self) -> None:
        records, actions = self.records()
        records[0] = self.record_with_complete_path_entity(actions[0])
        self.assertEqual([], self.failures(records, actions))

        corruptions = {
            "stable_id": (lambda entity, exports: entity.__setitem__("entity_id", 0), "invalid_stable_entity_id"),
            "queue": (lambda entity, exports: exports["entities"].__setitem__("turn_queue", []), "turn_queue_mismatch"),
            "order": (lambda entity, exports: entity["scheduler"].__setitem__("iteration_order", 1), "invalid_iteration_order"),
            "coordinate": (lambda entity, exports: entity.__setitem__("native_x", 12), "invalid_entity_coordinate"),
            "target": (lambda entity, exports: entity["path_state"].__setitem__("apparent_hero_native", {"x": "bad", "y": 8}), "invalid_apparent_target"),
            "track": (lambda entity, exports: entity["path_state"].__setitem__("mtrack_native", []), "invalid_mtrack"),
            "edog": (lambda entity, exports: entity["path_state"].__setitem__("edog", None), "missing_tame_edog"),
        }
        for name, (corrupt, expected) in corruptions.items():
            with self.subTest(name=name):
                forged = deepcopy(records)
                entity = forged[0]["exports"]["entities"]["entities"][0]
                corrupt(entity, forged[0]["exports"])
                # Simulate a malicious writer who recomputes every record
                # digest after altering the serialized native sidecar.
                forged[0] = record_from_exports(
                    fixture_id=self.fixture_id,
                    action=actions[0],
                    runtime=self.runtime,
                    exports=forged[0]["exports"],
                    controls=forged[0]["controls"],
                )
                self.assertIn(f"native path-state {expected}", "; ".join(self.failures(forged, actions)))

    def test_semantic_terrain_extension_is_backward_safe_but_rejects_partial_or_invalid_new_planes(self) -> None:
        records, actions = self.records()
        # Existing v1 sidecars omit the extension and remain valid.
        self.assertEqual([], self.failures(records, actions))

        partial = deepcopy(records)
        partial[0]["exports"]["map_fov"]["full_map_terrain_flags"] = []
        # Rebind the record so this is a shape/extension failure, not merely
        # a digest-tampering failure.
        rebuilt = record_from_exports(
            fixture_id=self.fixture_id,
            action=actions[0],
            runtime=self.runtime,
            exports=partial[0]["exports"],
            controls=partial[0]["controls"],
        )
        partial[0] = rebuilt
        failures = "; ".join(self.failures(partial, actions))
        self.assertIn("semantic terrain extension", failures)

        invalid = deepcopy(records)
        width, height = 79, 21
        invalid[0]["exports"]["map_fov"].update({
            "full_map_terrain_flags": [[32] * width for _ in range(height)],
            "full_map_terrain_horizontal": [[False] * width for _ in range(height)],
        })
        invalid[0] = record_from_exports(
            fixture_id=self.fixture_id,
            action=actions[0],
            runtime=self.runtime,
            exports=invalid[0]["exports"],
            controls=invalid[0]["controls"],
        )
        self.assertIn("five-bit", "; ".join(self.failures(invalid, actions)))

        digest_tampered = deepcopy(records)
        flags = [[0] * width for _ in range(height)]
        horizontal = [[False] * width for _ in range(height)]
        digest_tampered[0]["exports"]["map_fov"].update({
            "full_map_terrain_flags": flags,
            "full_map_terrain_horizontal": horizontal,
            "semantic_terrain_contract": {"source_only": True, "gold_implementation_eligible": False},
        })
        digest_tampered[0] = record_from_exports(
            fixture_id=self.fixture_id,
            action=actions[0],
            runtime=self.runtime,
            exports=digest_tampered[0]["exports"],
            controls=digest_tampered[0]["controls"],
        )
        self.assertIn("plane digest mismatch", "; ".join(self.failures(digest_tampered, actions)))

    def test_sidecar_is_not_a_level_dump_gold_or_score_input(self) -> None:
        # Keep this deliberately structural: the only live use is capture,
        # persistence, and oracle repeatability; all gold lanes receive task
        # level dumps and action rows, never the sidecar records.
        for function in (fuzz_nle_differential.causal_level_dump, fuzz_nle_differential.python_trace, fuzz_nle_differential.rust_trace, fuzz_nle_differential.lane_report):
            self.assertNotIn("native_pre_action_records", inspect.getsource(function))


if __name__ == "__main__":
    unittest.main()
