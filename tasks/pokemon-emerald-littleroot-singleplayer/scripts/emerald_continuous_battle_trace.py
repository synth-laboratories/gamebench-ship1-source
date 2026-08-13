#!/usr/bin/env python3
"""Continuous, no-reload Emerald battle-memory trace inside pinned mGBA v8."""

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


SCHEMA = "gamebench.pokemon_emerald.continuous_battle_trace.v1"
VALID_BUTTONS = {
    "a", "b", "select", "start", "right", "left", "up", "down", "r", "l",
}
MAX_VBLANKS = 20000
G_MAIN = 0x030022C0
G_BATTLE_MAIN_FUNC = 0x03005D04
G_BATTLE_CONTROLLER_EXEC_FLAGS = 0x02024068
G_BATTLERS_COUNT = 0x0202406C
G_BATTLER_POSITIONS = 0x02024076
G_CURRENT_TURN_ACTION_NUMBER = 0x02024082
G_CURRENT_ACTION_FUNC_ID = 0x02024083
G_BATTLE_MONS = 0x02024084
G_BATTLE_OUTCOME = 0x0202433A
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


def expand_tape(tape: Any) -> tuple[list[list[str]], dict[int, list[str]]]:
    if not isinstance(tape, dict) or not isinstance(tape.get("program"), list):
        raise ValueError("tape must contain a program list")
    ticks: list[list[str]] = []
    markers: dict[int, list[str]] = {}
    for index, segment in enumerate(tape["program"]):
        if not isinstance(segment, dict):
            raise ValueError(f"program[{index}] must be an object")
        buttons = segment.get("buttons", [])
        frames = segment.get("frames")
        if (
            not isinstance(buttons, list)
            or not all(isinstance(button, str) for button in buttons)
            or len(buttons) != len(set(buttons))
            or set(buttons) - VALID_BUTTONS
        ):
            raise ValueError(f"program[{index}] has invalid buttons")
        if not isinstance(frames, int) or frames < 1:
            raise ValueError(f"program[{index}] frames must be positive")
        ticks.extend([buttons] * frames)
        marker = segment.get("marker")
        if marker is not None:
            if not isinstance(marker, str) or not marker:
                raise ValueError(f"program[{index}] marker must be text")
            markers.setdefault(len(ticks), []).append(marker)
    for index, marker in enumerate(tape.get("markers", [])):
        if (
            not isinstance(marker, dict)
            or not isinstance(marker.get("vblank"), int)
            or not isinstance(marker.get("label"), str)
            or not marker["label"]
        ):
            raise ValueError(f"markers[{index}] is malformed")
        vblank = marker["vblank"]
        if not 0 <= vblank <= len(ticks):
            raise ValueError(f"markers[{index}] is outside tape")
        markers.setdefault(vblank, []).append(marker["label"])
    if len(ticks) > MAX_VBLANKS:
        raise ValueError(f"tape exceeds {MAX_VBLANKS} VBlanks")
    return ticks, {key: sorted(set(value)) for key, value in markers.items()}


def parse_mon(raw: bytes, battler: int, position: int) -> dict[str, Any]:
    u16 = lambda offset: int.from_bytes(raw[offset:offset + 2], "little")
    u32 = lambda offset: int.from_bytes(raw[offset:offset + 4], "little")
    return {
        "battler": battler,
        "position": position,
        "species": u16(0x00),
        "stats": {
            "attack": u16(0x02), "defense": u16(0x04), "speed": u16(0x06),
            "sp_attack": u16(0x08), "sp_defense": u16(0x0A),
        },
        "moves": [u16(0x0C + 2 * index) for index in range(4)],
        "stat_stages": [
            int.from_bytes(raw[0x18 + index:0x19 + index], "little", signed=True)
            for index in range(8)
        ],
        "ability": raw[0x20],
        "types": [raw[0x21], raw[0x22]],
        "pp": list(raw[0x24:0x28]),
        "hp": u16(0x28),
        "level": raw[0x2A],
        "max_hp": u16(0x2C),
        "item": u16(0x2E),
        "status1": u32(0x4C),
        "status2": u32(0x50),
        "raw_sha256": sha256_bytes(raw),
    }


