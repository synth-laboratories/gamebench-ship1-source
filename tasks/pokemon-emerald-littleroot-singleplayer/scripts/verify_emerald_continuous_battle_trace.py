#!/usr/bin/env python3
"""Verify an uninterrupted Emerald battle trace and its terminal snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from emerald_oracle_registry import load_registry
from verify_emerald_battle_memory_receipt import require_subset


SCHEMA = "gamebench.pokemon_emerald.continuous_battle_trace.v1"
TASK_ROOT = Path(__file__).resolve().parents[1]
TRACE_SCRIPT = Path(__file__).with_name("emerald_continuous_battle_trace.py")
SYMBOL_MANIFEST = TASK_ROOT / "fixtures/gold/emerald_battle_observability.json"
EXPECTED_IMAGE_ID = (
    "sha256:5995357b864e56df0715730a0ec2735d"
    "1a3f6af73d0bd90b87ee1b4f8bd7e0ed"
)


class ContinuousTraceError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(
    receipt_path: Path,
    input_state: Path,
    terminal_state: Path,
    tape_path: Path | None = None,
    expected_terminal_battle: Any | None = None,
) -> dict[str, Any]:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContinuousTraceError(f"cannot read trace receipt: {exc}") from exc
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        raise ContinuousTraceError("unsupported continuous trace schema")
    reduced = dict(receipt)
    stored = reduced.pop("receipt_sha256", None)
    actual = hashlib.sha256(canonical_json(reduced).encode("utf-8")).hexdigest()
    if stored != actual:
        raise ContinuousTraceError("receipt_sha256 does not validate")
    identity = receipt.get("identity")
    tape = receipt.get("tape")
    samples = receipt.get("samples")
    if not isinstance(identity, dict) or not isinstance(tape, dict):
        raise ContinuousTraceError("trace lacks identity or tape metadata")
    if not isinstance(samples, list) or not samples:
        raise ContinuousTraceError("trace has no samples")
    registry, _ = load_registry()
    if identity.get("rom_sha256") != registry["rom_sha256"]:
        raise ContinuousTraceError("trace ROM is not pinned")
    if identity.get("container_image_id") != EXPECTED_IMAGE_ID:
        raise ContinuousTraceError("trace image is not pinned v9")
    if identity.get("container_image_id") != registry["oracle"]["config"].get(
        "container_image_id"
    ):
        raise ContinuousTraceError("trace image differs from oracle registry")
    if identity.get("script_sha256") != file_sha256(TRACE_SCRIPT):
        raise ContinuousTraceError("continuous trace script hash mismatch")
    if identity.get("symbol_manifest_sha256") != file_sha256(SYMBOL_MANIFEST):
        raise ContinuousTraceError("battle symbol manifest hash mismatch")
    if identity.get("core_load_count") != 1:
        raise ContinuousTraceError("trace does not prove exactly one core load")
    if identity.get("intermediate_reload_count") != 0:
        raise ContinuousTraceError("trace contains an intermediate reload")
    if identity.get("initial_state_advance_frames") != 1:
        raise ContinuousTraceError("trace used an unsupported load boundary")
    if not input_state.is_file() or file_sha256(input_state) != identity.get(
        "input_state_sha256"
    ):
        raise ContinuousTraceError("input state hash mismatch")
    if not terminal_state.is_file() or file_sha256(terminal_state) != identity.get(
        "terminal_state_sha256"
    ):
        raise ContinuousTraceError("terminal state hash mismatch")
    if tape_path is not None and (
        not tape_path.is_file()
        or file_sha256(tape_path) != identity.get("tape_sha256")
    ):
        raise ContinuousTraceError("tape hash mismatch")
    vblank_count = tape.get("vblank_count")
    if not isinstance(vblank_count, int) or vblank_count < 0:
        raise ContinuousTraceError("invalid tape VBlank count")
    if receipt.get("sample_count") != vblank_count + 1 or len(samples) != vblank_count + 1:
        raise ContinuousTraceError("trace is not sampled on every VBlank")
    for expected_vblank, sample in enumerate(samples):
        if not isinstance(sample, dict) or sample.get("vblank") != expected_vblank:
            raise ContinuousTraceError("sample VBlank sequence is discontinuous")
        if not isinstance(sample.get("battle"), dict):
            raise ContinuousTraceError("sample lacks battle memory")
    if expected_terminal_battle is not None:
        try:
            require_subset(expected_terminal_battle, samples[-1]["battle"])
        except Exception as exc:
            raise ContinuousTraceError(str(exc)) from exc
    return {
        "status": "validated_continuous",
        "receipt_sha256": stored,
        "input_state_sha256": identity["input_state_sha256"],
        "terminal_state_sha256": identity["terminal_state_sha256"],
        "tape_sha256": identity["tape_sha256"],
        "vblank_count": vblank_count,
        "sample_count": len(samples),
        "marker_count": tape.get("marker_count"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--input-state", type=Path, required=True)
    parser.add_argument("--terminal-state", type=Path, required=True)
    parser.add_argument("--tape", type=Path)
    parser.add_argument("--expect-terminal-battle-json")
    args = parser.parse_args()
    try:
        expected = (
            json.loads(args.expect_terminal_battle_json)
            if args.expect_terminal_battle_json is not None
            else None
        )
        print(
            canonical_json(
                verify(
                    args.receipt,
                    args.input_state,
                    args.terminal_state,
                    args.tape,
                    expected,
                )
            )
        )
    except (ContinuousTraceError, json.JSONDecodeError) as exc:
        print(f"continuous trace verification failed closed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
