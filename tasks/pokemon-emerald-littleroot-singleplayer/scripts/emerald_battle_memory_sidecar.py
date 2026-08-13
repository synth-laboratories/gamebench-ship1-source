#!/usr/bin/env python3
"""Hash-bound Pokémon Emerald battle-memory observation sidecar.

This script runs inside the already-pinned v9 mGBA image but is not part of
the JSONL adapter or its image. The launcher mounts this file and the symbol
manifest read-only, and the receipt binds both hashes explicitly.
"""

from __future__ import annotations

import gc
import hashlib
import importlib.metadata
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import mgba.core
import mgba.log


SCHEMA = "gamebench.pokemon_emerald.battle_memory_sidecar.v1"
G_BATTLE_CONTROLLER_EXEC_FLAGS = 0x02024068
G_BATTLERS_COUNT = 0x0202406C
G_BATTLER_POSITIONS = 0x02024076
G_CURRENT_TURN_ACTION_NUMBER = 0x02024082
G_CURRENT_ACTION_FUNC_ID = 0x02024083
G_BATTLE_MONS = 0x02024084
G_BATTLE_OUTCOME = 0x0202433A
G_BATTLE_MAIN_FUNC = 0x03005D04
BATTLE_MON_SIZE = 0x58
MAX_BATTLERS = 4


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_mon(raw: bytes, battler: int, position: int) -> dict[str, Any]:
    u16 = lambda offset: int.from_bytes(raw[offset:offset + 2], "little")
    u32 = lambda offset: int.from_bytes(raw[offset:offset + 4], "little")
    return {
        "battler": battler,
        "position": position,
        "species": u16(0x00),
        "attack": u16(0x02),
        "defense": u16(0x04),
        "speed": u16(0x06),
        "sp_attack": u16(0x08),
        "sp_defense": u16(0x0A),
        "moves": [u16(0x0C + 2 * index) for index in range(4)],
        "iv_word": u32(0x14),
        "stat_stages": [
            int.from_bytes(raw[0x18 + index:0x19 + index], "little", signed=True)
            for index in range(8)
        ],
        "ability": raw[0x20],
        "types": [raw[0x21], raw[0x22]],
        "pp": list(raw[0x24:0x28]),
        "hp": u16(0x28),
        "level": raw[0x2A],
        "friendship": raw[0x2B],
        "max_hp": u16(0x2C),
        "item": u16(0x2E),
        "nickname_hex": raw[0x30:0x3B].hex(),
        "pp_bonuses": raw[0x3B],
        "ot_name_hex": raw[0x3C:0x44].hex(),
        "experience": u32(0x44),
        "personality": u32(0x48),
        "status1": u32(0x4C),
        "status2": u32(0x50),
        "ot_id": u32(0x54),
        "raw_sha256": sha256_bytes(raw),
    }


def main() -> int:
    mgba.log.silence()
    rom_path = Path(os.environ["EMERALD_BATTLE_ROM_PATH"])
    state_path = Path(os.environ["EMERALD_BATTLE_STATE_PATH"])
    manifest_path = Path(os.environ["EMERALD_BATTLE_SYMBOL_MANIFEST_PATH"])
    expected_script_sha = os.environ["EMERALD_BATTLE_SCRIPT_SHA256"]
    expected_manifest_sha = os.environ["EMERALD_BATTLE_SYMBOL_MANIFEST_SHA256"]
    script_sha = sha256_file(Path(__file__))
    manifest_sha = sha256_file(manifest_path)
    if script_sha != expected_script_sha:
        raise RuntimeError("mounted battle sidecar script hash mismatch")
    if manifest_sha != expected_manifest_sha:
        raise RuntimeError("mounted battle symbol manifest hash mismatch")

    temp_dir = Path(tempfile.mkdtemp(prefix="emerald-battle-sidecar-"))
    core = None
    try:
        copied_rom = temp_dir / "rom.gba"
        shutil.copyfile(rom_path, copied_rom)
        core = mgba.core.load_path(str(copied_rom))
        if core is None:
            raise RuntimeError("mGBA could not identify ROM")
        core.autoload_save()
        core.reset()
        loaded = core.load_raw_state(state_path.read_bytes())
        if loaded is False:
            raise RuntimeError("mGBA rejected state")
        core.run_frame()

        read = lambda address, length: bytes(
            core.memory.u8[address + offset] for offset in range(length)
        )
        count = read(G_BATTLERS_COUNT, 1)[0]
        if count > MAX_BATTLERS:
            raise RuntimeError(f"invalid gBattlersCount: {count}")
        positions = list(read(G_BATTLER_POSITIONS, MAX_BATTLERS))
        mons = [
            parse_mon(
                read(G_BATTLE_MONS + battler * BATTLE_MON_SIZE, BATTLE_MON_SIZE),
                battler,
                positions[battler],
            )
            for battler in range(count)
        ]
        receipt: dict[str, Any] = {
            "schema": SCHEMA,
            "identity": {
                "rom_sha256": sha256_file(rom_path),
                "state_sha256": sha256_file(state_path),
                "container_image_id": os.environ["EMERALD_BATTLE_IMAGE_ID"],
                "script_sha256": script_sha,
                "symbol_manifest_sha256": manifest_sha,
                "libmgba_package_version": "0.10.5+dfsg-1",
                "python_mgba_version": importlib.metadata.version("mgba"),
                "initial_state_advance_frames": 1,
            },
            "battle": {
                "battlers_count": count,
                "battler_positions": positions,
                "controller_exec_flags": int.from_bytes(
                    read(G_BATTLE_CONTROLLER_EXEC_FLAGS, 4), "little"
                ),
                "current_turn_action_number": read(
                    G_CURRENT_TURN_ACTION_NUMBER, 1
                )[0],
                "current_action_func_id": read(G_CURRENT_ACTION_FUNC_ID, 1)[0],
                "battle_outcome": read(G_BATTLE_OUTCOME, 1)[0],
                "battle_main_func_ptr": (
                    f"0x{int.from_bytes(read(G_BATTLE_MAIN_FUNC, 4), 'little'):08x}"
                ),
                "mons": mons,
            },
        }
        receipt["receipt_sha256"] = sha256_bytes(
            canonical_json(receipt).encode("utf-8")
        )
        print(canonical_json(receipt))
    finally:
        core = None
        gc.collect()
        shutil.rmtree(temp_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
