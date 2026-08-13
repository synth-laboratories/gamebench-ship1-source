#!/usr/bin/env python3
"""Fail-closed verification for an Emerald field-state sidecar receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from emerald_oracle_registry import load_registry


SCHEMA = "gamebench.pokemon_emerald.field_state_sidecar.v1"
TASK_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_PATH = Path(__file__).with_name("emerald_field_state_sidecar.py")
MANIFEST_PATH = TASK_ROOT / "fixtures/gold/emerald_field_state_observability.json"
EXPECTED_IMAGE_ID = "sha256:5995357b864e56df0715730a0ec2735d1a3f6af73d0bd90b87ee1b4f8bd7e0ed"


class FieldReceiptError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(receipt_path: Path, state: Path | None = None) -> dict[str, Any]:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FieldReceiptError(f"cannot read receipt: {exc}") from exc
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        raise FieldReceiptError("unsupported field-state receipt schema")
    reduced = dict(receipt)
    stored = reduced.pop("receipt_sha256", None)
    actual = hashlib.sha256(canonical_json(reduced).encode("utf-8")).hexdigest()
    if stored != actual:
        raise FieldReceiptError("receipt_sha256 does not validate")
    identity = receipt.get("identity")
    field_state = receipt.get("field_state")
    if not isinstance(identity, dict) or not isinstance(field_state, dict):
        raise FieldReceiptError("receipt lacks identity or field_state")
    registry, _ = load_registry()
    if identity.get("rom_sha256") != registry["rom_sha256"]:
        raise FieldReceiptError("receipt ROM is not registry-pinned")
    if identity.get("container_image_id") != EXPECTED_IMAGE_ID or identity.get(
        "container_image_id"
    ) != registry["oracle"]["config"].get("container_image_id"):
        raise FieldReceiptError("receipt did not use the registry-pinned v9 image")
    if identity.get("script_sha256") != file_sha256(SIDECAR_PATH):
        raise FieldReceiptError("receipt sidecar script hash is not current")
    if identity.get("symbol_manifest_sha256") != file_sha256(MANIFEST_PATH):
        raise FieldReceiptError("receipt symbol manifest hash is not current")
    if identity.get("initial_state_advance_frames") != 1:
        raise FieldReceiptError("receipt used an unsupported state boundary")
    state_sha = identity.get("state_sha256")
    if (
        not isinstance(state_sha, str)
        or len(state_sha) != 64
        or any(character not in "0123456789abcdef" for character in state_sha)
    ):
        raise FieldReceiptError("receipt state hash is malformed")
    if state is not None and (not state.is_file() or file_sha256(state) != state_sha):
        raise FieldReceiptError("receipt state does not match supplied state")
    flags = field_state.get("flags")
    expected_ids = {
        "FLAG_RECEIVED_RUNNING_SHOES": "0x112",
        "FLAG_SYS_B_DASH": "0x8c0",
    }
    if not isinstance(flags, dict) or set(flags) != set(expected_ids):
        raise FieldReceiptError("receipt flag set is incomplete or unexpected")
    try:
        save_block1 = int(field_state.get("save_block1_ptr"), 16)
    except (TypeError, ValueError) as exc:
        raise FieldReceiptError("save_block1_ptr is invalid") from exc
    if not 0x02000000 <= save_block1 < 0x02040000:
        raise FieldReceiptError("save_block1_ptr is outside EWRAM")
    for name, flag_id in expected_ids.items():
        value = flags[name]
        if not isinstance(value, dict) or value.get("flag_id") != flag_id:
            raise FieldReceiptError(f"{name} identity is invalid")
        if value.get("set") is not True:
            raise FieldReceiptError(f"{name} is not set")
        raw = value.get("raw_byte")
        mask_text = value.get("mask")
        try:
            mask = int(mask_text, 16)
        except (TypeError, ValueError) as exc:
            raise FieldReceiptError(f"{name} mask is invalid") from exc
        numeric_id = int(flag_id, 16)
        if mask != 1 << (numeric_id % 8):
            raise FieldReceiptError(f"{name} mask contradicts flag id")
        if value.get("address") != f"0x{save_block1 + 0x1270 + numeric_id // 8:08x}":
            raise FieldReceiptError(f"{name} address contradicts SaveBlock1 layout")
        if not isinstance(raw, int) or not raw & mask:
            raise FieldReceiptError(f"{name} raw byte contradicts set=true")
    return {
        "status": "validated",
        "receipt_sha256": stored,
        "state_sha256": state_sha,
        "flags": {name: True for name in expected_ids},
        "script_sha256": identity["script_sha256"],
        "symbol_manifest_sha256": identity["symbol_manifest_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--state", type=Path)
    args = parser.parse_args()
    try:
        print(canonical_json(verify(args.receipt, args.state)))
    except FieldReceiptError as exc:
        print(f"field-state receipt verification failed closed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
