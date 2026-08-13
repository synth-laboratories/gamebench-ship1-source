#!/usr/bin/env python3
"""ROM-free tests for source-derived Emerald observability."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import emerald_source_observability as obs


class FakeMemory:
    def __init__(self) -> None:
        self.data: dict[int, int] = {}

    def write(self, address: int, value: bytes) -> None:
        self.data.update({address + offset: byte for offset, byte in enumerate(value)})

    def u8(self, address: int, value: int) -> None:
        self.write(address, bytes([value]))

    def u16(self, address: int, value: int) -> None:
        self.write(address, value.to_bytes(2, "little"))

    def u32(self, address: int, value: int) -> None:
        self.write(address, value.to_bytes(4, "little"))

    def read(self, address: int, length: int) -> bytes:
        return bytes(self.data.get(address + offset, 0) for offset in range(length))


class SourceObservabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.memory = FakeMemory()
        self.sb1 = 0x02001000
        self.sb2 = 0x02008000
        self.memory.u32(obs.G_SAVE_BLOCK1_PTR, self.sb1)
        self.memory.u32(obs.G_SAVE_BLOCK2_PTR, self.sb2)

    def test_story_addresses_gender_and_flags_follow_source_formulas(self) -> None:
        self.memory.u8(self.sb2 + 8, 1)
        expected_vars = {
            "littleroot_town_state": 0x1234,
            "littleroot_rival_state": 3,
            "littleroot_intro_state": 7,
        }
        for name, value in expected_vars.items():
            var_id = obs.STORY_VARS[name]
            self.memory.u16(
                self.sb1 + 0x139C + 2 * (var_id - 0x4000), value
            )
        for name in ("rescued_birch", "pokedex_get", "running_shoes_received"):
            flag_id = obs.STORY_FLAGS[name]
            address = self.sb1 + 0x1270 + flag_id // 8
            self.memory.u8(
                address, self.memory.read(address, 1)[0] | (1 << (flag_id % 8))
            )

        result = obs.observe_source_state(self.memory.read)
        self.assertEqual(1, result["player_gender"])
        self.assertEqual(expected_vars, result["story_vars"])
        self.assertTrue(result["story_flags"]["rescued_birch"])
        self.assertTrue(result["story_flags"]["pokedex_get"])
        self.assertTrue(result["story_flags"]["running_shoes_received"])
        self.assertFalse(result["story_flags"]["pokemon_get"])

    def test_script_contexts_callbacks_and_palette_are_raw_facts(self) -> None:
        self.memory.u8(obs.GLOBAL_SCRIPT_CONTEXT_STATUS, 2)
        context = bytearray(obs.SCRIPT_CONTEXT_SIZE)
        context[0:3] = bytes([4, 1, 5])
        context[4:8] = (0x08001235).to_bytes(4, "little")
        context[8:12] = (0x08123456).to_bytes(4, "little")
        context[0x5C:0x60] = (0x081DB67C).to_bytes(4, "little")
        context[0x60:0x64] = (0x081DBA08).to_bytes(4, "little")
        self.memory.write(obs.GLOBAL_SCRIPT_CONTEXT, context)
        palette = bytearray(obs.PALETTE_FADE_SIZE)
        palette[4] = 0x2A
        palette[7] = 0x80
        palette[9] = 0x03
        self.memory.write(obs.G_PALETTE_FADE, palette)
        self.memory.u32(obs.G_MAIN, 0x08000101)
        self.memory.u32(obs.G_MAIN + 4, 0x08000201)
        self.memory.u32(obs.G_FIELD_CALLBACK, 0x08000301)

        result = obs.observe_source_state(self.memory.read)
        self.assertEqual(2, result["script_contexts"]["global_status"])
        self.assertEqual(4, result["script_contexts"]["global"]["stack_depth"])
        self.assertEqual(
            "0x08123456", result["script_contexts"]["global"]["script_ptr"]
        )
        self.assertEqual(
            "0x08000101", result["callbacks"]["main_callback1"]
        )
        self.assertTrue(result["palette_fade"]["active"])
        self.assertEqual(3, result["palette_fade"]["mode"])
        self.assertEqual(42, result["palette_fade"]["delay_counter"])

    def test_tasks_are_bounded_and_fingerprint_is_deterministic(self) -> None:
        for slot in (0, 7, 15):
            address = obs.G_TASKS + slot * obs.TASK_SIZE
            self.memory.u32(address, 0x08001001 + slot * 2)
            self.memory.u8(address + 4, 1)
            self.memory.u8(address + 7, slot)
            self.memory.u16(address + 8, slot * 100)
        first = obs.observe_source_state(self.memory.read)["active_tasks"]
        second = obs.observe_source_state(self.memory.read)["active_tasks"]
        self.assertEqual(3, first["count"])
        self.assertEqual([0, 7, 15], [item["slot"] for item in first["entries"]])
        self.assertEqual(first["fingerprint_sha256"], second["fingerprint_sha256"])

        # A change to bounded task data must change the fingerprint.
        self.memory.u16(obs.G_TASKS + 7 * obs.TASK_SIZE + 8, 701)
        changed = obs.observe_source_state(self.memory.read)["active_tasks"]
        self.assertNotEqual(first["fingerprint_sha256"], changed["fingerprint_sha256"])

    def test_invalid_save_pointer_fails_closed(self) -> None:
        self.memory.u32(obs.G_SAVE_BLOCK1_PTR, 0x08000000)
        with self.assertRaisesRegex(RuntimeError, "gSaveBlock1Ptr"):
            obs.observe_source_state(self.memory.read)

    def test_documented_symbols_and_ids_match_decoder_constants(self) -> None:
        manifest = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "fixtures/gold/emerald_source_observability.json"
            ).read_text(encoding="utf-8")
        )
        symbols = manifest["symbols"]
        self.assertEqual(obs.G_MAIN, int(symbols["gMain"], 16))
        self.assertEqual(obs.G_PALETTE_FADE, int(symbols["gPaletteFade"], 16))
        self.assertEqual(obs.G_TASKS, int(symbols["gTasks"], 16))
        self.assertEqual(
            obs.GLOBAL_SCRIPT_CONTEXT,
            int(symbols["sGlobalScriptContext"], 16),
        )
        documented_vars = {
            key.removeprefix("VAR_").lower(): int(value, 16)
            for key, value in manifest["variables"].items()
        }
        self.assertEqual(obs.STORY_VARS, documented_vars)

    def test_optional_ppu_provenance_is_bounded_and_hash_first(self) -> None:
        manifest = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "fixtures/gold/emerald_source_observability.json"
            ).read_text(encoding="utf-8")
        )
        schema = manifest["optional_ppu_capture_schema"]
        self.assertEqual("gamebench.pokemon_emerald.ppu_provenance.v1", schema["schema"])
        self.assertIn("opt-in", schema["emission"])
        self.assertIn("never included", schema["emission"])
        self.assertEqual("the same post-load or post-step VBlank used for the RGB frame", schema["frame_boundary"])
        self.assertEqual(
            {"dispcnt", "bgcnt", "bg_offsets", "window"},
            {entry["name"] for entry in schema["registers"]},
        )
        ranges = {entry["name"]: entry for entry in schema["memory_ranges"]}
        self.assertEqual({"bg_vram", "bg_palette", "obj_vram", "obj_palette", "oam"}, set(ranges))
        self.assertTrue(all(entry["default"] == "sha256" for entry in ranges.values()))
        self.assertEqual(65536, ranges["bg_vram"]["bytes"])
        self.assertEqual(512, ranges["bg_palette"]["bytes"])
        self.assertEqual(1024, ranges["oam"]["bytes"])
        self.assertIn("raw bytes only", schema["raw_payload_policy"])


if __name__ == "__main__":
    unittest.main()
