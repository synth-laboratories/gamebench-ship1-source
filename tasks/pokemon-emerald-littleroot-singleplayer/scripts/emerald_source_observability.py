#!/usr/bin/env python3
"""Bounded, source-derived Pokémon Emerald memory observations.

The addresses and offsets in this module are for the matching USA/Europe ROM
only. Their derivation is recorded in
``fixtures/gold/emerald_source_observability.json``.  This module deliberately
returns raw facts rather than assigning story meaning to numeric variable
values or callback/task pointers.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any


ReadBytes = Callable[[int, int], bytes]

G_MAIN = 0x030022C0
G_SAVE_BLOCK1_PTR = 0x03005D8C
G_SAVE_BLOCK2_PTR = 0x03005D90
G_FIELD_CALLBACK = 0x03005DAC
G_FIELD_CALLBACK2 = 0x03005DB0
G_TASKS = 0x03005E00
G_PALETTE_FADE = 0x02037FD4

GLOBAL_SCRIPT_CONTEXT_STATUS = 0x03000E38
GLOBAL_SCRIPT_CONTEXT = 0x03000E40
IMMEDIATE_SCRIPT_CONTEXT = 0x03000EB8

SAVE_BLOCK1_SIZE = 0x3D88
SAVE_BLOCK1_FLAGS_OFFSET = 0x1270
SAVE_BLOCK1_VARS_OFFSET = 0x139C
SAVE_BLOCK2_PLAYER_GENDER_OFFSET = 0x08

SCRIPT_CONTEXT_SIZE = 0x74
TASK_COUNT = 16
TASK_SIZE = 0x28
PALETTE_FADE_SIZE = 0x0C

STORY_VARS = {
    "littleroot_town_state": 0x4050,
    "littleroot_rival_state": 0x408D,
    "littleroot_intro_state": 0x4092,
}

STORY_FLAGS = {
    "set_wall_clock": 0x051,
    "rescued_birch": 0x052,
    "hide_brendans_house_2f_poke_ball": 0x331,
    "hide_mays_house_2f_poke_ball": 0x332,
    "pokemon_get": 0x860,
    "pokedex_get": 0x861,
    "visited_littleroot_town": 0x86F,
    "running_shoes_received": 0x8C0,
    "received_pokedex_from_birch": 0x8E4,
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _u8(read: ReadBytes, address: int) -> int:
    return read(address, 1)[0]


def _u16(read: ReadBytes, address: int) -> int:
    return int.from_bytes(read(address, 2), "little")


def _u32(read: ReadBytes, address: int) -> int:
    return int.from_bytes(read(address, 4), "little")


def _ptr(value: int) -> str:
    return f"0x{value:08x}"


def _require_ewram_pointer(value: int, name: str) -> None:
    if not 0x02000000 <= value < 0x02040000:
        raise RuntimeError(f"invalid Emerald {name} value: 0x{value:08x}")


def _script_context(read: ReadBytes, address: int) -> dict[str, Any]:
    raw = read(address, SCRIPT_CONTEXT_SIZE)
    return {
        "stack_depth": raw[0],
        "mode": raw[1],
        "comparison_result": raw[2],
        "native_ptr": _ptr(int.from_bytes(raw[4:8], "little")),
        "script_ptr": _ptr(int.from_bytes(raw[8:12], "little")),
        "cmd_table_ptr": _ptr(int.from_bytes(raw[0x5C:0x60], "little")),
        "cmd_table_end_ptr": _ptr(int.from_bytes(raw[0x60:0x64], "little")),
        "raw_sha256": _sha256(raw),
    }


def _tasks(read: ReadBytes) -> dict[str, Any]:
    active: list[dict[str, Any]] = []
    for slot in range(TASK_COUNT):
        raw = read(G_TASKS + slot * TASK_SIZE, TASK_SIZE)
        if raw[4] == 0:
            continue
        active.append(
            {
                "slot": slot,
                "func_ptr": _ptr(int.from_bytes(raw[0:4], "little")),
                "priority": raw[7],
                "prev": raw[5],
                "next": raw[6],
                "data_sha256": _sha256(raw[8:]),
            }
        )
    return {
        "count": len(active),
        "entries": active,
        "fingerprint_sha256": _sha256(
            canonical_json(active).encode("utf-8")
        ),
    }


def observe_source_state(read: ReadBytes) -> dict[str, Any]:
    """Read deterministic, bounded source facts from a loaded Emerald core."""
    save_block1 = _u32(read, G_SAVE_BLOCK1_PTR)
    save_block2 = _u32(read, G_SAVE_BLOCK2_PTR)
    _require_ewram_pointer(save_block1, "gSaveBlock1Ptr")
    _require_ewram_pointer(save_block2, "gSaveBlock2Ptr")

    story_vars = {
        name: _u16(
            read,
            save_block1 + SAVE_BLOCK1_VARS_OFFSET + 2 * (var_id - 0x4000),
        )
        for name, var_id in STORY_VARS.items()
    }
    story_flags = {
        name: bool(
            _u8(read, save_block1 + SAVE_BLOCK1_FLAGS_OFFSET + flag_id // 8)
            & (1 << (flag_id % 8))
        )
        for name, flag_id in STORY_FLAGS.items()
    }

    palette_raw = read(G_PALETTE_FADE, PALETTE_FADE_SIZE)
    palette_fade = {
        # These masks are visible in the matching compiled palette.o:
        # active is byte 7 bit 7; mode is byte 9 bits 0..1.
        "active": bool(palette_raw[7] & 0x80),
        "mode": palette_raw[9] & 0x03,
        "delay_counter": palette_raw[4] & 0x3F,
        "raw_hex": palette_raw.hex(),
        "raw_sha256": _sha256(palette_raw),
    }

    return {
        "save_block1_ptr": _ptr(save_block1),
        "save_block2_ptr": _ptr(save_block2),
        "player_gender": _u8(
            read, save_block2 + SAVE_BLOCK2_PLAYER_GENDER_OFFSET
        ),
        "story_vars": story_vars,
        "story_flags": story_flags,
        "script_contexts": {
            "global_status": _u8(read, GLOBAL_SCRIPT_CONTEXT_STATUS),
            "global": _script_context(read, GLOBAL_SCRIPT_CONTEXT),
            "immediate": _script_context(read, IMMEDIATE_SCRIPT_CONTEXT),
        },
        "palette_fade": palette_fade,
        "active_tasks": _tasks(read),
        "callbacks": {
            "main_callback1": _ptr(_u32(read, G_MAIN)),
            "main_callback2": _ptr(_u32(read, G_MAIN + 4)),
            "main_saved_callback": _ptr(_u32(read, G_MAIN + 8)),
            "field_callback": _ptr(_u32(read, G_FIELD_CALLBACK)),
            "field_callback2": _ptr(_u32(read, G_FIELD_CALLBACK2)),
        },
    }
