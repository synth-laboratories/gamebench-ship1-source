#!/usr/bin/env python3
"""Fail-closed verifier for external full-PPU receipt artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from emerald_oracle_registry import DEFAULT_REGISTRY_PATH, RegistryError, require_trusted_oracle, resolve_checkpoint

SCHEMA = "gamebench.pokemon_emerald.ppu_receipt.v2"
REQUIRED_FILES = {"rgb": 240 * 160 * 3, "io": 0x60, "vram": 0x18000, "palette": 0x400, "oam": 0x400}


class ReceiptError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(receipt_path: Path, registry_path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"cannot read receipt: {exc}") from exc
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        raise ReceiptError("unsupported PPU receipt schema")
    identity = receipt.get("source_identity")
    if not isinstance(identity, dict):
        raise ReceiptError("receipt has no source identity")
    try:
        registry, checkpoint = resolve_checkpoint(identity.get("checkpoint"), registry_path)
        require_trusted_oracle(registry)
    except RegistryError as exc:
        raise ReceiptError(f"receipt identity is not trusted: {exc}") from exc
    source = checkpoint.source
    config = registry["oracle"]["config"]
    if not checkpoint.authenticated or source is None:
        raise ReceiptError("receipt checkpoint is not authenticated")
    expected = {
        "rom_sha256": registry["rom_sha256"],
        "state_sha256": source["state_sha256"],
        "adapter_source_sha256": config["adapter_source_sha256"],
        "observability_source_sha256": config["observability_source_sha256"],
    }
    for key, value in expected.items():
        if identity.get(key) != value:
            raise ReceiptError(f"receipt {key} does not match the trusted v8 identity")
    if identity.get("registry_sha256") != sha256_file(registry_path):
        raise ReceiptError("receipt registry digest does not match the supplied registry")
    fresh = receipt.get("fresh_replay")
    if not isinstance(fresh, dict) or fresh.get("status") != "exact":
        raise ReceiptError("receipt lacks an exact fresh-replay attestation")
    if fresh.get("frame_rgb_sha256") != receipt.get("frame_rgb_sha256"):
        raise ReceiptError("fresh replay RGB hash does not match receipt")
    state = receipt.get("source_state")
    if not isinstance(state, dict) or fresh.get("source_state_sha256") != state.get("state_sha256"):
        raise ReceiptError("fresh replay source-state hash does not match receipt")
    files = receipt.get("files")
    if not isinstance(files, dict):
        raise ReceiptError("receipt has no file manifest")
    root = receipt_path.parent
    for name, expected_size in REQUIRED_FILES.items():
        entry = files.get(name)
        if not isinstance(entry, dict) or entry.get("bytes") != expected_size:
            raise ReceiptError(f"receipt {name} has an invalid byte count")
        path = root / str(entry.get("path", ""))
        if path.parent != root or not path.is_file():
            raise ReceiptError(f"receipt {name} does not name a local evidence file")
        if path.stat().st_size != expected_size or sha256_file(path) != entry.get("sha256"):
            raise ReceiptError(f"receipt {name} hash does not validate")
    registers = receipt.get("registers")
    required_registers = ("dispcnt", "bgcnt", "bg_offsets", "bg2_affine", "bg3_affine", "win0h", "win1h", "win0v", "win1v", "winin", "winout", "mosaic", "bldcnt", "bldalpha", "bldy")
    if not isinstance(registers, dict) or any(key not in registers for key in required_registers):
        raise ReceiptError("receipt is not a full PPU register capture")
    return {"status": "validated", "checkpoint": checkpoint.checkpoint_id, "vblank": receipt.get("vblank"), "frame_rgb_sha256": receipt["frame_rgb_sha256"], "source_state_sha256": state["state_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.receipt, args.registry), sort_keys=True))
    except ReceiptError as exc:
        print(f"PPU receipt verification failed closed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
