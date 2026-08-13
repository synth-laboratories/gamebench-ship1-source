from __future__ import annotations

import ctypes
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.nle_native_entities import (
    EXPECTED_DLEVEL_SIZE,
    EXPECTED_EDOG_SIZE,
    EXPECTED_MEXTRA_SIZE,
    EXPECTED_BINARY_SHA256,
    EXPECTED_LEVEL_MONLIST_OFFSET,
    EXPECTED_MONST_SIZE,
    EXPECTED_PERMONST_SIZE,
    EXPECTED_OBJ_SIZE,
    EXPECTED_RM_SIZE,
    NativeLevel,
    NativeEdog,
    NativeMextra,
    NativeMonst,
    NativeObj,
    NativePermonst,
    NativeRm,
    PinnedNleEntityReader,
    _assert_layout,
    _monster_species_rules,
    validate_native_entity_record,
    validate_native_presentation,
)
from scripts.nle_authoritative_entity_contract import validate_authoritative_entity_export


class NativeEntityLayoutTests(unittest.TestCase):
    def test_pinned_source_layout_is_explicit(self) -> None:
        self.assertEqual(EXPECTED_RM_SIZE, ctypes.sizeof(NativeRm))
        self.assertEqual(EXPECTED_MONST_SIZE, ctypes.sizeof(NativeMonst))
        self.assertEqual(EXPECTED_PERMONST_SIZE, ctypes.sizeof(NativePermonst))
        self.assertEqual(EXPECTED_OBJ_SIZE, ctypes.sizeof(NativeObj))
        self.assertEqual(EXPECTED_MEXTRA_SIZE, ctypes.sizeof(NativeMextra))
        self.assertEqual(EXPECTED_EDOG_SIZE, ctypes.sizeof(NativeEdog))
        self.assertEqual(EXPECTED_DLEVEL_SIZE, ctypes.sizeof(NativeLevel))
        self.assertEqual(EXPECTED_LEVEL_MONLIST_OFFSET, NativeLevel.monlist.offset)
        _assert_layout()

    def test_permonst_static_profile_exports_exact_attack_matrix(self) -> None:
        name = ctypes.create_string_buffer(b"grid bug")
        species = NativePermonst()
        species.mname = ctypes.cast(name, ctypes.c_void_p).value
        species.mlet = bytes([24])  # source class index for printable x
        species.mlevel = 0
        species.mmove = 12
        species.ac = 9
        species.mr = 48
        species._geno = 0x00B3  # frequency 3, no-corpse bit set
        species._cwt = 15
        species._cnutrit = 10
        species.mresists = 48
        raw_attacks = (2, 6, 1, 1) + (0,) * 20
        species._attacks = (ctypes.c_uint8 * 24)(*raw_attacks)

        rules = _monster_species_rules(species, 115)

        self.assertEqual("grid bug", rules["name"])
        self.assertEqual("nle_reset_permonst_static_profile_v2", rules["provenance"])
        self.assertEqual(0x00B3, rules["geno"])
        self.assertEqual(3, rules["generation_frequency"])
        self.assertEqual(15, rules["corpse_weight"])
        self.assertEqual(10, rules["corpse_nutrition"])
        self.assertTrue(rules["no_corpse"])
        self.assertEqual(
            {
                "armor_class": 9,
                "level": 0,
                "magic_resistance": 48,
                "resistances": 48,
                "attacks": [
                    {"slot": 0, "aatyp": 2, "adtyp": 6, "damn": 1, "damd": 1},
                    *[
                        {"slot": slot, "aatyp": 0, "adtyp": 0, "damn": 0, "damd": 0}
                        for slot in range(1, 6)
                    ],
                ],
                "attack_bytes_hex": bytes(raw_attacks).hex(),
                "provenance": "nle_reset_permonst_attack_profile_v1",
            },
            rules["combat"],
        )

    def test_species_rules_validator_accepts_frozen_legacy_flags_profile(self) -> None:
        name = ctypes.create_string_buffer(b"grid bug")
        species = NativePermonst()
        species.mname = ctypes.cast(name, ctypes.c_void_p).value
        species.mlet = bytes([24])  # source class index for printable x
        species.mmove = 12
        species._attacks = (ctypes.c_uint8 * 24)(2, 6, 1, 1, *([0] * 20))
        profile = _monster_species_rules(species, 115)
        profile.pop("combat")
        for field in ("geno", "generation_frequency", "corpse_weight", "corpse_nutrition", "no_corpse"):
            profile.pop(field)
        profile["provenance"] = "nle_reset_permonst_static_flags"
        record = {
            "schema": "gamebench.nethack.native_entity_snapshot.v1",
            "source_turn": {"moves": 1, "monstermoves": 1},
            "turn_queue": [1],
            "entities": [{
                "entity_id": 1,
                "species_id": 115,
                "species_rules": profile,
                "allegiance": "hostile",
                "x": 10,
                "y": 10,
                "native_x": 11,
                "hp": 1,
                "hp_max": 1,
                "scheduler": {
                    "iteration_order": 0,
                    "base_speed": 12,
                    "movement_points": 0,
                    "speed_state": 0,
                    "can_move": True,
                    "sleeping": False,
                    "fleeing": False,
                    "strategy": 0,
                    "special_cooldown": 0,
                },
                "underlay": {
                    "terrain_type": 1,
                    "terrain_memory_glyph": 2378,
                    "object_stack": [],
                    "object_stack_complete": True,
                },
            }],
        }
        self.assertEqual([], validate_native_entity_record(record))

    def test_species_rules_validator_rejects_inconsistent_population_metadata(self) -> None:
        name = ctypes.create_string_buffer(b"grid bug")
        species = NativePermonst()
        species.mname = ctypes.cast(name, ctypes.c_void_p).value
        species.mlet = bytes([24])
        species._geno = 0x00B3
        species._cwt = 15
        species._cnutrit = 10
        species._attacks = (ctypes.c_uint8 * 24)(2, 6, 1, 1, *([0] * 20))
        profile = _monster_species_rules(species, 115)
        profile["generation_frequency"] = 2
        record = {
            "schema": "gamebench.nethack.native_entity_snapshot.v1",
            "source_turn": {"moves": 1, "monstermoves": 1},
            "turn_queue": [1],
            "entities": [{
                "entity_id": 1,
                "species_id": 115,
                "species_rules": profile,
                "allegiance": "hostile",
                "x": 10,
                "y": 10,
                "native_x": 11,
                "hp": 1,
                "hp_max": 1,
                "scheduler": {
                    "iteration_order": 0,
                    "base_speed": 12,
                    "movement_points": 0,
                    "speed_state": 0,
                    "can_move": True,
                    "sleeping": False,
                    "fleeing": False,
                    "strategy": 0,
                    "special_cooldown": 0,
                },
                "underlay": {
                    "terrain_type": 1,
                    "terrain_memory_glyph": 2378,
                    "object_stack": [],
                    "object_stack_complete": True,
                },
            }],
        }
        self.assertTrue(validate_native_entity_record(record))

    def test_corrupted_pet_extension_layout_hard_fails(self) -> None:
        with patch("scripts.nle_native_entities.EXPECTED_EDOG_SIZE", 1):
            with self.assertRaisesRegex(RuntimeError, "edog size"):
                _assert_layout()

    def test_tame_pet_extension_never_guesses_from_an_unsafe_pointer(self) -> None:
        monster = NativeMonst()
        monster.mtame = 1
        flags = {"is_minion": False}
        with self.assertRaisesRegex(RuntimeError, "tame monster mextra"):
            PinnedNleEntityReader._edog_path_state(monster, flags)
        monster.mextra = 1
        with self.assertRaisesRegex(RuntimeError, "tame monster mextra"):
            PinnedNleEntityReader._edog_path_state(monster, flags)

    def test_live_snapshot_is_read_only_and_uses_stable_source_ids(self) -> None:
        if sys.platform != "darwin":
            self.skipTest("pinned native reader targets the macOS NLE wheel")
        try:
            import nle
            from nle import nethack
        except ModuleNotFoundError:
            self.skipTest("NLE unavailable")
        env = nle.env.NLE(character="val-hum-fem-law", observation_keys=("glyphs", "specials"), actions=tuple(nethack.ACTIONS), allow_all_modes=True, allow_all_yn_questions=True)
        try:
            env.seed(core=123, disp=456, reseed=False)
            observation = env.reset()
            reader = PinnedNleEntityReader(env.nethack)
            before = reader.snapshot().public_record()
            self.assertEqual(before, reader.snapshot().public_record())
            cells = reader.source_cells()
            self.assertEqual(79 * 21, len(cells))
            cell_index = {(cell["x"], cell["y"]): cell for cell in cells}
            ids = [entity["entity_id"] for entity in before["entities"]]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(ids, before["turn_queue"])
            self.assertEqual(EXPECTED_BINARY_SHA256, before["binary_sha256"])
            export = reader.snapshot().scheduler_export()
            gate = validate_authoritative_entity_export(export, expected_source_step=export["source_step"])
            self.assertEqual("eligible", gate["status"])
            self.assertFalse(gate["gold_scheduler_implementation_eligible"])
            crosscheck = validate_native_presentation(reader.snapshot(), observation, nethack)
            self.assertGreaterEqual(crosscheck["verified_public_pet_cells"], 1)
            for entity in before["entities"]:
                self.assertEqual(entity["native_x"] - 1, entity["x"])
                self.assertTrue(entity["underlay"]["object_stack_complete"])
                self.assertIn(entity["allegiance"], {"hostile", "peaceful", "tame"})
                self.assertEqual(entity["entity_id"], cell_index[(entity["x"], entity["y"])]["monster_id"])
                path = entity["path_state"]
                self.assertEqual({"x", "y"}, set(path["apparent_hero_native"]))
                self.assertEqual(4, len(path["mtrack_native"]))
                self.assertIn("strategy", path)
                self.assertIn("trap_seen_mask", path)
                self.assertIn("last_monster_move", path)
                self.assertIn("is_minion", path["status"])
                if entity["allegiance"] == "tame" and not path["status"]["is_minion"]:
                    self.assertIsInstance(path["edog"], dict)
                    self.assertEqual({"x", "y"}, set(path["edog"]["ogoal_native"]))
                else:
                    self.assertIsNone(path["edog"])
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
