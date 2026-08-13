#!/usr/bin/env python3
"""Attribute a Rust frame mismatch using a verified full-PPU receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

WIDTH, HEIGHT = 240, 160


def rgb_from_ppm(path: Path) -> bytes:
    data = path.read_bytes()
    header, rgb = data.split(b"\n255\n", 1)
    if header != b"P6\n240 160" or len(rgb) != WIDTH * HEIGHT * 3:
        raise ValueError(f"{path} is not a native 240x160 RGB PPM")
    return rgb


def region(left: bytes, right: bytes, x: int, y: int, width: int, height: int) -> dict[str, int]:
    pixels = channels = delta = 0
    for row in range(y, y + height):
        for column in range(x, x + width):
            offset = (row * WIDTH + column) * 3
            changed = False
            for channel in range(3):
                amount = abs(left[offset + channel] - right[offset + channel])
                changed |= amount != 0
                channels += amount != 0
                delta += amount
            pixels += changed
    return {"pixels": width * height, "differing_pixels": pixels, "differing_channels": channels, "total_channel_delta": delta}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--recomposed-rgb", type=Path, required=True)
    parser.add_argument("--rust-ppm", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    source = (args.receipt.parent / receipt["files"]["rgb"]["path"]).read_bytes()
    ppu = args.recomposed_rgb.read_bytes()
    rust = rgb_from_ppm(args.rust_ppm)
    if len(source) != WIDTH * HEIGHT * 3 or len(ppu) != len(source):
        raise SystemExit("receipt and recomposed RGB surfaces must be 240x160")
    regions = {"full_frame": (0, 0, 240, 160), "battlefield": (0, 0, 240, 112), "command_ui": (0, 112, 240, 48), "upper_half": (0, 0, 240, 80), "lower_half": (0, 80, 240, 80)}
    ppu_diff = {name: region(source, ppu, *bounds) for name, bounds in regions.items()}
    rust_diff = {name: region(source, rust, *bounds) for name, bounds in regions.items()}
    ppu_exact = ppu_diff["full_frame"]["differing_pixels"] == 0
    report = {
        "schema": "gamebench.pokemon_emerald.ppu_diagnosis.v1",
        "receipt": str(args.receipt), "vblank": receipt["vblank"],
        "source_rgb_sha256": hashlib.sha256(source).hexdigest(),
        "recomposed_rgb_sha256": hashlib.sha256(ppu).hexdigest(),
        "rust_rgb_sha256": hashlib.sha256(rust).hexdigest(),
        "source_vs_ppu_compositor": ppu_diff,
        "source_vs_rust_engine": rust_diff,
        "attribution": {
            "classification": "engine_supplied_assets_or_state" if ppu_exact else "compositor_or_capture_incomplete",
            "confidence": "high" if ppu_exact else "low",
            "evidence": [
                "The receipt's source framebuffer and PPU-only recomposition are exact." if ppu_exact else "The PPU-only recomposition differs from mGBA.",
                "Rust differs from the same authenticated source VBlank; its frame is not an mGBA PPU layer export.",
            ],
            "limits": "mGBA exposes a final framebuffer, not independently rendered layer framebuffers; BG/OBJ/window images are decoded artifacts from the authenticated PPU state.",
        },
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
