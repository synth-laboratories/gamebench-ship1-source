#!/usr/bin/env python3
"""Hash-bound field-state observations from an authenticated Emerald state."""

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


SCHEMA = "gamebench.pokemon_emerald.field_state_sidecar.v1"
G_SAVE_BLOCK1_PTR = 0x03005D8C
FLAGS_OFFSET = 0x1270
FLAG_RECEIVED_RUNNING_SHOES = 0x112
FLAG_SYS_B_DASH = 0x8C0


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    mgba.log.silence()
    rom_path = Path(os.environ["EMERALD_FIELD_ROM_PATH"])
    state_path = Path(os.environ["EMERALD_FIELD_STATE_PATH"])
    manifest_path = Path(os.environ["EMERALD_FIELD_SYMBOL_MANIFEST_PATH"])
    script_sha = sha256_file(Path(__file__))
    manifest_sha = sha256_file(manifest_path)
    if script_sha != os.environ["EMERALD_FIELD_SCRIPT_SHA256"]:
        raise RuntimeError("mounted field sidecar script hash mismatch")
    if manifest_sha != os.environ["EMERALD_FIELD_SYMBOL_MANIFEST_SHA256"]:
        raise RuntimeError("mounted field symbol manifest hash mismatch")

    temporary = Path(tempfile.mkdtemp(prefix="emerald-field-sidecar-"))
    core = None
    try:
        copied_rom = temporary / "rom.gba"
        shutil.copyfile(rom_path, copied_rom)
        core = mgba.core.load_path(str(copied_rom))
        if core is None:
            raise RuntimeError("mGBA could not identify ROM")
        core.autoload_save()
        core.reset()
        if core.load_raw_state(state_path.read_bytes()) is False:
            raise RuntimeError("mGBA rejected state")
        core.run_frame()

        read = lambda address, length: bytes(
            core.memory.u8[address + offset] for offset in range(length)
        )
        save_block1 = int.from_bytes(read(G_SAVE_BLOCK1_PTR, 4), "little")
        if not 0x02000000 <= save_block1 < 0x02040000:
            raise RuntimeError(f"invalid gSaveBlock1Ptr: 0x{save_block1:08x}")

        def flag(flag_id: int) -> dict[str, Any]:
            address = save_block1 + FLAGS_OFFSET + flag_id // 8
            raw = read(address, 1)[0]
            mask = 1 << (flag_id % 8)
            return {
                "flag_id": f"0x{flag_id:03x}",
                "address": f"0x{address:08x}",
                "raw_byte": raw,
                "mask": f"0x{mask:02x}",
                "set": bool(raw & mask),
            }

        receipt: dict[str, Any] = {
            "schema": SCHEMA,
            "identity": {
                "rom_sha256": sha256_file(rom_path),
                "state_sha256": sha256_file(state_path),
                "container_image_id": os.environ["EMERALD_FIELD_IMAGE_ID"],
                "script_sha256": script_sha,
                "symbol_manifest_sha256": manifest_sha,
                "libmgba_package_version": "0.10.5+dfsg-1",
                "python_mgba_version": importlib.metadata.version("mgba"),
                "initial_state_advance_frames": 1,
            },
            "field_state": {
                "save_block1_ptr": f"0x{save_block1:08x}",
                "flags": {
                    "FLAG_RECEIVED_RUNNING_SHOES": flag(FLAG_RECEIVED_RUNNING_SHOES),
                    "FLAG_SYS_B_DASH": flag(FLAG_SYS_B_DASH),
                },
            },
        }
        receipt["receipt_sha256"] = hashlib.sha256(
            canonical_json(receipt).encode("utf-8")
        ).hexdigest()
        print(canonical_json(receipt))
    finally:
        core = None
        gc.collect()
        shutil.rmtree(temporary, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
