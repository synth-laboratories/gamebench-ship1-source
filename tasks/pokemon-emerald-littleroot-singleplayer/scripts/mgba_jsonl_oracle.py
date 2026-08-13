#!/usr/bin/env python3
"""Strict JSONL pixel oracle backed by a pinned mGBA core.

This process is intentionally small.  It loads one ROM/save-state pair, accepts
one set of held buttons per VBlank, and returns the native 240x160 RGB888
framebuffer.  It does not resize, encode, filter, or compare frames itself.

The normal entry point is ``run_mgba_jsonl_oracle.sh``. That wrapper supplies
container-local ROM and state paths through environment variables. Snapshot
capture is disabled unless it also mounts one explicit host output directory;
the JSONL adapter accepts no other writable path.
"""

from __future__ import annotations

import base64
import gc
import hashlib
import importlib.metadata
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import mgba.core
import mgba.image
import mgba.log

from emerald_source_observability import observe_source_state


WIDTH = 240
HEIGHT = 160
RGB_BYTES = WIDTH * HEIGHT * 3
CORE_PACKAGE_VERSION = "0.10.5+dfsg-1"
PYTHON_BINDING_VERSION = importlib.metadata.version("mgba")
ADAPTER_VERSION = "9"
BASE_CONFIG = {
    "adapter": "gamebench.mgba_jsonl_oracle",
    "adapter_version": ADAPTER_VERSION,
    "audio": False,
    "bios": "mGBA built-in",
    "frame_boundary": "one core.run_frame call per step",
    "framebuffer": "native 240x160 RGB888",
    "frameskip": 0,
    "initial_state_advance_frames": 1,
    "libmgba_package_version": CORE_PACKAGE_VERSION,
    "python_mgba_version": PYTHON_BINDING_VERSION,
}


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


def runtime_config() -> dict[str, Any]:
    observability_path = Path(__file__).with_name("emerald_source_observability.py")
    return {
        **BASE_CONFIG,
        "adapter_source_sha256": sha256_file(Path(__file__)),
        "observability_source_sha256": sha256_file(observability_path),
        "container_image_id": os.environ.get(
            "MGBA_ORACLE_IMAGE_ID", "native-execution"
        ),
    }


def button_indices(buttons: list[str], key_indices: dict[str, int]) -> tuple[int, ...]:
    """Validate and return python-mGBA key enum indices for ``set_keys``.

    ``Core.set_keys`` accepts each key enum as a separate positional argument,
    then converts those indices to its internal bit mask. Passing an already
    ORed value as one argument silently collapses chords such as up+right.
    Keeping this helper pure makes that protocol boundary independently
    testable without a live core.
    """
    result: list[int] = []
    for button in buttons:
        key_index = key_indices[button]
        if not isinstance(key_index, int) or key_index < 0:
            raise RuntimeError(f"mGBA returned an invalid key index for {button!r}")
        result.append(key_index)
    return tuple(result)