def sample(read: Any, vblank: int, buttons: list[str], markers: list[str]) -> dict[str, Any]:
    count = read(G_BATTLERS_COUNT, 1)[0]
    if count > MAX_BATTLERS:
        raise RuntimeError(f"invalid gBattlersCount: {count}")
    positions = list(read(G_BATTLER_POSITIONS, MAX_BATTLERS))
    pointer = lambda address: f"0x{int.from_bytes(read(address, 4), 'little'):08x}"
    return {
        "vblank": vblank,
        "buttons": buttons,
        "markers": markers,
        "battle": {
            "battlers_count": count,
            "battler_positions": positions,
            "controller_exec_flags": int.from_bytes(
                read(G_BATTLE_CONTROLLER_EXEC_FLAGS, 4), "little"
            ),
            "current_turn_action_number": read(G_CURRENT_TURN_ACTION_NUMBER, 1)[0],
            "current_action_func_id": read(G_CURRENT_ACTION_FUNC_ID, 1)[0],
            "battle_outcome": read(G_BATTLE_OUTCOME, 1)[0],
            "battle_main_func_ptr": pointer(G_BATTLE_MAIN_FUNC),
            "mons": [
                parse_mon(
                    read(G_BATTLE_MONS + battler * BATTLE_MON_SIZE, BATTLE_MON_SIZE),
                    battler,
                    positions[battler],
                )
                for battler in range(count)
            ],
        },
        "callbacks": {
            "main_callback1": pointer(G_MAIN),
            "main_callback2": pointer(G_MAIN + 4),
            "main_saved_callback": pointer(G_MAIN + 8),
        },
    }


def main() -> int:
    mgba.log.silence()
    rom = Path(os.environ["EMERALD_TRACE_ROM_PATH"])
    state = Path(os.environ["EMERALD_TRACE_STATE_PATH"])
    tape_path = Path(os.environ["EMERALD_TRACE_TAPE_PATH"])
    manifest = Path(os.environ["EMERALD_TRACE_SYMBOL_MANIFEST_PATH"])
    output = Path(os.environ["EMERALD_TRACE_TERMINAL_STATE_PATH"])
    script_sha = sha256_file(Path(__file__))
    manifest_sha = sha256_file(manifest)
    if script_sha != os.environ["EMERALD_TRACE_SCRIPT_SHA256"]:
        raise RuntimeError("continuous trace script hash mismatch")
    if manifest_sha != os.environ["EMERALD_TRACE_SYMBOL_MANIFEST_SHA256"]:
        raise RuntimeError("battle symbol manifest hash mismatch")
    tape = json.loads(tape_path.read_text(encoding="utf-8"))
    ticks, markers = expand_tape(tape)

    temp_dir = Path(tempfile.mkdtemp(prefix="emerald-continuous-battle-"))
    core = None
    try:
        copied_rom = temp_dir / "rom.gba"
        shutil.copyfile(rom, copied_rom)
        core = mgba.core.load_path(str(copied_rom))
        if core is None:
            raise RuntimeError("mGBA could not identify ROM")
        core.autoload_save()
        core.reset()
        if core.load_raw_state(state.read_bytes()) is False:
            raise RuntimeError("mGBA rejected input state")
        core.run_frame()
        read = lambda address, length: bytes(
            core.memory.u8[address + offset] for offset in range(length)
        )
        key_map = {
            "a": core.KEY_A, "b": core.KEY_B, "select": core.KEY_SELECT,
            "start": core.KEY_START, "right": core.KEY_RIGHT, "left": core.KEY_LEFT,
            "up": core.KEY_UP, "down": core.KEY_DOWN, "r": core.KEY_R, "l": core.KEY_L,
        }
        samples = [sample(read, 0, [], markers.get(0, []))]
        for vblank, buttons in enumerate(ticks, start=1):
            core.set_keys(*(key_map[button] for button in buttons))
            core.run_frame()
            core.set_keys()
            samples.append(sample(read, vblank, buttons, markers.get(vblank, [])))

        if output.exists():
            raise FileExistsError(f"refusing to overwrite terminal state: {output}")
        raw_state = bytes(core.save_raw_state())
        with output.open("xb") as destination:
            destination.write(raw_state)
            destination.flush()
            os.fsync(destination.fileno())
        receipt: dict[str, Any] = {
            "schema": SCHEMA,
            "identity": {
                "rom_sha256": sha256_file(rom),
                "input_state_sha256": sha256_file(state),
                "terminal_state_sha256": sha256_bytes(raw_state),
                "container_image_id": os.environ["EMERALD_TRACE_IMAGE_ID"],
                "script_sha256": script_sha,
                "symbol_manifest_sha256": manifest_sha,
                "tape_sha256": sha256_file(tape_path),
                "libmgba_package_version": "0.10.5+dfsg-1",
                "python_mgba_version": importlib.metadata.version("mgba"),
                "initial_state_advance_frames": 1,
                "core_load_count": 1,
                "intermediate_reload_count": 0,
            },
            "tape": {
                "id": tape.get("id"),
                "vblank_count": len(ticks),
                "marker_count": sum(len(value) for value in markers.values()),
            },
            "terminal_state_path": str(output),
            "sample_count": len(samples),
            "samples": samples,
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
