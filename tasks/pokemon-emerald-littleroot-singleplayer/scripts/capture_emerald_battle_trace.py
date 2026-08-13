#!/usr/bin/env python3
"""Replay one continuous Emerald battle tape in the pinned mGBA oracle.

The host side authenticates the ROM, starting checkpoint, and container image.
The container loads the checkpoint exactly once, samples source battle memory
at every program-segment boundary, and writes one terminal snapshot.  It never
uses intermediate save states, so RNG, PP, HP, callbacks, and story effects
belong to one uninterrupted emulator execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

IMAGE = "gamebench-mgba-oracle:0.10.5-9"
IMAGE_ID = "sha256:5995357b864e56df0715730a0ec2735d1a3f6af73d0bd90b87ee1b4f8bd7e0ed"
SCHEMA = "gamebench.pokemon_emerald.continuous_battle_trace.v1"
BATTLE_MON_BASE = 0x02024084
BATTLE_MON_SIZE = 0x58
BATTLE_CALLBACKS = ("0x08039ef1", "0x08038421")
SAVE_BLOCK1_PTR = 0x03005D8C
SAVE_VARS_OFFSET = 0x139C
SAVE_FLAGS_OFFSET = 0x1270
FLAG_DEFEATED_RIVAL_ROUTE103 = 0x082
FLAG_HIDE_ROUTE103_RIVAL = 0x2D3
FLAG_HIDE_LITTLEROOT_LAB_RIVAL = 0x379
FLAG_HIDE_OLDALE_RIVAL = 0x3D3
VAR_BIRCH_LAB_STATE = 0x4084
VAR_LITTLEROOT_RIVAL_STATE = 0x408D
VAR_OLDALE_RIVAL_STATE = 0x40C7
VALID_BUTTONS = {
    "a", "b", "select", "start", "right", "left", "up", "down", "r", "l"
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_once(path: Path, value: bytes) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence artifact: {path}")
    with path.open("xb") as output:
        output.write(value)
        output.flush()
        os.fsync(output.fileno())


def checked_program(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("program"), list):
        raise RuntimeError("battle tape must be an object with a program list")
    program: list[dict[str, Any]] = []
    total = 0
    for index, segment in enumerate(raw["program"]):
        if not isinstance(segment, dict):
            raise RuntimeError(f"program[{index}] must be an object")
        buttons = segment.get("buttons", [])
        frames = segment.get("frames")
        marker = segment.get("marker", f"segment_{index:03d}")
        if (
            not isinstance(buttons, list)
            or not all(isinstance(button, str) for button in buttons)
            or len(buttons) != len(set(buttons))
            or set(buttons) - VALID_BUTTONS
        ):
            raise RuntimeError(f"program[{index}] has invalid buttons")
        if not isinstance(frames, int) or frames < 1:
            raise RuntimeError(f"program[{index}].frames must be positive")
        if not isinstance(marker, str) or not marker:
            raise RuntimeError(f"program[{index}].marker must be a non-empty string")
        total += frames
        if total > 20_000:
            raise RuntimeError("continuous battle tape is bounded to 20,000 VBlanks")
        program.append({"buttons": buttons, "frames": frames, "marker": marker})
    return raw, program


def require_subset(expected: Any, actual: Any, path: str) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise RuntimeError(f"{path} expected an object")
        for key, value in expected.items():
            if key not in actual:
                raise RuntimeError(f"{path}.{key} is missing")
            require_subset(value, actual[key], f"{path}.{key}")
        return
    if expected != actual:
        raise RuntimeError(f"{path} mismatch: expected {expected!r}, got {actual!r}")


def validate_terminal(expected: dict[str, Any], sample: dict[str, Any]) -> None:
    require_subset(expected.get("callbacks", {}), sample["callbacks"], "callbacks")
    require_subset(expected.get("position", {}), sample["position"], "position")
    require_subset(expected.get("story", {}), sample["story"], "story")
    battlers = expected.get("battlers", {})
    if not isinstance(battlers, dict):
        raise RuntimeError("terminal_expectations.battlers must be an object")
    for name, value in battlers.items():
        if name not in {"battler0", "battler1"}:
            raise RuntimeError(f"unsupported terminal battler key: {name}")
        require_subset(value, sample["battlers"][int(name[-1])], name)


def u16(core: Any, address: int) -> int:
    return core.memory.u8[address] | (core.memory.u8[address + 1] << 8)


def u32(core: Any, address: int) -> int:
    return sum(core.memory.u8[address + index] << (8 * index) for index in range(4))


def battle_mon(core: Any, battler: int) -> dict[str, Any]:
    address = BATTLE_MON_BASE + battler * BATTLE_MON_SIZE
    return {
        "species": u16(core, address),
        "attack": u16(core, address + 0x02),
        "defense": u16(core, address + 0x04),
        "speed": u16(core, address + 0x06),
        "sp_attack": u16(core, address + 0x08),
        "sp_defense": u16(core, address + 0x0A),
        "moves": [u16(core, address + 0x0C + 2 * index) for index in range(4)],
        "stat_stages": [core.memory.u8[address + 0x18 + index] for index in range(8)],
        "pp": [core.memory.u8[address + 0x24 + index] for index in range(4)],
        "hp": u16(core, address + 0x28),
        "level": core.memory.u8[address + 0x2A],
        "max_hp": u16(core, address + 0x2C),
        "experience": u32(core, address + 0x44),
        "status1": u32(core, address + 0x4C),
        "status2": u32(core, address + 0x50),
    }


def source_sample(core: Any, frame: int, marker: str, buttons: list[str]) -> dict[str, Any]:
    block = core.memory.u32[SAVE_BLOCK1_PTR]
    if not 0x02000000 <= block < 0x02040000:
        raise RuntimeError(f"invalid gSaveBlock1Ptr 0x{block:08x}")

    def var(var_id: int) -> int:
        return u16(core, block + SAVE_VARS_OFFSET + 2 * (var_id - 0x4000))

    def flag(flag_id: int) -> bool:
        value = core.memory.u8[block + SAVE_FLAGS_OFFSET + flag_id // 8]
        return bool(value & (1 << (flag_id % 8)))

    callbacks = [
        f"0x{core.memory.u32[0x030022C0]:08x}",
        f"0x{core.memory.u32[0x030022C4]:08x}",
    ]
    raw = {
        "frame": frame,
        "marker": marker,
        "buttons": buttons,
        "callbacks": {
            "main_callback1": callbacks[0],
            "main_callback2": callbacks[1],
            "battle_owned": tuple(callbacks) == BATTLE_CALLBACKS,
        },
        "position": {
            "map_group": core.memory.s8[block + 4],
            "map_number": core.memory.s8[block + 5],
            "player_x": core.memory.s16[block],
            "player_y": core.memory.s16[block + 2],
        },
        "battlers": [battle_mon(core, 0), battle_mon(core, 1)],
        "story": {
            "vars": {
                "birch_lab_state": var(VAR_BIRCH_LAB_STATE),
                "littleroot_rival_state": var(VAR_LITTLEROOT_RIVAL_STATE),
                "oldale_rival_state": var(VAR_OLDALE_RIVAL_STATE),
            },
            "flags": {
                "defeated_rival_route103": flag(FLAG_DEFEATED_RIVAL_ROUTE103),
                "hide_route103_rival": flag(FLAG_HIDE_ROUTE103_RIVAL),
                "hide_littleroot_lab_rival": flag(FLAG_HIDE_LITTLEROOT_LAB_RIVAL),
                "hide_oldale_rival": flag(FLAG_HIDE_OLDALE_RIVAL),
            },
        },
    }
    return {
        **raw,
        "canonical_sha256": sha256_bytes(canonical_json(raw).encode("utf-8")),
    }


def transition_signature(core: Any) -> tuple[Any, ...]:
    """Facts whose live changes must not be hidden inside a settle segment."""
    block = core.memory.u32[SAVE_BLOCK1_PTR]
    defeat_byte = core.memory.u8[
        block + SAVE_FLAGS_OFFSET + FLAG_DEFEATED_RIVAL_ROUTE103 // 8
    ]
    defeat = bool(defeat_byte & (1 << (FLAG_DEFEATED_RIVAL_ROUTE103 % 8)))
    battlers = [battle_mon(core, index) for index in range(2)]
    return (
        core.memory.u32[0x030022C0],
        core.memory.u32[0x030022C4],
        defeat,
        *(
            (
                mon["species"], mon["level"], mon["hp"], mon["max_hp"],
                tuple(mon["pp"]), tuple(mon["stat_stages"]), mon["status1"],
                mon["status2"],
            )
            for mon in battlers
        ),
    )


def load_core(rom: Path, state: Path) -> tuple[Any, Path]:
    import mgba.core

    temporary = Path(tempfile.mkdtemp(prefix="gamebench-battle-trace-"))
    copied_rom = temporary / "emerald.gba"
    shutil.copyfile(rom, copied_rom)
    core = mgba.core.load_path(str(copied_rom))
    if core is None:
        raise RuntimeError("mGBA could not load the pinned ROM")
    core.autoload_save()
    core.reset()
    if core.load_raw_state(state.read_bytes()) is False:
        raise RuntimeError("mGBA rejected the authenticated state")
    core.run_frame()
    return core, temporary


def run_inside(
    output_dir: Path,
    program: list[dict[str, Any]],
    expected: dict[str, Any],
) -> int:
    import gc
    import importlib.metadata
    import mgba.log

    if output_dir != Path("/oracle-output") or any(output_dir.iterdir()):
        raise RuntimeError("container output must be an empty /oracle-output mount")
    rom = Path("/oracle/emerald.gba")
    state = Path("/oracle/checkpoint.state")
    if sha256_file(rom) != expected["rom_sha256"]:
        raise RuntimeError("container ROM identity mismatch")
    if sha256_file(state) != expected["state_sha256"]:
        raise RuntimeError("container checkpoint identity mismatch")
    if os.environ.get("MGBA_ORACLE_IMAGE_ID") != IMAGE_ID:
        raise RuntimeError("container image identity mismatch")

    mgba.log.silence()
    temporary: Path | None = None
    try:
        core, temporary = load_core(rom, state)
        key_map = {
            "a": core.KEY_A, "b": core.KEY_B, "select": core.KEY_SELECT,
            "start": core.KEY_START, "right": core.KEY_RIGHT,
            "left": core.KEY_LEFT, "up": core.KEY_UP, "down": core.KEY_DOWN,
            "r": core.KEY_R, "l": core.KEY_L,
        }
        frame = 0
        samples = [source_sample(core, frame, "load", [])]
        previous_transition = transition_signature(core)
        for segment in program:
            keys = [key_map[button] for button in segment["buttons"]]
            for _ in range(segment["frames"]):
                core.set_keys(*keys)
                core.run_frame()
                frame += 1
                current_transition = transition_signature(core)
                if current_transition != previous_transition:
                    samples.append(
                        source_sample(
                            core,
                            frame,
                            f"transition:{segment['marker']}",
                            segment["buttons"],
                        )
                    )
                    previous_transition = current_transition
            core.set_keys()
            samples.append(
                source_sample(core, frame, segment["marker"], segment["buttons"])
            )

        validate_terminal(expected["terminal_expectations"], samples[-1])
        raw_state = bytes(core.save_raw_state())
        if not raw_state:
            raise RuntimeError("mGBA returned an empty terminal state")
        write_once(output_dir / "terminal.state", raw_state)
        trace_body = {
            "schema": SCHEMA,
            "source_identity": {
                **{
                    key: expected[key]
                    for key in (
                        "checkpoint", "rom_sha256", "state_sha256",
                        "tape_sha256", "registry_sha256",
                    )
                },
                "container_image_id": IMAGE_ID,
                "libmgba_package_version": "0.10.5+dfsg-1",
                "python_mgba_version": importlib.metadata.version("mgba"),
            },
            "frame_boundary": (
                "one run_frame after raw-state load; one run_frame per tape VBlank"
            ),
            "program": program,
            "samples": samples,
            "terminal_snapshot": {
                "path": "terminal.state",
                "bytes": len(raw_state),
                "sha256": sha256_bytes(raw_state),
            },
        }
        trace = {
            **trace_body,
            "canonical_sha256": sha256_bytes(
                canonical_json(trace_body).encode("utf-8")
            ),
        }
        write_once(
            output_dir / "trace.json",
            (json.dumps(trace, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
    finally:
        gc.collect()
        if temporary is not None:
            shutil.rmtree(temporary, ignore_errors=True)
    return 0


def run_host(args: argparse.Namespace) -> int:
    from emerald_oracle_registry import (
        RegistryError,
        require_authenticated,
        require_trusted_oracle,
        resolve_checkpoint,
    )

    rom = Path(args.rom).resolve()
    state = Path(args.state).resolve()
    tape = Path(args.tape).resolve()
    output = Path(args.output_dir).resolve()
    if not rom.is_file() or not state.is_file() or not tape.is_file():
        raise RuntimeError("--rom, --state, and --tape must be existing files")
    if not output.is_dir() or any(output.iterdir()):
        raise RuntimeError("--output-dir must be an existing empty directory")
    try:
        registry, checkpoint = resolve_checkpoint(args.checkpoint, Path(args.registry))
        require_trusted_oracle(registry)
        source = require_authenticated(checkpoint).source
        assert source is not None
    except RegistryError as exc:
        raise RuntimeError(f"untrusted checkpoint: {exc}") from exc
    if sha256_file(rom) != registry["rom_sha256"]:
        raise RuntimeError("ROM does not match registry")
    if sha256_file(state) != source["state_sha256"]:
        raise RuntimeError("state does not match authenticated checkpoint")
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE], text=True
    ).strip()
    if image_id != IMAGE_ID:
        raise RuntimeError("pinned oracle image mismatch")
    tape_body, program = checked_program(tape)
    terminal_expectations = tape_body.get("terminal_expectations")
    if not isinstance(terminal_expectations, dict):
        raise RuntimeError("battle tape requires terminal_expectations")
    expected = {
        "checkpoint": checkpoint.checkpoint_id,
        "rom_sha256": sha256_file(rom),
        "state_sha256": sha256_file(state),
        "tape_sha256": sha256_file(tape),
        "registry_sha256": sha256_file(Path(args.registry)),
        "terminal_expectations": terminal_expectations,
    }
    command = [
        "docker", "run", "--rm", "--platform", "linux/arm64",
        "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--volume", f"{Path(__file__).resolve()}:/capture.py:ro",
        "--volume", f"{rom}:/oracle/emerald.gba:ro",
        "--volume", f"{state}:/oracle/checkpoint.state:ro",
        "--volume", f"{output}:/oracle-output:rw",
        "--env", f"MGBA_ORACLE_IMAGE_ID={image_id}",
        "--entrypoint", "python3", IMAGE, "/capture.py", "--inside",
        "--output-dir", "/oracle-output",
        "--program-json", canonical_json(program),
        "--expected-json", canonical_json(expected),
    ]
    subprocess.run(command, check=True)
    print(output / "trace.json")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--rom")
    parser.add_argument("--state")
    parser.add_argument("--checkpoint", default="route103_rival_battle_command")
    parser.add_argument(
        "--registry",
        default=str(SCRIPT_DIR.parent / "fixtures" / "gold" / "oracle_registry.json"),
    )
    parser.add_argument("--tape")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--program-json", help=argparse.SUPPRESS)
    parser.add_argument("--expected-json", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside:
        return run_inside(
            Path(args.output_dir),
            json.loads(args.program_json),
            json.loads(args.expected_json),
        )
    if not args.rom or not args.state or not args.tape:
        parser.error("--rom, --state, and --tape are required")
    return run_host(args)


if __name__ == "__main__":
    raise SystemExit(main())
