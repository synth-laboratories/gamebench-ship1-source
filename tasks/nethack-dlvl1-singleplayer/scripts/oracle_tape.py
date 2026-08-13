#!/usr/bin/env python3
"""Integrity and provenance helpers for authoritative frozen NLE tapes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))
RAW_TAPE_FILES = ("meta.json", "level_dump.json", "actions.jsonl", "snapshots.jsonl")
MANIFEST_FILE = "tape_manifest.json"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path.name}:{number} must contain an object")
        records.append(value)
    return records


def oracle_identity() -> dict[str, Any]:
    return json.loads((TASK_DIR / "shared" / "oracle_identity.json").read_text())


def capture_runtime_identity(nle_module: Any) -> dict[str, Any]:
    """Fingerprint the actual runtime used to produce a new oracle tape."""

    distribution = importlib.metadata.distribution("nle")
    binaries: dict[str, str] = {}
    for relative in distribution.files or ():
        name = str(relative)
        if name.endswith((".so", ".dylib", ".dll")) or name == "nle/nethack/actions.py":
            path = Path(distribution.locate_file(relative)).resolve()
            if path.is_file():
                binaries[name] = sha256_file(path)
    record = Path(distribution._path) / "RECORD"  # type: ignore[attr-defined]
    capture_script = Path(__file__).with_name("capture_nle_fixture.py")
    return {
        "schema": "gamebench.nethack.capture_runtime.v1",
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable_sha256": sha256_file(Path(sys.executable).resolve()),
        },
        "platform": platform.platform(),
        "nle_distribution_record_sha256": sha256_file(record),
        "nle_runtime_files_sha256": binaries,
        "capture_script_sha256": sha256_file(capture_script),
        "oracle_source_artifact": oracle_identity()["oracle"]["source_artifact"],
    }


def _terminal_evidence(projection: dict[str, Any]) -> dict[str, Any]:
    return {
        "tty_chars": projection.get("tty_chars", []),
        "tty_colors": projection.get("tty_colors", []),
        "tty_cursor_yx": projection.get("tty_cursor_yx", []),
    }


def build_manifest(fixture_dir: Path) -> dict[str, Any]:
    from scripts.native_pre_action_evidence import SIDECAR_FILE, manifest_provenance, validate_records
    from scripts.source_pager_evidence import (
        SIDECAR_FILE as SOURCE_PAGER_SIDECAR_FILE,
        manifest_provenance as source_pager_manifest_provenance,
        validate_source_pager_evidence,
    )
    from scripts.native_reset_entity_state import (
        SIDECAR_FILE as RESET_ENTITY_SIDECAR_FILE,
        manifest_provenance as reset_entity_manifest_provenance,
        validate_reset_entity_state,
    )

    meta = json.loads((fixture_dir / "meta.json").read_text())
    actions = load_jsonl(fixture_dir / "actions.jsonl")
    snapshots = load_jsonl(fixture_dir / "snapshots.jsonl")
    if len(snapshots) != len(actions) + 1:
        raise ValueError("tape must contain reset plus one snapshot per action")

    turns: list[dict[str, Any]] = []
    for index, action in enumerate(actions, start=1):
        before = snapshots[index - 1]
        after = snapshots[index]
        turns.append(
            {
                "step": index,
                "input": action,
                "input_sha256": sha256_json(action),
                "source_state_sha256": sha256_json(before),
                "result_state_sha256": sha256_json(after),
                "terminal_ui_evidence_sha256": sha256_json(_terminal_evidence(after.get("projection", {}))),
            }
        )

    runtime = meta.get("capture_runtime")
    sidecar_path = fixture_dir / SIDECAR_FILE
    records = load_jsonl(sidecar_path) if sidecar_path.is_file() else []
    native_failures = validate_records(
        records,
        actions,
        fixture_id=str(meta.get("fixture_id", fixture_dir.name)),
        runtime=runtime if isinstance(runtime, dict) else None,
        require_native=sidecar_path.is_file(),
    )
    if native_failures:
        raise ValueError("; ".join(native_failures))
    source_pager_path = fixture_dir / SOURCE_PAGER_SIDECAR_FILE
    source_pager_payload = json.loads(source_pager_path.read_text()) if source_pager_path.is_file() else None
    source_pager_report = validate_source_pager_evidence(
        source_pager_payload,
        fixture_id=str(meta.get("fixture_id", fixture_dir.name)),
        native_records=records if sidecar_path.is_file() else None,
    )
    if source_pager_report["errors"]:
        raise ValueError("; ".join(str(error) for error in source_pager_report["errors"]))
    reset_entity_path = fixture_dir / RESET_ENTITY_SIDECAR_FILE
    reset_entity_record = json.loads(reset_entity_path.read_text()) if reset_entity_path.is_file() else None
    if reset_entity_record is not None and not isinstance(reset_entity_record, dict):
        raise ValueError("native reset entity state must be a JSON object")
    reset_entity_failures = validate_reset_entity_state(
        reset_entity_record,
        fixture_id=str(meta.get("fixture_id", fixture_dir.name)),
        runtime=runtime if isinstance(runtime, dict) else None,
        level_dump=json.loads((fixture_dir / "level_dump.json").read_text()),
        actions=actions,
        reset_projection=snapshots[0].get("projection", {}),
        # Missing is a v1 compatibility outcome; a newly captured v2 tape
        # writes the file and is rejected if its receipt does not validate.
        require_native=reset_entity_path.is_file(),
    )
    if reset_entity_failures:
        raise ValueError("; ".join(reset_entity_failures))
    raw_files = (*RAW_TAPE_FILES, SIDECAR_FILE) if sidecar_path.is_file() else RAW_TAPE_FILES
    if reset_entity_path.is_file():
        raw_files = (*raw_files, RESET_ENTITY_SIDECAR_FILE)
    if source_pager_path.is_file():
        raw_files = (*raw_files, SOURCE_PAGER_SIDECAR_FILE)
    manifest = {
        "schema": "gamebench.nethack.oracle_tape_manifest.v1",
        "fixture_id": meta.get("fixture_id", fixture_dir.name),
        "oracle_identity": oracle_identity(),
        "capture_runtime": runtime
        if isinstance(runtime, dict)
        else {
            "status": "legacy_version_only",
            "limitation": "The historical capture predates exact binary/runtime fingerprinting.",
            "nle_version": meta.get("nle_version"),
            "nethack_version": meta.get("nethack_version"),
        },
        "files_sha256": {name: sha256_file(fixture_dir / name) for name in raw_files},
        "native_pre_action_evidence": manifest_provenance(records),
        "reset_state_sha256": sha256_json(snapshots[0]),
        "turns": turns,
        "terminal_state_sha256": sha256_json(snapshots[-1]),
    }
    # Keep old v1 manifests byte-stable: absence means the explicit legacy
    # outcome.  A v2 capture always carries this field and hashes its receipt.
    if reset_entity_path.is_file():
        manifest["native_reset_entity_state"] = reset_entity_manifest_provenance(reset_entity_record)
    if source_pager_path.is_file():
        manifest["source_pager_evidence"] = source_pager_manifest_provenance(source_pager_payload, source_pager_report)
    return manifest


def write_manifest(fixture_dir: Path) -> Path:
    destination = fixture_dir / MANIFEST_FILE
    destination.write_text(json.dumps(build_manifest(fixture_dir), indent=2, sort_keys=True) + "\n")
    return destination


def validate_manifest(fixture_dir: Path) -> list[str]:
    path = fixture_dir / MANIFEST_FILE
    if not path.is_file():
        return [f"{fixture_dir.name}: missing {MANIFEST_FILE}"]
    try:
        actual = json.loads(path.read_text())
        expected = build_manifest(fixture_dir)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"{fixture_dir.name}: invalid oracle tape: {error}"]
    if actual != expected:
        return [
            f"{fixture_dir.name}: {MANIFEST_FILE} does not match raw tape bytes; "
            "refuse replay until the tape is deliberately re-manifested"
        ]
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=TASK_DIR / "fixtures" / "nle_oracle")
    parser.add_argument("--write", action="store_true", help="Write or deliberately refresh manifests.")
    args = parser.parse_args()
    fixtures = sorted(path.parent for path in args.root.resolve().rglob("meta.json"))
    if not fixtures:
        raise SystemExit("oracle tape guard: zero fixtures found")
    failures: list[str] = []
    for fixture in fixtures:
        if args.write:
            write_manifest(fixture)
        failures.extend(validate_manifest(fixture))
    if failures:
        raise SystemExit("oracle tape integrity FAILED\n" + "\n".join(failures))
    print(json.dumps({"status": "pass", "fixtures": len(fixtures), "written": args.write}, sort_keys=True))


if __name__ == "__main__":
    main()
