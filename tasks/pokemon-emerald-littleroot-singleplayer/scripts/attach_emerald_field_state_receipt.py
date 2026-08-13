#!/usr/bin/env python3
"""Attach a verified field-state receipt to an authenticated checkpoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from emerald_oracle_registry import DEFAULT_REGISTRY_PATH, load_registry
from verify_emerald_field_state_receipt import FieldReceiptError, verify


class AttachError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    registry, checkpoints = load_registry()
    checkpoint = checkpoints.get(args.checkpoint)
    if checkpoint is None or not checkpoint.authenticated or checkpoint.source is None:
        raise AttachError("checkpoint must already be authenticated")
    result = verify(args.receipt)
    if result["state_sha256"] != checkpoint.source["state_sha256"]:
        raise AttachError("field-state receipt does not match checkpoint source")

    raw = json.loads(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    row = next(item for item in raw["checkpoints"] if item["id"] == args.checkpoint)
    capture = row.setdefault("capture", {})
    if "field_state_assertion" in capture:
        raise AttachError("checkpoint already has a field_state_assertion")
    capture["field_state_assertion"] = {
        "status": "verified_external_sidecar",
        "receipt_path": str(args.receipt.resolve()),
        "receipt_sha256": result["receipt_sha256"],
        "state_sha256": result["state_sha256"],
        "script_sha256": result["script_sha256"],
        "symbol_manifest_sha256": result["symbol_manifest_sha256"],
        "expected_flags": result["flags"],
    }
    temporary = DEFAULT_REGISTRY_PATH.with_name(
        DEFAULT_REGISTRY_PATH.name + ".field-sidecar-partial"
    )
    if temporary.exists():
        raise AttachError(f"temporary registry path already exists: {temporary}")
    temporary.write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, DEFAULT_REGISTRY_PATH)
    print(json.dumps(capture["field_state_assertion"], sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttachError, FieldReceiptError, json.JSONDecodeError) as exc:
        raise SystemExit(f"field-state receipt attachment failed: {exc}")
