#!/usr/bin/env python3
"""Describe receipt-vs-staged PPU asset gaps without promoting receipt bytes."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt_path = args.receipt.resolve()
    root = receipt_path.parent
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != "gamebench.pokemon_emerald.ppu_receipt.v1":
        raise SystemExit("unsupported receipt schema")
    vram = (root / receipt["files"]["vram"]["path"]).read_bytes()
    palette = (root / receipt["files"]["palette"]["path"]).read_bytes()
    oam = (root / receipt["files"]["oam"]["path"]).read_bytes()
    bgcnt = receipt["registers"]["bgcnt"]
    screenblocks = [1, 2, 2, 4]
    backgrounds = []
    for index, control in enumerate(bgcnt):
        charbase = ((control >> 2) & 3) * 0x4000
        screenbase = ((control >> 8) & 31) * 0x800
        size = (control >> 14) & 3
        map_bytes = screenblocks[size] * 0x800
        backgrounds.append({
            "bg": index,
            "control": f"0x{control:04x}",
            "charbase": f"0x{charbase:05x}",
            "charbase_sha256": digest(vram[charbase:charbase + 0x4000]),
            "screenbase": f"0x{screenbase:05x}",
            "screenblock_bytes": map_bytes,
            "screenblock_sha256": digest(vram[screenbase:screenbase + map_bytes]),
        })
    task_root = Path(__file__).resolve().parents[1]
    staged_map = task_root / "gold_rust/assets/battle_tall_grass_map.bin.b64"
    staged_map_bytes = base64.b64decode(staged_map.read_bytes())
    bg2_map = vram[0xF000:0x10000]
    manifest = {
        "schema": "gamebench.pokemon_emerald.ppu_asset_gap.v1",
        "receipt": str(receipt_path),
        "receipt_frame_rgb_sha256": receipt["frame_rgb_sha256"],
        "backgrounds": backgrounds,
        "runtime_memory": {
            "bg_palette_sha256": digest(palette[:0x200]),
            "obj_palette_sha256": digest(palette[0x200:]),
            "obj_vram_sha256": digest(vram[0x10000:0x18000]),
            "oam_sha256": digest(oam),
        },
        "staged_comparison": {
            "asset": str(staged_map),
            "asset_sha256": digest(staged_map_bytes),
            "receipt_bg2_screenblock_sha256": digest(bg2_map),
            "matches": staged_map_bytes == bg2_map,
        },
        "gap": "The staged tall-grass map is not the exact runtime BG2 screenblock. Do not copy receipt bytes into runtime. Extract the named source graphics/tilemap/palette/OBJ uploads from the pinned pret revision, record their file digests, then reproduce the documented upload order into GbaMode0PpuMemory.",
        "provenance_recipe": [
            "Start from the pinned pret/pokeemerald revision in emerald_source_observability.json.",
            "Identify the battle setup upload functions and source graphics named by the authenticated battle state.",
            "Extract each source asset with its path, source-revision digest, dimensions, destination VRAM/palette/OAM offset, and register write.",
            "Stage only those source assets in the repository; construct GbaMode0PpuMemory through range-checked upload methods.",
            "Keep BGxHOFS/VOFS in logical battle state; for the command surface set BG0 VOFS=160 rather than reading IO latch 0x1c18.",
            "Validate each resulting VBlank against a fresh receipt with zero RGB tolerance.",
        ],
    }
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    if output.parent == task_root or task_root in output.parents:
        raise SystemExit("gap manifests are external evidence, not task-repository artifacts")
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
