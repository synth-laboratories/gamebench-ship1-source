#!/usr/bin/env python3
"""Capture one authenticated, receipt-backed GBA PPU VBlank.

Normal JSONL oracle traffic stays compact.  This separate, explicit operation
replays a bounded tape in the pinned container, records raw PPU material only
in a new external evidence directory, and rejects a capture unless a second
fresh replay reaches the same RGB and source semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
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

WIDTH = 240
HEIGHT = 160
RGB_BYTES = WIDTH * HEIGHT * 3
IMAGE = "gamebench-mgba-oracle:0.10.5-9"
IMAGE_ID = "sha256:5995357b864e56df0715730a0ec2735d1a3f6af73d0bd90b87ee1b4f8bd7e0ed"
SCHEMA = "gamebench.pokemon_emerald.ppu_receipt.v2"
ADAPTER_PATH = "/opt/gamebench/mgba_jsonl_oracle.py"
OBSERVABILITY_PATH = "/opt/gamebench/emerald_source_observability.py"


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


def write_once(path: Path, value: bytes) -> dict[str, Any]:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence artifact: {path}")
    path.write_bytes(value)
    return {"path": path.name, "bytes": len(value), "sha256": sha256_bytes(value)}


def source_state(core: Any, memory_bytes: Any, observe_source_state: Any) -> dict[str, Any]:
    save_block1 = core.memory.u32[0x03005D8C]
    if not 0x02000000 <= save_block1 < 0x02040000:
        raise RuntimeError(f"invalid Emerald gSaveBlock1Ptr: 0x{save_block1:08x}")
    state = {
        "player_x": core.memory.s16[save_block1],
        "player_y": core.memory.s16[save_block1 + 2],
        "map_group": core.memory.s8[save_block1 + 4],
        "map_number": core.memory.s8[save_block1 + 5],
        "observability": observe_source_state(memory_bytes),
    }
    return {**state, "state_sha256": sha256_bytes(canonical_json(state).encode("utf-8"))}


def ppu_registers(core: Any) -> tuple[bytes, dict[str, Any]]:
    """Read the emulated IO backing store as halfwords, not the open bus.

    mGBA's public byte bus reads of write-only display registers return the
    open-bus latch.  The pinned Python binding exposes the GBA board's IO
    backing array, which is the exact register image the mGBA renderer uses.
    This is deliberately limited to an authenticated, pinned binding.
    """
    words = [int(core._native.memory.io[index]) for index in range(0x60 // 2)]
    io = b"".join(word.to_bytes(2, "little") for word in words)
    at = lambda byte: words[byte // 2]
    return io, {
        "dispcnt": at(0x00),
        "bgcnt": [at(0x08 + 2 * index) for index in range(4)],
        "bg_offsets": [at(0x10 + 2 * index) for index in range(8)],
        "bg2_affine": [at(0x20 + 2 * index) for index in range(8)],
        "bg3_affine": [at(0x30 + 2 * index) for index in range(8)],
        "win0h": at(0x40), "win1h": at(0x42),
        "win0v": at(0x44), "win1v": at(0x46),
        "winin": at(0x48), "winout": at(0x4A),
        "mosaic": at(0x4C), "bldcnt": at(0x50),
        "bldalpha": at(0x52), "bldy": at(0x54),
    }


def load_core(rom: Path, state: Path) -> tuple[Any, Any, Path]:
    import mgba.core
    import mgba.image

    temporary = Path(tempfile.mkdtemp(prefix="gamebench-ppu-receipt-"))
    copied_rom = temporary / "emerald.gba"
    shutil.copyfile(rom, copied_rom)
    core = mgba.core.load_path(str(copied_rom))
    if core is None:
        raise RuntimeError("mGBA could not load the pinned ROM")
    core.autoload_save()
    core.reset()
    if core.desired_video_dimensions() != (WIDTH, HEIGHT):
        raise RuntimeError("mGBA video mode is not native 240x160")
    video = mgba.image.Image(WIDTH, HEIGHT)
    core.set_video_buffer(video)
    core.reset()
    if core.load_raw_state(state.read_bytes()) is False:
        raise RuntimeError("mGBA rejected the requested state")
    core.run_frame()
    return core, video, temporary


def apply_button(core: Any, button: str) -> None:
    key_map = {
        "a": core.KEY_A, "b": core.KEY_B, "select": core.KEY_SELECT,
        "start": core.KEY_START, "right": core.KEY_RIGHT, "left": core.KEY_LEFT,
        "up": core.KEY_UP, "down": core.KEY_DOWN, "noop": None,
    }
    if button not in key_map:
        raise RuntimeError(f"unsupported tape button {button!r}")
    if key_map[button] is None:
        core.set_keys()
    else:
        core.set_keys(key_map[button])
    core.run_frame()
    core.set_keys()


def capture_inside(output_dir: Path, tape: list[str], vblank: int, expected: dict[str, str]) -> int:
    import gc
    import mgba.log

    sys.path.insert(0, "/opt/gamebench")
    from emerald_source_observability import observe_source_state

    if output_dir != Path("/oracle-output") or not output_dir.is_dir():
        raise RuntimeError("container capture output must be the explicit /oracle-output mount")
    if not 0 <= vblank <= len(tape):
        raise RuntimeError("requested VBlank must be within the supplied tape")
    if sha256_file(Path(ADAPTER_PATH)) != expected["adapter_source_sha256"]:
        raise RuntimeError("pinned adapter source digest does not match trusted v8 identity")
    if sha256_file(Path(OBSERVABILITY_PATH)) != expected["observability_source_sha256"]:
        raise RuntimeError("pinned observability source digest does not match trusted v8 identity")
    rom = Path("/oracle/emerald.gba")
    state = Path("/oracle/checkpoint.state")
    mgba.log.silence()
    temporary: Path | None = None
    fresh_temporary: Path | None = None
    try:
        core, video, temporary = load_core(rom, state)
        memory_bytes = lambda address, length: bytes(core.memory.u8[address + offset] for offset in range(length))
        initial_rgb = video.to_pil().convert("RGB").tobytes()
        if sha256_bytes(initial_rgb) != expected["initial_rgb_sha256"]:
            raise RuntimeError("capture load boundary does not match authenticated checkpoint RGB")
        for button in tape[:vblank]:
            apply_button(core, button)
        rgb = video.to_pil().convert("RGB").tobytes()
        if len(rgb) != RGB_BYTES:
            raise RuntimeError("mGBA framebuffer is not RGB888 240x160")
        state_view = source_state(core, memory_bytes, observe_source_state)
        io, registers = ppu_registers(core)
        vram = memory_bytes(0x06000000, 0x18000)
        palette = memory_bytes(0x05000000, 0x400)
        oam = memory_bytes(0x07000000, 0x400)

        # A wholly fresh emulator must replay the exact prefix to the same
        # semantic state and framebuffer before any raw PPU bytes are accepted.
        fresh, fresh_video, fresh_temporary = load_core(rom, state)
        fresh_memory = lambda address, length: bytes(fresh.memory.u8[address + offset] for offset in range(length))
        for button in tape[:vblank]:
            apply_button(fresh, button)
        fresh_rgb = fresh_video.to_pil().convert("RGB").tobytes()
        fresh_state = source_state(fresh, fresh_memory, observe_source_state)
        if fresh_rgb != rgb or fresh_state != state_view:
            raise RuntimeError("fresh source replay failed to reproduce captured VBlank RGB and semantics")

        files = {
            "rgb": write_once(output_dir / "frame.rgb", rgb),
            "io": write_once(output_dir / "io.bin", io),
            "vram": write_once(output_dir / "vram.bin", vram),
            "palette": write_once(output_dir / "palette.bin", palette),
            "oam": write_once(output_dir / "oam.bin", oam),
        }
        tape_bytes = canonical_json(tape).encode("utf-8")
        receipt = {
            "schema": SCHEMA,
            "frame_boundary": "load: one core.run_frame; each tape item: one core.run_frame",
            "vblank": vblank,
            "tape": {"vblanks": len(tape), "sha256": sha256_bytes(tape_bytes), "prefix_sha256": sha256_bytes(canonical_json(tape[:vblank]).encode("utf-8"))},
            "source_identity": {
                "rom_sha256": sha256_file(rom), "state_sha256": sha256_file(state),
                "checkpoint": expected["checkpoint"], "registry_sha256": expected["registry_sha256"],
                "emulator": {"core": "mGBA", "libmgba_package_version": "0.10.5+dfsg-1", "python_mgba_version": importlib.metadata.version("mgba"), "container_image_id": os.environ["MGBA_ORACLE_IMAGE_ID"]},
                "adapter_source_sha256": expected["adapter_source_sha256"],
                "observability_source_sha256": expected["observability_source_sha256"],
            },
            "fresh_replay": {"status": "exact", "frame_rgb_sha256": sha256_bytes(fresh_rgb), "source_state_sha256": fresh_state["state_sha256"]},
            "frame_rgb_sha256": sha256_bytes(rgb), "source_state": state_view,
            "registers": registers,
            "memory_layout": {"io": {"address": "0x04000000", "bytes": len(io)}, "vram": {"address": "0x06000000", "bytes": len(vram)}, "palette": {"address": "0x05000000", "bytes": len(palette)}, "oam": {"address": "0x07000000", "bytes": len(oam)}},
            "files": files,
        }
        write_once(output_dir / "receipt.json", (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        gc.collect()
        if temporary is not None: shutil.rmtree(temporary, ignore_errors=True)
        if fresh_temporary is not None: shutil.rmtree(fresh_temporary, ignore_errors=True)
    return 0


def load_tape(path: Path | None) -> list[str]:
    if path is None:
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(button, str) for button in value):
        raise RuntimeError("--tape must be a JSON array of button names")
    if len(value) > 1_000:
        raise RuntimeError("--tape is bounded to 1000 VBlanks")
    return value


def capture_host(args: argparse.Namespace) -> int:
    from emerald_oracle_registry import (
        RegistryError,
        require_authenticated,
        require_trusted_oracle,
        resolve_checkpoint,
    )
    rom, state, output = Path(args.rom).resolve(), Path(args.state).resolve(), Path(args.output_dir).resolve()
    if not rom.is_file() or not state.is_file() or not output.is_dir():
        raise RuntimeError("--rom and --state must be files and --output-dir must already exist")
    if any(output.iterdir()):
        raise RuntimeError("--output-dir must be empty to preserve an immutable receipt")
    try:
        registry, checkpoint = resolve_checkpoint(args.checkpoint, Path(args.registry))
        require_trusted_oracle(registry)
        source = require_authenticated(checkpoint).source
        assert source is not None
    except RegistryError as exc:
        raise RuntimeError(f"untrusted checkpoint: {exc}") from exc
    if sha256_file(rom) != registry["rom_sha256"] or sha256_file(state) != source["state_sha256"]:
        raise RuntimeError("ROM/state do not match the authenticated checkpoint identity")
    identity = registry["oracle"]
    config = identity["config"]
    image_id = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE], text=True).strip()
    if image_id != IMAGE_ID or config.get("container_image_id") != IMAGE_ID:
        raise RuntimeError("pinned oracle image mismatch")
    tape = load_tape(Path(args.tape) if args.tape else None)
    expected = {
        "checkpoint": checkpoint.checkpoint_id, "registry_sha256": sha256_file(Path(args.registry)),
        "initial_rgb_sha256": source["initial_rgb_sha256"],
        "adapter_source_sha256": config["adapter_source_sha256"],
        "observability_source_sha256": config["observability_source_sha256"],
    }
    command = ["docker", "run", "--rm", "--platform", "linux/arm64", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "--volume", f"{Path(__file__).resolve()}:/capture.py:ro", "--volume", f"{rom}:/oracle/emerald.gba:ro", "--volume", f"{state}:/oracle/checkpoint.state:ro", "--volume", f"{output}:/oracle-output:rw", "--env", f"MGBA_ORACLE_IMAGE_ID={image_id}", "--entrypoint", "python", IMAGE, "/capture.py", "--inside", "--output-dir", "/oracle-output", "--vblank", str(args.vblank), "--tape-json", canonical_json(tape), "--expected-json", canonical_json(expected)]
    subprocess.run(command, check=True)
    print(output / "receipt.json")
    return 0


def main() -> int:
    # This module is mounted by itself into the immutable oracle container.
    # Keep host-only registry imports out of the container startup path.
    default_registry = str(SCRIPT_DIR.parent / "fixtures" / "gold" / "oracle_registry.json")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--rom")
    parser.add_argument("--state")
    parser.add_argument("--checkpoint", default="starter_battle")
    parser.add_argument("--registry", default=default_registry)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tape", help="JSON array of one button/noop per VBlank")
    parser.add_argument("--vblank", type=int, default=0)
    parser.add_argument("--tape-json", help=argparse.SUPPRESS)
    parser.add_argument("--expected-json", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.vblank < 0:
        parser.error("--vblank must be non-negative")
    if args.inside:
        return capture_inside(Path(args.output_dir), json.loads(args.tape_json), args.vblank, json.loads(args.expected_json))
    if not args.rom or not args.state:
        parser.error("--rom and --state are required outside the container")
    return capture_host(args)


if __name__ == "__main__":
    raise SystemExit(main())
