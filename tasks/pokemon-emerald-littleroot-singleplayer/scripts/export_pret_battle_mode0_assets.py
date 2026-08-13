#!/usr/bin/env python3
"""Export source-derived, decoded battle mode-0 assets from a pinned pret tree.

The exporter writes only individual graphics/tilemap/palette artifacts plus a
provenance manifest. It never reads emulator VRAM and never emits a frame.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


REVISION = "83df84e40623b79281f2397faa611cbf044170bd"
SCHEMA = "gamebench.pokemon_emerald.mode0_source_assets.v1"
ASSETS = (
    ("textbox_tiles", "graphics/battle_interface/textbox.png", "png4bpp", "bg_vram", 0x0000),
    ("textbox_map", "graphics/battle_interface/textbox_map.bin", "raw", "bg_vram", 0xC000),
    ("textbox_palette_0", "graphics/battle_interface/textbox_0.pal", "jasc_palette", "bg_palette", 0x000),
    ("textbox_palette_1", "graphics/battle_interface/textbox_1.pal", "jasc_palette", "bg_palette", 0x020),
    ("tall_grass_tiles", "graphics/battle_environment/tall_grass/tiles.png", "png4bpp", "bg_vram", 0x8000),
    ("tall_grass_map", "graphics/battle_environment/tall_grass/map.bin", "raw", "bg_vram", 0xD000),
    ("tall_grass_palette", "graphics/battle_environment/tall_grass/palette.pal", "jasc_palette", "bg_palette", 0x040),
    ("tall_grass_anim_tiles", "graphics/battle_environment/tall_grass/anim_tiles.png", "png4bpp", "bg_vram", 0x4000),
    ("tall_grass_anim_map", "graphics/battle_environment/tall_grass/anim_map.bin", "raw", "bg_vram", 0xE000),
)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def pack_png_4bpp(path: Path) -> bytes:
    from PIL import Image

    image = Image.open(path)
    if image.mode != "P" or image.width % 8 or image.height % 8:
        raise ValueError(f"{path} must be indexed and tile-aligned")
    pixels = list(image.getdata())
    if any(index > 15 for index in pixels):
        raise ValueError(f"{path} has a palette index above 15")
    packed = bytearray()
    for row in range(image.height):
        start = row * image.width
        for column in range(0, image.width, 2):
            packed.append(pixels[start + column] | (pixels[start + column + 1] << 4))
    return bytes(packed)


def parse_jasc_palette(path: Path) -> bytes:
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines[:2] != ["JASC-PAL", "0100"]:
        raise ValueError(f"{path} is not a JASC palette")
    count = int(lines[2])
    colors = lines[3:3 + count]
    if len(colors) != count:
        raise ValueError(f"{path} is truncated")
    packed = bytearray()
    for line in colors:
        red, green, blue = (int(value) for value in line.split())
        value = (red >> 3) | ((green >> 3) << 5) | ((blue >> 3) << 10)
        packed.extend(value.to_bytes(2, "little"))
    return bytes(packed)


def export(source: Path, output: Path, receipt_path: Path | None) -> int:
    revision = os.environ.get("PRET_POKEEMERALD_REVISION")
    if revision is None:
        revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        raise ValueError(f"source revision is {revision}, expected {REVISION}")
    if output.exists() or not output.parent.is_dir():
        raise ValueError("output must be a new path under an existing directory")
    output.mkdir()
    receipt_vram = receipt_palette = None
    if receipt_path is not None:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("schema") != "gamebench.pokemon_emerald.ppu_receipt.v1":
            raise ValueError("unsupported PPU receipt schema")
        receipt_root = receipt_path.parent
        receipt_vram = (receipt_root / receipt["files"]["vram"]["path"]).read_bytes()
        receipt_palette = (receipt_root / receipt["files"]["palette"]["path"]).read_bytes()
    records = []
    for name, relative, codec, space, offset in ASSETS:
        source_path = source / relative
        source_bytes = source_path.read_bytes()
        if codec == "raw":
            decoded = source_bytes
        elif codec == "png4bpp":
            decoded = pack_png_4bpp(source_path)
        elif codec == "jasc_palette":
            decoded = parse_jasc_palette(source_path)
        else:
            raise AssertionError(codec)
        artifact = output / f"{name}.bin"
        artifact.write_bytes(decoded)
        record = {
            "id": name,
            "source_path": relative,
            "source_sha256": digest(source_bytes),
            "codec": codec,
            "decoded_path": artifact.name,
            "decoded_bytes": len(decoded),
            "decoded_sha256": digest(decoded),
            "destination": {"space": space, "offset": f"0x{offset:05x}"},
        }
        if receipt_vram is not None and receipt_palette is not None:
            runtime = receipt_vram if space == "bg_vram" else receipt_palette
            observed = runtime[offset:offset + len(decoded)]
            record["runtime_receipt_comparison"] = {
                "compared_bytes": len(observed),
                "differing_bytes": sum(left != right for left, right in zip(decoded, observed)),
                "exact": decoded == observed,
            }
        records.append(record)
    manifest = {
        "schema": SCHEMA,
        "source_repository": "https://github.com/pret/pokeemerald",
        "source_revision": revision,
        "uploads": records,
        "dynamic_steps_not_exported": [
            "CopyToBgTilemapBuffer / BattlePutTextOnWindow text and window tiles",
            "healthbox and species sprite OBJ uploads plus OAM coordinates",
            "BattleMode0Surface logical BG0 scroll shadow",
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output / "manifest.json")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, help="optional external PPU receipt to compare, never to import")
    args = parser.parse_args()
    return export(args.source.resolve(), args.output.resolve(), args.receipt.resolve() if args.receipt else None)


if __name__ == "__main__":
    raise SystemExit(main())
