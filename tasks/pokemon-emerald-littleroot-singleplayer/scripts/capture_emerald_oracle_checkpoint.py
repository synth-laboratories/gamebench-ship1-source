#!/usr/bin/env python3
"""Capture and authenticate a named mGBA checkpoint without committing its state.

The capture starts at an *already authenticated* registry checkpoint, replays a
concrete VBlank program, asks the pinned adapter to save a raw mGBA state into
an explicit non-repository host path, and proves continuation equivalence by
loading that snapshot through a fresh adapter process. Only then can it promote
a ``capture_required`` registry row.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from emerald_oracle_registry import (  # noqa: E402
    DEFAULT_REGISTRY_PATH,
    OracleCheckpoint,
    RegistryError,
    canonical_json,
    file_sha256,
    initial_state_matches,
    load_registry,
    require_trusted_oracle,
    require_authenticated,
    resolve_checkpoint,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
RGB_BYTES = 240 * 160 * 3
VALID_BUTTONS = {"a", "b", "select", "start", "right", "left", "up", "down", "r", "l"}
CONTAINER_SNAPSHOT_DIR = Path("/oracle-output")
RECEIPT_SCHEMA = "gamebench.pokemon_emerald.oracle_snapshot_capture.v2"
TRACE_SCHEMA = "gamebench.pokemon_emerald.capture_vblank_trace.v1"


class CaptureError(RuntimeError):
    """A capture is incomplete or unauthenticated and cannot be promoted."""


def checked_response(process: subprocess.Popen[str]) -> dict[str, Any]:
    if process.stdout is None:
        raise CaptureError("oracle stdout was not opened")
    line = process.stdout.readline()
    if not line:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise CaptureError(f"oracle closed its JSONL stream: {stderr.strip()}")
    try:
        response = json.loads(line)
    except json.JSONDecodeError as exc:
        raise CaptureError(f"oracle returned invalid JSON: {line!r}") from exc
    if not isinstance(response, dict) or response.get("ok") is not True:
        raise CaptureError(f"oracle error: {response}")
    return response


def send(process: subprocess.Popen[str], request: dict[str, Any]) -> dict[str, Any]:
    if process.stdin is None:
        raise CaptureError("oracle stdin was not opened")
    process.stdin.write(canonical_json(request) + "\n")
    process.stdin.flush()
    return checked_response(process)


def close(process: subprocess.Popen[str]) -> None:
    if process.stdin is not None and not process.stdin.closed:
        process.stdin.close()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)


def checked_rgb(response: dict[str, Any]) -> str:
    encoded = response.get("frame_rgb_b64")
    if not isinstance(encoded, str):
        raise CaptureError("oracle response has no frame_rgb_b64")
    try:
        rgb = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise CaptureError("oracle response frame_rgb_b64 is not base64") from exc
    if len(rgb) != RGB_BYTES:
        raise CaptureError(f"oracle returned {len(rgb)} RGB bytes; expected {RGB_BYTES}")
    digest = hashlib.sha256(rgb).hexdigest()
    if response.get("frame_rgb_sha256") != digest:
        raise CaptureError("oracle frame_rgb_sha256 does not match RGB bytes")
    return digest


def verify_identity(
    response: dict[str, Any], registry: dict[str, Any], expected_rom_sha: str
) -> None:
    if response.get("rom_sha256") != expected_rom_sha:
        raise CaptureError("oracle loaded a ROM other than the registry-pinned source")
    emulator = response.get("emulator")
    config = response.get("config")
    if emulator != registry["oracle"]["emulator"] or config != registry["oracle"]["config"]:
        raise CaptureError("oracle emulator/config identity does not match the registry")
    if not isinstance(emulator, dict):
        raise CaptureError("oracle response has no emulator identity")
    if emulator.get("config_sha256") != hashlib.sha256(
        canonical_json(config).encode("utf-8")
    ).hexdigest():
        raise CaptureError("oracle config_sha256 does not authenticate returned config")


def expand_program(tape_path: Path) -> tuple[list[list[str]], str]:
    try:
        raw = json.loads(tape_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError(f"cannot read concrete capture tape {tape_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise CaptureError("capture tape root must be an object")
    program = raw.get("program")
    if not isinstance(program, list):
        raise CaptureError("capture tape must contain a program list")
    ticks: list[list[str]] = []
    for index, segment in enumerate(program):
        if not isinstance(segment, dict):
            raise CaptureError(f"capture tape program[{index}] must be an object")
        buttons = segment.get("buttons", [])
        frames = segment.get("frames")
        if not isinstance(buttons, list) or not all(isinstance(button, str) for button in buttons):
            raise CaptureError(f"capture tape program[{index}].buttons must be a string list")
        if len(buttons) != len(set(buttons)) or set(buttons) - VALID_BUTTONS:
            raise CaptureError(f"capture tape program[{index}] has invalid buttons")
        if not isinstance(frames, int) or frames < 1:
            raise CaptureError(f"capture tape program[{index}].frames must be positive")
        ticks.extend([buttons] * frames)
    return ticks, file_sha256(tape_path)


def tape_metadata(tape_path: Path) -> dict[str, Any]:
    """Optional routing labels copied into receipts; never inferred from Rust."""
    try:
        raw = json.loads(tape_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError(f"cannot read concrete capture tape {tape_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise CaptureError("capture tape root must be an object")
    metadata: dict[str, Any] = {
        key: raw[key]
        for key in ("id", "coverage_segment")
        if isinstance(raw.get(key), str) and raw[key]
    }
    assertions = raw.get("source_assertions")
    if assertions is not None:
        if not isinstance(assertions, dict):
            raise CaptureError("capture tape source_assertions must be an object")
        metadata["source_assertions"] = assertions
    return metadata


def _require_subset(expected: Any, actual: Any, path: str) -> list[str]:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise CaptureError(f"{path} expected an object")
        validated: list[str] = []
        for key, value in expected.items():
            if key not in actual:
                raise CaptureError(f"{path}.{key} is missing from source state")
            validated.extend(_require_subset(value, actual[key], f"{path}.{key}"))
        return validated
    if actual != expected:
        raise CaptureError(
            f"{path} mismatch: expected {expected!r}, got {actual!r}"
        )
    return [path]


def validate_terminal_source_assertions(
    metadata: dict[str, Any], source_state: dict[str, Any]
) -> None:
    """Enforce assertions backed by raw v8 source observations.

    Historical tapes contain descriptive counters such as
    ``minimum_dialogue_pages`` that the adapter cannot directly observe. They
    remain signed into the tape but are explicitly listed as unverified; only
    position and observability subsets can be capture gates.
    """
    assertions = metadata.get("source_assertions")
    if not isinstance(assertions, dict):
        return
    validated: list[str] = []
    position = assertions.get("terminal_source_position")
    if position is not None:
        validated.extend(
            _require_subset(
                position, source_position(source_state), "terminal_source_position"
            )
        )
    observability = assertions.get("terminal_observability")
    if observability is not None:
        validated.extend(
            _require_subset(
                observability,
                source_state.get("observability"),
                "terminal_observability",
            )
        )
    supported = {"terminal_source_position", "terminal_observability"}
    unverified = sorted(set(assertions) - supported)
    metadata["assertion_validation"] = {
        "validated_paths": sorted(validated),
        "unverified_keys": unverified,
    }


def source_position(source_state: dict[str, Any]) -> dict[str, int]:
    """Return the minimum portable semantic boundary recorded in a receipt."""
    required = ("player_x", "player_y", "map_group", "map_number")
    if not all(isinstance(source_state.get(field), int) for field in required):
        raise CaptureError("source state lacks required player/map integers")
    return {field: source_state[field] for field in required}


def trace_frame(response: dict[str, Any], vblank: int, buttons: list[str]) -> dict[str, Any]:
    state = response.get("source_state")
    if not isinstance(state, dict):
        raise CaptureError("oracle response lacks source_state for capture trace")
    return {
        "vblank": vblank,
        "buttons": list(buttons),
        "frame_rgb_sha256": checked_rgb(response),
        "source_state": state,
    }


def write_new_json(path: Path, value: dict[str, Any], label: str) -> None:
    """Write an immutable external evidence artifact after all verification passes."""
    if path.exists():
        raise CaptureError(f"refusing to overwrite existing {label}: {path}")
    if not path.is_absolute() or not path.parent.is_dir():
        raise CaptureError(f"{label} must be an absolute path whose parent exists: {path}")
    if TASK_ROOT == path.parent or TASK_ROOT in path.parents:
        raise CaptureError(f"{label} must stay outside the task repository")
    temporary = path.with_name(path.name + ".partial")
    if temporary.exists():
        raise CaptureError(f"refusing to replace pre-existing {label} temporary path: {temporary}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def start_oracle(
    launcher: Path,
    rom_path: Path,
    source_state_path: Path,
    checkpoint_id: str,
    snapshot_directory: Path,
) -> subprocess.Popen[str]:
    if not launcher.is_file():
        raise CaptureError(f"oracle launcher not found: {launcher}")
    return subprocess.Popen(
        [
            str(launcher),
            str(rom_path),
            str(source_state_path),
            checkpoint_id,
            str(snapshot_directory),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )


def load_source(
    process: subprocess.Popen[str], rom_path: Path, state_path: str
) -> dict[str, Any]:
    response = send(
        process,
        {"op": "load", "rom_path": str(rom_path), "state_path": state_path},
    )
    if response.get("frame_number") != 0:
        raise CaptureError("oracle load did not establish frame_number 0")
    checked_rgb(response)
    return response


def promote(
    *,
    registry_path: Path,
    target_id: str,
    source_state_sha256: str,
    initial_rgb_sha256: str,
    initial_source_state: dict[str, Any],
    from_checkpoint: str,
    tape_sha256: str,
    snapshot_frame_number: int,
    receipt_sha256: str | None = None,
    trace_sha256: str | None = None,
) -> None:
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError(f"cannot reload registry for promotion: {exc}") from exc
    checkpoints = raw.get("checkpoints")
    if not isinstance(checkpoints, list):
        raise CaptureError("registry checkpoints are malformed during promotion")
    target = next((item for item in checkpoints if item.get("id") == target_id), None)
    if not isinstance(target, dict):
        raise CaptureError(f"target checkpoint disappeared from registry: {target_id}")
    target_status = target.get("status")
    if target_status not in {"capture_required", "quarantined_provenance"}:
        raise CaptureError(
            f"target checkpoint {target_id} is not an unpromoted capture_required or re-authenticatable quarantined_provenance row"
        )
    if target_status == "capture_required" and target.get("source") is not None:
        raise CaptureError(f"target checkpoint {target_id} is not an unpromoted capture_required row")
    required = ("player_x", "player_y", "map_group", "map_number")
    if not all(isinstance(initial_source_state.get(field), int) for field in required):
        raise CaptureError("snapshot reload lacks required source position/map fields")
    capture = target.setdefault("capture", {})
    if not isinstance(capture, dict):
        raise CaptureError(f"target checkpoint {target_id} capture metadata is malformed")
    if target_status == "quarantined_provenance":
        # Keep the old adapter identity auditable while replacing it with the
        # freshly verified receipt below.  Re-authentication is intentionally
        # limited to provenance quarantine; mislabeled or capture-required
        # rows cannot be silently rewritten.
        old_provenance = capture.get("provenance")
        if isinstance(old_provenance, dict):
            capture.setdefault("superseded_provenance", old_provenance)
    target["status"] = "authenticated"
    target["source"] = {
        "state_sha256": source_state_sha256,
        "initial_rgb_sha256": initial_rgb_sha256,
        "initial_state": {field: initial_source_state[field] for field in required},
    }
    capture["provenance"] = {
        "captured_from_authenticated_checkpoint": from_checkpoint,
        "capture_tape_sha256": tape_sha256,
        "snapshot_frame_number": snapshot_frame_number,
        "round_trip": "fresh adapter reload matched one no-input continuation frame and source_state",
    }
    if receipt_sha256 is not None:
        capture["provenance"]["receipt_sha256"] = receipt_sha256
    if trace_sha256 is not None:
        capture["provenance"]["capture_trace_sha256"] = trace_sha256
    temporary_path = registry_path.with_name(registry_path.name + ".capture-partial")
    if temporary_path.exists():
        raise CaptureError(f"refusing to replace pre-existing registry temporary path: {temporary_path}")
    temporary_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary_path, registry_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY_PATH,
        help="oracle registry to authenticate against and, when promoting, update",
    )
    parser.add_argument("--from-checkpoint", required=True, help="authenticated registry checkpoint")
    parser.add_argument("--promote-checkpoint", help="capture_required registry checkpoint to promote")
    parser.add_argument("--verify-only", action="store_true", help="round-trip snapshot without editing registry")
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True, help="local source state for --from-checkpoint")
    parser.add_argument("--tape", type=Path, required=True, help="concrete deterministic JSON tape")
    parser.add_argument("--snapshot-output", type=Path, required=True, help="new absolute local .state path outside task repository")
    parser.add_argument(
        "--trace-output", type=Path,
        help="new absolute JSON VBlank trace outside task repository (recommended for resumable evidence)",
    )
    parser.add_argument(
        "--receipt-output", type=Path,
        help="new absolute JSON receipt outside task repository (recommended for resumable promotion)",
    )
    parser.add_argument(
        "--oracle-launcher",
        type=Path,
        default=SCRIPT_DIR / "run_mgba_jsonl_oracle.sh",
    )
    args = parser.parse_args()
    if bool(args.promote_checkpoint) == bool(args.verify_only):
        parser.error("supply exactly one of --promote-checkpoint or --verify-only")
    return args


def main() -> int:
    args = parse_args()
    if not args.rom.is_absolute() or not args.state.is_absolute() or not args.snapshot_output.is_absolute():
        raise CaptureError("--rom, --state, and --snapshot-output must be absolute")
    if not args.rom.is_file() or not args.state.is_file():
        raise CaptureError("--rom and --state must name existing local files")
    if args.snapshot_output.suffix != ".state" or args.snapshot_output.exists():
        raise CaptureError("--snapshot-output must be a new .state path")
    if not args.snapshot_output.parent.is_dir():
        raise CaptureError("--snapshot-output parent directory does not exist")
    if TASK_ROOT == args.snapshot_output.parent or TASK_ROOT in args.snapshot_output.parents:
        raise CaptureError("--snapshot-output must stay outside the task repository")
    for output, label in ((args.trace_output, "--trace-output"), (args.receipt_output, "--receipt-output")):
        if output is not None:
            if not output.is_absolute() or output.exists() or not output.parent.is_dir():
                raise CaptureError(f"{label} must be a new absolute path with an existing parent")
            if TASK_ROOT == output.parent or TASK_ROOT in output.parents:
                raise CaptureError(f"{label} must stay outside the task repository")
    try:
        registry, from_checkpoint = resolve_checkpoint(args.from_checkpoint, args.registry)
        require_trusted_oracle(registry)
        require_authenticated(from_checkpoint)
        if args.promote_checkpoint:
            target_registry, target_checkpoint = resolve_checkpoint(
                args.promote_checkpoint, args.registry
            )
            if target_registry != registry or target_checkpoint.status not in {
                "capture_required",
                "quarantined_provenance",
            }:
                raise CaptureError(
                    "--promote-checkpoint must be a capture_required or quarantined_provenance registry row"
                )
    except RegistryError as exc:
        raise CaptureError(str(exc)) from exc
    source = from_checkpoint.source
    assert source is not None
    if file_sha256(args.rom) != registry["rom_sha256"]:
        raise CaptureError("--rom does not match the registry-pinned SHA-256")
    if file_sha256(args.state) != source["state_sha256"]:
        raise CaptureError("--state does not match --from-checkpoint identity")
    ticks, tape_sha256 = expand_program(args.tape)
    metadata = tape_metadata(args.tape)

    original = start_oracle(
        args.oracle_launcher, args.rom, args.state, from_checkpoint.checkpoint_id,
        args.snapshot_output.parent,
    )
    try:
        loaded = load_source(original, args.rom, str(args.state))
        verify_identity(loaded, registry, registry["rom_sha256"])
        if loaded.get("state_sha256") != source["state_sha256"]:
            raise CaptureError("oracle did not load the authenticated source state")
        if checked_rgb(loaded) != source["initial_rgb_sha256"]:
            raise CaptureError("authenticated source initial RGB does not match registry")
        loaded_source_state = loaded.get("source_state")
        if not isinstance(loaded_source_state, dict) or not initial_state_matches(
            from_checkpoint, loaded_source_state
        ):
            raise CaptureError("authenticated source initial state does not match registry")
        frames = [trace_frame(loaded, 0, [])]
        current = loaded
        for expected_frame, buttons in enumerate(ticks, start=1):
            current = send(original, {"op": "step", "buttons": buttons})
            if current.get("frame_number") != expected_frame:
                raise CaptureError("oracle frame number drifted while replaying capture tape")
            frames.append(trace_frame(current, expected_frame, buttons))
        current_source_state = current.get("source_state")
        if not isinstance(current_source_state, dict):
            raise CaptureError("terminal oracle response lacks source_state")
        validate_terminal_source_assertions(metadata, current_source_state)
        snapshot_name = args.snapshot_output.name
        snapshot = send(
            original,
            {"op": "snapshot", "output_path": str(CONTAINER_SNAPSHOT_DIR / snapshot_name)},
        )
        verify_identity(snapshot, registry, registry["rom_sha256"])
        if snapshot.get("snapshot_path") != str(CONTAINER_SNAPSHOT_DIR / snapshot_name):
            raise CaptureError("adapter snapshot response did not confirm the explicit target")
        if snapshot.get("frame_number") != current.get("frame_number"):
            raise CaptureError("snapshot frame number differs from source boundary")
        if snapshot.get("frame_rgb_sha256") != checked_rgb(current):
            raise CaptureError("snapshot frame hash differs from source boundary")
        if snapshot.get("source_state") != current.get("source_state"):
            raise CaptureError("snapshot source_state differs from source boundary")
        snapshot_state_sha256 = snapshot.get("snapshot_state_sha256")
        if not isinstance(snapshot_state_sha256, str) or file_sha256(args.snapshot_output) != snapshot_state_sha256:
            raise CaptureError("host snapshot SHA-256 does not match adapter response")
        continuation = send(original, {"op": "step", "buttons": []})
        expected_frame_hash = checked_rgb(continuation)
        expected_source_state = continuation.get("source_state")
        if not isinstance(expected_source_state, dict):
            raise CaptureError("source continuation lacks source_state")
    finally:
        close(original)

    reloaded = start_oracle(
        args.oracle_launcher, args.rom, args.state, from_checkpoint.checkpoint_id,
        args.snapshot_output.parent,
    )
    try:
        round_trip = load_source(reloaded, args.rom, str(CONTAINER_SNAPSHOT_DIR / snapshot_name))
        verify_identity(round_trip, registry, registry["rom_sha256"])
        if round_trip.get("state_sha256") != snapshot_state_sha256:
            raise CaptureError("fresh adapter did not load the captured snapshot bytes")
        actual_frame_hash = checked_rgb(round_trip)
        if actual_frame_hash != expected_frame_hash or round_trip.get("source_state") != expected_source_state:
            raise CaptureError("snapshot reload did not match the no-input continuation frame/state")
    finally:
        close(reloaded)

    trace = {
        "schema": TRACE_SCHEMA,
        "from_checkpoint": from_checkpoint.checkpoint_id,
        "capture_tape_sha256": tape_sha256,
        "capture_tape": metadata,
        "source_identity": {
            "rom_sha256": registry["rom_sha256"],
            "source_state_sha256": source["state_sha256"],
            "emulator": registry["oracle"]["emulator"],
            "config": registry["oracle"]["config"],
        },
        "initial_frame_rgb_sha256": frames[0]["frame_rgb_sha256"],
        "initial_source_state": frames[0]["source_state"],
        "frame_count": len(frames),
        "frames": frames,
        "terminal_snapshot_state_sha256": snapshot_state_sha256,
        "terminal_source_position": source_position(current["source_state"]),
    }
    trace_sha256 = hashlib.sha256(canonical_json(trace).encode("utf-8")).hexdigest()
    trace["trace_sha256"] = trace_sha256
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "from_checkpoint": from_checkpoint.checkpoint_id,
        "promote_checkpoint": args.promote_checkpoint,
        "capture_tape_sha256": tape_sha256,
        "capture_tape_path": str(args.tape),
        "capture_tape": metadata,
        "snapshot_state_sha256": snapshot_state_sha256,
        "snapshot_state_path": str(args.snapshot_output),
        "snapshot_frame_number": snapshot["frame_number"],
        "initial_frame_rgb_sha256": frames[0]["frame_rgb_sha256"],
        "initial_source_state": frames[0]["source_state"],
        "terminal_frame_rgb_sha256": frames[-1]["frame_rgb_sha256"],
        "terminal_source_state": current["source_state"],
        "terminal_source_position": source_position(current["source_state"]),
        "post_reload_initial_rgb_sha256": actual_frame_hash,
        "post_reload_source_state": expected_source_state,
        "round_trip": "exact_no_input_continuation",
        "source_identity": {
            "rom_sha256": registry["rom_sha256"],
            "source_state_sha256": source["state_sha256"],
            "emulator": registry["oracle"]["emulator"],
            "config": registry["oracle"]["config"],
        },
        "capture_trace_sha256": trace_sha256,
    }
    if args.trace_output is not None:
        receipt["capture_trace_path"] = str(args.trace_output)
    if args.promote_checkpoint:
        # This is signed into the immutable receipt before the registry is
        # changed, so a later verifier can bind the state to its intended row.
        receipt["registry_promoted"] = args.promote_checkpoint
    receipt_sha256 = hashlib.sha256(canonical_json(receipt).encode("utf-8")).hexdigest()
    receipt["receipt_sha256"] = receipt_sha256
    if args.trace_output is not None:
        write_new_json(args.trace_output, trace, "capture trace")
    if args.promote_checkpoint:
        promote(
            registry_path=args.registry,
            target_id=args.promote_checkpoint,
            source_state_sha256=snapshot_state_sha256,
            initial_rgb_sha256=actual_frame_hash,
            initial_source_state=expected_source_state,
            from_checkpoint=from_checkpoint.checkpoint_id,
            tape_sha256=tape_sha256,
            snapshot_frame_number=snapshot["frame_number"],
            receipt_sha256=receipt_sha256 if args.receipt_output is not None else None,
            trace_sha256=trace_sha256 if args.trace_output is not None else None,
        )
    if args.receipt_output is not None:
        write_new_json(args.receipt_output, receipt, "capture receipt")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CaptureError as exc:
        print(f"capture error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
