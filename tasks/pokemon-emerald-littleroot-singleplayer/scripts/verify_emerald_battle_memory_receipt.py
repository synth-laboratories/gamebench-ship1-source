#!/usr/bin/env python3
"""Verify a hash-bound Emerald battle-memory sidecar receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from emerald_oracle_registry import load_registry


SCHEMA = "gamebench.pokemon_emerald.battle_memory_sidecar.v1"
TASK_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_PATH = Path(__file__).with_name("emerald_battle_memory_sidecar.py")
SYMBOL_MANIFEST_PATH = (
    TASK_ROOT / "fixtures/gold/emerald_battle_observability.json"
)
EXPECTED_IMAGE_ID = (
    "sha256:5995357b864e56df0715730a0ec2735d"
    "1a3f6af73d0bd90b87ee1b4f8bd7e0ed"
)


class BattleReceiptError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_subset(expected: Any, actual: Any, path: str = "battle") -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise BattleReceiptError(f"{path} expected an object")
        for key, value in expected.items():
            if key not in actual:
                raise BattleReceiptError(f"{path}.{key} is missing")
            require_subset(value, actual[key], f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) > len(actual):
            raise BattleReceiptError(f"{path} expected a compatible list")
        for index, value in enumerate(expected):
            require_subset(value, actual[index], f"{path}[{index}]")
        return
    if actual != expected:
        raise BattleReceiptError(
            f"{path} mismatch: expected {expected!r}, got {actual!r}"
        )


def verify(
    receipt_path: Path,
    state_override: Path | None = None,
    expected_battle: Any | None = None,
) -> dict[str, Any]:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BattleReceiptError(f"cannot read receipt: {exc}") from exc
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        raise BattleReceiptError("unsupported battle receipt schema")
    reduced = dict(receipt)
    stored_digest = reduced.pop("receipt_sha256", None)
    actual_digest = hashlib.sha256(
        canonical_json(reduced).encode("utf-8")
    ).hexdigest()
    if stored_digest != actual_digest:
        raise BattleReceiptError("receipt_sha256 does not validate")

    identity = receipt.get("identity")
    battle = receipt.get("battle")
    if not isinstance(identity, dict) or not isinstance(battle, dict):
        raise BattleReceiptError("receipt lacks identity or battle object")
    registry, _ = load_registry()
    if identity.get("rom_sha256") != registry["rom_sha256"]:
        raise BattleReceiptError("receipt ROM is not registry-pinned")
    if identity.get("container_image_id") != EXPECTED_IMAGE_ID:
        raise BattleReceiptError("receipt did not use pinned v9 image")
    if identity.get("container_image_id") != registry["oracle"]["config"].get(
        "container_image_id"
    ):
        raise BattleReceiptError("receipt image differs from current oracle registry")
    if identity.get("script_sha256") != file_sha256(SIDECAR_PATH):
        raise BattleReceiptError("receipt sidecar script hash is not current")
    if identity.get("symbol_manifest_sha256") != file_sha256(
        SYMBOL_MANIFEST_PATH
    ):
        raise BattleReceiptError("receipt symbol manifest hash is not current")
    if identity.get("initial_state_advance_frames") != 1:
        raise BattleReceiptError("receipt used an unsupported state boundary")
    state_sha = identity.get("state_sha256")
    if not isinstance(state_sha, str) or len(state_sha) != 64:
        raise BattleReceiptError("receipt state hash is malformed")
    if state_override is not None:
        if not state_override.is_file() or file_sha256(state_override) != state_sha:
            raise BattleReceiptError("receipt state does not match supplied state")
    count = battle.get("battlers_count")
    mons = battle.get("mons")
    if not isinstance(count, int) or not 0 <= count <= 4:
        raise BattleReceiptError("invalid battlers_count")
    if not isinstance(mons, list) or len(mons) != count:
        raise BattleReceiptError("battle mon count is inconsistent")
    if expected_battle is not None:
        require_subset(expected_battle, battle)
    return {
        "status": "validated",
        "receipt_sha256": stored_digest,
        "state_sha256": state_sha,
        "battlers_count": count,
        "script_sha256": identity["script_sha256"],
        "symbol_manifest_sha256": identity["symbol_manifest_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument(
        "--expect-battle-json",
        help="JSON object/list subset that must match receipt.battle",
    )
    args = parser.parse_args()
    try:
        expected = (
            json.loads(args.expect_battle_json)
            if args.expect_battle_json is not None
            else None
        )
        print(
            canonical_json(
                verify(args.receipt, args.state, expected)
            )
        )
    except (BattleReceiptError, json.JSONDecodeError) as exc:
        print(f"battle receipt verification failed closed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