class Oracle:
    def __init__(self) -> None:
        self.core: Any | None = None
        self.video_buffer: Any | None = None
        self.temp_dir: Path | None = None
        self.frame_number = 0
        self.rom_sha256: str | None = None
        self.state_sha256: str | None = None

    def close(self) -> None:
        self.core = None
        self.video_buffer = None
        gc.collect()
        if self.temp_dir is not None:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None

    def _frame_rgb(self) -> bytes:
        if self.video_buffer is None:
            raise RuntimeError("no source state is loaded")
        rgb = self.video_buffer.to_pil().convert("RGB").tobytes()
        if len(rgb) != RGB_BYTES:
            raise RuntimeError(
                f"mGBA returned {len(rgb)} RGB bytes; expected {RGB_BYTES}"
            )
        return rgb

    def _memory_bytes(self, address: int, length: int) -> bytes:
        if self.core is None:
            raise RuntimeError("no source state is loaded")
        return bytes(self.core.memory.u8[address + offset] for offset in range(length))

    def _source_state(self) -> dict[str, Any]:
        if self.core is None:
            raise RuntimeError("no source state is loaded")
        save_block1 = self.core.memory.u32[0x03005D8C]
        if not 0x02000000 <= save_block1 < 0x02040000:
            raise RuntimeError(
                f"invalid Emerald gSaveBlock1Ptr value: 0x{save_block1:08x}"
            )
        state = {
            "player_x": self.core.memory.s16[save_block1],
            "player_y": self.core.memory.s16[save_block1 + 2],
            "map_group": self.core.memory.s8[save_block1 + 4],
            "map_number": self.core.memory.s8[save_block1 + 5],
            "rng_value": self.core.memory.u32[0x03005D80],
            "save_block1_sha256": sha256_bytes(
                self._memory_bytes(save_block1, 0x3D88)
            ),
            "player_avatar_sha256": sha256_bytes(
                self._memory_bytes(0x02037590, 0x24)
            ),
            "object_events_sha256": sha256_bytes(
                self._memory_bytes(0x02037350, 0x240)
            ),
            # Emerald's first two hardware OAM entries are the bedroom Poké
            # Ball and player at this checkpoint. Preserve their exact
            # attributes so a localized pixel mismatch can be attributed to
            # geometry/tile selection instead of guessed from screenshots.
            "oam_entries_0_1_hex": self._memory_bytes(0x07000000, 16).hex(),
            "obj_tiles_0_7_hex": self._memory_bytes(0x06010000, 0x100).hex(),
            "oam_entries_0_7_hex": self._memory_bytes(0x07000000, 64).hex(),
            "obj_tiles_20_35_hex": self._memory_bytes(0x06010000 + 20 * 32, 16 * 32).hex(),
            # OBJ palette banks 0..2 are the player/field-effect/NPC colour
            # authorities at this checkpoint. Keeping the raw upload here
            # makes a directional tile mismatch attributable to palette DMA
            # rather than to an inferred RGB screenshot difference.
            "obj_palette_0_2_hex": self._memory_bytes(0x05000200, 3 * 32).hex(),
            "observability": observe_source_state(self._memory_bytes),
        }
        return {
            **state,
            "state_sha256": sha256_bytes(canonical_json(state).encode("utf-8")),
        }

    def _response(self, rgb: bytes, *, include_identity: bool = False) -> dict[str, Any]:
        response: dict[str, Any] = {
            "ok": True,
            "frame_rgb_b64": base64.b64encode(rgb).decode("ascii"),
            "frame_number": self.frame_number,
            "frame_rgb_sha256": sha256_bytes(rgb),
            "source_state": self._source_state(),
        }
        if include_identity:
            config = runtime_config()
            response.update(
                {
                    "rom_sha256": self.rom_sha256,
                    "state_sha256": self.state_sha256,
                    "emulator": {
                        "core": "mGBA",
                        "version": (
                            f"libmgba {CORE_PACKAGE_VERSION}; "
                            f"python-mgba {PYTHON_BINDING_VERSION}"
                        ),
                        "config_sha256": sha256_bytes(
                            canonical_json(config).encode("utf-8")
                        ),
                    },
                    "config": config,
                }
            )
        return response

    def _resolve_state_path(self, requested_state: str) -> Path:
        """Return the fixed input state or a snapshot in the mounted output dir.

        A container invocation normally exposes exactly one read-only input
        state. Snapshot round-trips additionally expose one explicit writable
        host directory at ``/oracle-output``. Do not permit arbitrary paths
        from the JSONL client: that would turn the oracle into a file reader.
        """
        fixed_state = Path(os.environ.get("MGBA_ORACLE_STATE_PATH", requested_state))
        snapshot_root_text = os.environ.get("MGBA_ORACLE_SNAPSHOT_DIR")
        if not snapshot_root_text:
            return fixed_state
        snapshot_root = Path(snapshot_root_text).resolve()
        candidate = Path(requested_state)
        try:
            candidate.relative_to(snapshot_root)
        except ValueError:
            return fixed_state
        resolved = candidate.resolve()
        if resolved.parent != snapshot_root or resolved.suffix != ".state":
            raise ValueError("snapshot reload path must name one .state file in /oracle-output")
        return resolved

    def snapshot(self, request: dict[str, Any]) -> dict[str, Any]:
        """Persist the current raw mGBA state to the explicit mounted target.

        Snapshots are write-once, flat files under the directory selected by
        the launcher. The response deliberately contains digests/readout, not
        state bytes, so the JSONL protocol cannot exfiltrate a save state.
        """
        if self.core is None:
            raise RuntimeError("snapshot received before load")
        requested_output = request.get("output_path")
        if not isinstance(requested_output, str) or not requested_output:
            raise ValueError("snapshot requires a non-empty output_path")
        snapshot_root_text = os.environ.get("MGBA_ORACLE_SNAPSHOT_DIR")
        if not snapshot_root_text:
            raise RuntimeError("snapshot is disabled: no explicit host output directory is mounted")
        snapshot_root = Path(snapshot_root_text).resolve()
        output_path = Path(requested_output)
        try:
            output_path.relative_to(snapshot_root)
        except ValueError as exc:
            raise ValueError("snapshot output_path must be inside /oracle-output") from exc
        output_path = output_path.resolve()
        if output_path.parent != snapshot_root or output_path.suffix != ".state":
            raise ValueError("snapshot output_path must name one .state file in /oracle-output")
        if output_path.exists():
            raise FileExistsError(f"refusing to overwrite snapshot: {output_path}")
        raw_state = bytes(self.core.save_raw_state())
        if not raw_state:
            raise RuntimeError("mGBA returned an empty raw state")
        temporary_path = output_path.with_name(output_path.name + ".partial")
        try:
            with temporary_path.open("xb") as output:
                output.write(raw_state)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, output_path)
        except Exception:
            if temporary_path.exists():
                temporary_path.unlink()
            raise
        rgb = self._frame_rgb()
        config = runtime_config()
        return {
            "ok": True,
            "snapshot_path": str(output_path),
            "snapshot_state_sha256": sha256_bytes(raw_state),
            "frame_number": self.frame_number,
            "frame_rgb_sha256": sha256_bytes(rgb),
            "source_state": self._source_state(),
            "rom_sha256": self.rom_sha256,
            "emulator": {
                "core": "mGBA",
                "version": f"libmgba {CORE_PACKAGE_VERSION}; python-mgba {PYTHON_BINDING_VERSION}",
                "config_sha256": sha256_bytes(canonical_json(config).encode("utf-8")),
            },
            "config": config,
        }

    def load(self, request: dict[str, Any]) -> dict[str, Any]:
        requested_rom = request.get("rom_path")
        requested_state = request.get("state_path")
        if not isinstance(requested_rom, str) or not requested_rom:
            raise ValueError("load requires a non-empty rom_path")
        if not isinstance(requested_state, str) or not requested_state:
            raise ValueError("load requires a non-empty state_path")

        # The Docker wrapper exposes exactly these two files.  When the adapter
        # is run natively, the requested paths are used directly.
        rom_path = Path(os.environ.get("MGBA_ORACLE_ROM_PATH", requested_rom))
        state_path = self._resolve_state_path(requested_state)
        if not rom_path.is_file():
            raise FileNotFoundError(f"ROM not found: {rom_path}")
        if not state_path.is_file():
            raise FileNotFoundError(f"save state not found: {state_path}")

        rom_sha256 = sha256_file(rom_path)
        state_sha256 = sha256_file(state_path)
        if (
            self.core is not None
            and self.rom_sha256 == rom_sha256
            and self.state_sha256 == state_sha256
        ):
            # ``set_keys`` takes positional enum indices, so ``set_keys(0)``
            # presses KEY_A. A release is an empty key set.
            self.core.set_keys()
            loaded = self.core.load_raw_state(state_path.read_bytes())
            if loaded is False:
                raise RuntimeError("mGBA rejected the supplied save state")
            self.core.run_frame()
            self.frame_number = 0
            return self._response(self._frame_rgb(), include_identity=True)

        self.close()
        self.rom_sha256 = rom_sha256
        self.state_sha256 = state_sha256
        self.temp_dir = Path(tempfile.mkdtemp(prefix="gamebench-mgba-oracle-"))
        copied_rom = self.temp_dir / "rom.gba"
        shutil.copyfile(rom_path, copied_rom)

        core = mgba.core.load_path(str(copied_rom))
        if core is None:
            raise RuntimeError("mGBA could not identify the supplied ROM")
        core.autoload_save()
        core.reset()
        width, height = core.desired_video_dimensions()
        if (width, height) != (WIDTH, HEIGHT):
            raise RuntimeError(
                f"mGBA requested {width}x{height}; expected {WIDTH}x{HEIGHT}"
            )
        video_buffer = mgba.image.Image(width, height)
        core.set_video_buffer(video_buffer)
        core.reset()

        state_bytes = state_path.read_bytes()
        loaded = core.load_raw_state(state_bytes)
        if loaded is False:
            raise RuntimeError("mGBA rejected the supplied save state")

        # Match PokeAgent's load_state boundary: it advances one frame after a
        # raw-state load so the video buffer and memory view are synchronized.
        core.run_frame()
        self.core = core
        self.video_buffer = video_buffer
        self.frame_number = 0
        return self._response(self._frame_rgb(), include_identity=True)

    def step(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.core is None:
            raise RuntimeError("step received before load")
        buttons = request.get("buttons")
        if not isinstance(buttons, list) or not all(
            isinstance(button, str) for button in buttons
        ):
            raise ValueError("step requires a list of button names")
        if len(buttons) != len(set(buttons)):
            raise ValueError("step buttons must not contain duplicates")

        key_map = {
            "a": self.core.KEY_A,
            "b": self.core.KEY_B,
            "select": self.core.KEY_SELECT,
            "start": self.core.KEY_START,
            "right": self.core.KEY_RIGHT,
            "left": self.core.KEY_LEFT,
            "up": self.core.KEY_UP,
            "down": self.core.KEY_DOWN,
            "r": self.core.KEY_R,
            "l": self.core.KEY_L,
        }
        unknown = sorted(set(buttons) - set(key_map))
        if unknown:
            raise ValueError(f"unknown button names: {', '.join(unknown)}")

        # python-mgba exposes GBA keys as enum *indices* (KEY_A == 0,
        # KEY_DOWN == 7). Its ``set_keys`` method shifts each *positional*
        # index internally. Passing an ORed index as one argument preserves
        # single buttons but loses chords (up+right becomes up); preserve every
        # requested key as its own argument.
        self.core.set_keys(*button_indices(buttons, key_map))
        self.core.run_frame()
        # Do not pass 0 here: with python-mGBA's positional API that is KEY_A.
        self.core.set_keys()
        self.frame_number += 1
        return self._response(self._frame_rgb())


def write_response(response: dict[str, Any]) -> None:
    sys.stdout.write(canonical_json(response) + "\n")
    sys.stdout.flush()


def main() -> int:
    mgba.log.silence()
    oracle = Oracle()
    try:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("request must be a JSON object")
                operation = request.get("op")
                if operation == "load":
                    response = oracle.load(request)
                elif operation == "step":
                    response = oracle.step(request)
                elif operation == "snapshot":
                    response = oracle.snapshot(request)
                else:
                    raise ValueError(f"unsupported operation: {operation!r}")
            except Exception as exc:  # JSONL errors belong in the protocol.
                response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            write_response(response)
    finally:
        oracle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
