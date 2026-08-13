#!/usr/bin/env python3
"""Fail-closed verification for an immutable Emerald checkpoint receipt.

This is deliberately ROM-free.  It lets a later route-capture invocation
resume from an already captured external mGBA state without re-running or
silently trusting the route program.  Live mGBA reload remains the capture
command's responsibility; this verifier checks the durable artifact graph:
receipt digest -> trace digest -> external raw snapshot digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from emerald_oracle_registry import (
    QUARANTINED_ADAPTER_SOURCE_SHA256,
    SUPERSEDED_ADAPTER_SOURCE_SHA256,
)


RECEIPT_SCHEMA = "gamebench.pokemon_emerald.oracle_snapshot_capture.v2"
TRACE_SCHEMA = "gamebench.pokemon_emerald.capture_vblank_trace.v1"


class ReceiptError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReceiptError(f"{label} root must be an object")
    return value


def digest_without(value: dict[str, Any], field: str) -> str:
    reduced = dict(value)
    stored = reduced.pop(field, None)
    if not isinstance(stored, str) or len(stored) != 64:
        raise ReceiptError(f"missing or malformed {field}")
    actual = hashlib.sha256(canonical_json(reduced).encode("utf-8")).hexdigest()
    if stored != actual:
        raise ReceiptError(f"{field} does not validate")
    return stored


def required_position(value: Any, label: str) -> None:
    if not isinstance(value, dict) or not all(
        isinstance(value.get(field), int)
        for field in ("map_group", "map_number", "player_x", "player_y")
    ):
        raise ReceiptError(f"{label} is missing map/player integer fields")


def verify(
    receipt_path: Path,
    state_override: Path | None = None,
    *,
    allow_superseded_identity: bool = False,
) -> dict[str, Any]:
    receipt = read_object(receipt_path, "receipt")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ReceiptError("unsupported receipt schema")
    receipt_sha = digest_without(receipt, "receipt_sha256")
    if receipt.get("round_trip") != "exact_no_input_continuation":
        raise ReceiptError("receipt does not prove exact reload continuation")
    if not isinstance(receipt.get("capture_tape_sha256"), str) or len(receipt["capture_tape_sha256"]) != 64:
        raise ReceiptError("receipt is missing capture_tape_sha256")
    identity = receipt.get("source_identity")
    if not isinstance(identity, dict) or not isinstance(identity.get("rom_sha256"), str) or not isinstance(identity.get("source_state_sha256"), str):
        raise ReceiptError("receipt is missing source identity")
    config = identity.get("config")
    if isinstance(config, dict) and config.get("adapter_source_sha256") in QUARANTINED_ADAPTER_SOURCE_SHA256:
        raise ReceiptError("receipt was produced by a quarantined adapter identity")
    superseded = (
        isinstance(config, dict)
        and config.get("adapter_source_sha256")
        in SUPERSEDED_ADAPTER_SOURCE_SHA256
    )
    if superseded and not allow_superseded_identity:
        raise ReceiptError(
            "receipt was produced by superseded adapter v7; "
            "it is audit-only until replayed under the pinned v9 identity"
        )
    required_position(receipt.get("terminal_source_position"), "terminal_source_position")
    expected_state_sha = receipt.get("snapshot_state_sha256")
    if not isinstance(expected_state_sha, str) or len(expected_state_sha) != 64:
        raise ReceiptError("receipt is missing snapshot_state_sha256")
    state_path = state_override or Path(str(receipt.get("snapshot_state_path", "")))
    if not state_path.is_absolute() or not state_path.is_file():
        raise ReceiptError("external snapshot state is unavailable; supply --state to relocate it")
    if file_sha256(state_path) != expected_state_sha:
        raise ReceiptError("external snapshot SHA-256 does not match receipt")
    trace_status = "not_recorded"
    trace_path_raw = receipt.get("capture_trace_path")
    if trace_path_raw is not None:
        trace_path = Path(str(trace_path_raw))
        trace = read_object(trace_path, "capture trace")
        if trace.get("schema") != TRACE_SCHEMA:
            raise ReceiptError("unsupported capture trace schema")
        trace_sha = digest_without(trace, "trace_sha256")
        if trace_sha != receipt.get("capture_trace_sha256"):
            raise ReceiptError("capture trace digest does not match receipt")
        if trace.get("capture_tape_sha256") != receipt.get("capture_tape_sha256"):
            raise ReceiptError("capture trace tape digest does not match receipt")
        if trace.get("source_identity") != identity:
            raise ReceiptError("capture trace source identity does not match receipt")
        if trace.get("terminal_snapshot_state_sha256") != expected_state_sha:
            raise ReceiptError("capture trace terminal state does not match receipt")
        if trace.get("terminal_source_position") != receipt.get("terminal_source_position"):
            raise ReceiptError("capture trace terminal position does not match receipt")
        trace_status = "validated"
    return {
        "status": "audit_only" if superseded else "validated",
        "receipt_sha256": receipt_sha,
        "snapshot_state_sha256": expected_state_sha,
        "snapshot_state_path": str(state_path),
        "from_checkpoint": receipt.get("from_checkpoint"),
        "promote_checkpoint": receipt.get("promote_checkpoint"),
        "terminal_source_position": receipt["terminal_source_position"],
        "trace": trace_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--state", type=Path, help="relocated external .state path")
    parser.add_argument(
        "--allow-superseded-identity",
        action="store_true",
        help="verify v7 artifact integrity but label it audit_only",
    )
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                verify(
                    args.receipt,
                    args.state,
                    allow_superseded_identity=args.allow_superseded_identity,
                ),
                sort_keys=True,
            )
        )
    except ReceiptError as exc:
        print(f"receipt verification failed closed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
