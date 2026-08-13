#!/usr/bin/env python3
"""Execute and validate full-scope Emerald coverage evidence.

This is intentionally an evidence orchestrator, not an engine test.  It only
runs the existing strict differential harness for registry rows that are both
authenticated and supplied with their matching local state.  Concrete,
capture-ready source-only tapes are recorded through the existing source tape
recorder.  Everything else is counted as unexecuted; it is never inferred from
Rust implementation or transport checks.
"""

from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from emerald_coverage_dashboard import (
    DEFAULT_FRAMES,
    DEFAULT_ORACLE,
    DEFAULT_REGISTRY as DEFAULT_COVERAGE_REGISTRY,
    build_dashboard,
    print_table,
)
from emerald_oracle_registry import (
    DEFAULT_REGISTRY_PATH,
    RegistryError,
    canonical_json,
    file_sha256,
    load_registry,
    require_trusted_oracle,
)


ROOT = Path(__file__).resolve().parents[1]
FUZZ = ROOT / "scripts/fuzz_emerald_differential.py"
RECORDER = ROOT / "fixtures/source_tapes/battle_coverage_v1/capture_source_tape.py"
DEFAULT_BATTLE_PLAN = ROOT / "fixtures/source_tapes/battle_coverage_v1/manifest.json"
SOURCE_PLAN_SCHEMA = "gamebench.pokemon_emerald.source_tape_plan.v1"
SOURCE_TRACE_SCHEMA = "gamebench.pokemon_emerald.source_vblank_tape.v1"
RGB_BYTES = 240 * 160 * 3


class OrchestrationError(RuntimeError):
    """A malformed evidence input must not become a coverage pass."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise OrchestrationError(f"{path} root must be an object")
    return value


def parse_state_assignments(values: list[str], label: str) -> dict[str, Path]:
    assignments: dict[str, Path] = {}
    for value in values:
        key, separator, raw_path = value.partition("=")
        path = Path(raw_path)
        if not separator or not key or not path.is_absolute():
            raise OrchestrationError(f"{label} must use NAME=/absolute/path")
        if key in assignments:
            raise OrchestrationError(f"duplicate {label} for {key}")
        if not path.is_file():
            raise OrchestrationError(f"{label} file does not exist: {path}")
        assignments[key] = path
    return assignments


def load_source_plans(paths: list[Path]) -> tuple[dict[str, tuple[dict[str, Any], dict[str, Any], str]], list[str]]:
    """Return tape id -> (plan root, tape, plan sha); reject duplicate IDs."""
    plans: dict[str, tuple[dict[str, Any], dict[str, Any], str]] = {}
    diagnostics: list[str] = []
    for path in paths:
        root = read_json(path)
        if root.get("schema") != SOURCE_PLAN_SCHEMA or not isinstance(root.get("tapes"), list):
            diagnostics.append(f"UNSUPPORTED source tape plan: {path}")
            continue
        digest = file_sha256(path)
        for tape in root["tapes"]:
            if not isinstance(tape, dict) or not isinstance(tape.get("id"), str):
                diagnostics.append(f"UNSUPPORTED source tape entry: {path}")
                continue
            if tape["id"] in plans:
                raise OrchestrationError(f"duplicate source tape id: {tape['id']}")
            plans[tape["id"]] = (root, tape, digest)
    return plans, diagnostics


def response_frame_identity(response: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if response.get("ok") is not True or not isinstance(response.get("frame_rgb_b64"), str):
        raise OrchestrationError("oracle round-trip response lacks an RGB frame")
    try:
        rgb = base64.b64decode(response["frame_rgb_b64"], validate=True)
    except ValueError as exc:
        raise OrchestrationError("oracle round-trip RGB is invalid base64") from exc
    if len(rgb) != RGB_BYTES:
        raise OrchestrationError("oracle round-trip RGB has an invalid size")
    state = response.get("source_state")
    if not isinstance(state, dict):
        raise OrchestrationError("oracle round-trip response lacks source_state")
    return sha256_bytes(rgb), state


def roundtrip_state(
    command: str, rom: Path, state: Path, registry: dict[str, Any], expected_state_sha: str | None
) -> dict[str, Any]:
    """Load the same local state twice and require identical initial identity."""
    process = subprocess.Popen(
        shlex.split(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    responses: list[dict[str, Any]] = []
    try:
        assert process.stdin is not None and process.stdout is not None
        request = canonical_json({"op": "load", "rom_path": str(rom), "state_path": str(state)}) + "\n"
        for _ in range(2):
            process.stdin.write(request)
            process.stdin.flush()
            line = process.stdout.readline()
            if not line:
                raise OrchestrationError("oracle closed during savestate round-trip")
            loaded = json.loads(line)
            if not isinstance(loaded, dict):
                raise OrchestrationError("oracle round-trip did not return an object")
            responses.append(loaded)
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    first_sha, first_state = response_frame_identity(responses[0])
    second_sha, second_state = response_frame_identity(responses[1])
    local_rom = file_sha256(rom)
    local_state = file_sha256(state)
    for response in responses:
        if response.get("rom_sha256") != local_rom or local_rom != registry["rom_sha256"]:
            raise OrchestrationError("round-trip ROM identity does not match the registry")
        if response.get("state_sha256") != local_state:
            raise OrchestrationError("round-trip state identity does not match the local state")
        if expected_state_sha is not None and local_state != expected_state_sha:
            raise OrchestrationError("local state does not match the promoted registry identity")
        if response.get("emulator") != registry["oracle"]["emulator"]:
            raise OrchestrationError("round-trip emulator identity does not match the registry")
        if response.get("config") != registry["oracle"]["config"]:
            raise OrchestrationError("round-trip emulator config does not match the registry")
    if first_sha != second_sha or canonical_json(first_state) != canonical_json(second_state):
        raise OrchestrationError("savestate load/load round-trip changed initial RGB or source state")
    return {
        "status": "authenticated",
        "rom_sha256": local_rom,
        "state_sha256": local_state,
        "initial_rgb_sha256": first_sha,
        "initial_source_state": first_state,
    }


def validate_source_trace(
    path: Path,
    plans: dict[str, tuple[dict[str, Any], dict[str, Any], str]],
    registry: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Return (tape_id, error); a trace is executed only when fully proven."""
    try:
        trace = read_json(path)
        if trace.get("schema") != SOURCE_TRACE_SCHEMA:
            raise OrchestrationError("unsupported trace schema")
        if trace.get("comparison") != {"kind": "source_only", "rust_compared": False}:
            raise OrchestrationError("trace comparison must remain source_only")
        tape = trace.get("tape")
        if not isinstance(tape, dict) or not isinstance(tape.get("id"), str):
            raise OrchestrationError("trace is missing tape.id")
        tape_id = tape["id"]
        if tape_id not in plans:
            raise OrchestrationError(f"trace tape id {tape_id!r} is not in a supplied plan")
        _, planned, plan_sha = plans[tape_id]
        provenance = tape.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("plan_tape_id") != tape_id or provenance.get("plan_manifest_sha256") != plan_sha:
            raise OrchestrationError("trace has no matching tape-plan provenance")
        if provenance.get("checkpoint") != planned.get("checkpoint"):
            raise OrchestrationError("trace checkpoint provenance does not match its plan")
        roundtrip = provenance.get("savestate_roundtrip")
        if not isinstance(roundtrip, dict) or roundtrip.get("status") != "authenticated":
            raise OrchestrationError("trace lacks authenticated savestate round-trip provenance")
        identity = trace.get("source_identity")
        if not isinstance(identity, dict) or identity.get("rom_sha256") != registry["rom_sha256"]:
            raise OrchestrationError("trace ROM provenance does not match the registry")
        if identity.get("state_sha256") != roundtrip.get("state_sha256"):
            raise OrchestrationError("trace state provenance does not match its round-trip")
        if identity.get("emulator") != registry["oracle"]["emulator"] or identity.get("config") != registry["oracle"]["config"]:
            raise OrchestrationError("trace emulator provenance does not match the registry")
        frames = trace.get("frames")
        if not isinstance(frames, list) or not frames or trace.get("frame_count") != len(frames):
            raise OrchestrationError("trace frame count is invalid")
        if trace.get("initial_frame_rgb_sha256") != roundtrip.get("initial_rgb_sha256"):
            raise OrchestrationError("trace initial RGB does not match round-trip provenance")
        for index, frame in enumerate(frames):
            if not isinstance(frame, dict) or frame.get("vblank") != index or not isinstance(frame.get("source_state"), dict):
                raise OrchestrationError("trace VBlank/source-state sequence is invalid")
        stored = trace.get("trace_sha256")
        reduced = dict(trace)
        reduced.pop("trace_sha256", None)
        if stored != sha256_bytes(canonical_json(reduced).encode("utf-8")):
            raise OrchestrationError("trace_sha256 does not validate")
        return tape_id, None
    except OrchestrationError as exc:
        return None, str(exc)


def run_differential(
    checkpoint_id: str, state: Path, args: argparse.Namespace, output: Path
) -> tuple[bool, str]:
    command = [
        sys.executable, str(FUZZ), "--mode", "oracle", "--oracle-checkpoint", checkpoint_id,
        "--oracle-rom", str(args.rom), "--oracle-state", str(state),
        "--oracle-command", args.oracle_command, "--random-cases", str(args.random_cases),
        "--steps", str(args.steps), "--output", str(output),
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    # Exit 1 is an authentic comparison with divergences; exit 2 is failed setup.
    if result.returncode not in (0, 1) or not output.is_file():
        return False, (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
    return True, "exact" if result.returncode == 0 else "divergences_found"


def run_capture_ready_tapes(
    plans: dict[str, tuple[dict[str, Any], dict[str, Any], str]],
    capture_states: dict[str, Path],
    registry: dict[str, Any],
    args: argparse.Namespace,
    output_dir: Path,
) -> tuple[list[Path], dict[str, str], list[str]]:
    traces: list[Path] = []
    outcomes: dict[str, str] = {}
    diagnostics: list[str] = []
    for tape_id, (_, tape, plan_sha) in plans.items():
        ready = tape.get("status") in ("capture_ready", "ready") and isinstance(tape.get("program"), list)
        if not ready:
            outcomes[tape_id] = "unexecuted_plan"
            continue
        state = capture_states.get(str(tape.get("checkpoint")))
        if state is None:
            outcomes[tape_id] = "unexecuted_missing_state"
            continue
        try:
            receipt = roundtrip_state(args.oracle_command, args.rom, state, registry, None)
        except OrchestrationError as exc:
            outcomes[tape_id] = "unexecuted_roundtrip_failed"
            diagnostics.append(f"{tape_id}: {exc}")
            continue
        output = output_dir / "source-tapes" / f"{tape_id}.json"
        if output.exists():
            outcomes[tape_id] = "unexecuted_output_exists"
            continue
        with tempfile.TemporaryDirectory(prefix="emerald-source-tape-") as temp:
            concrete = {
                "id": tape_id,
                "checkpoint": tape["checkpoint"],
                "program": tape["program"],
                "provenance": {
                    "plan_tape_id": tape_id,
                    "plan_manifest_sha256": plan_sha,
                    "checkpoint": tape["checkpoint"],
                    "savestate_roundtrip": receipt,
                },
            }
            tape_path = Path(temp) / "tape.json"
            tape_path.write_text(json.dumps(concrete), encoding="utf-8")
            command = [sys.executable, str(RECORDER), "--oracle-command", args.oracle_command, "--rom", str(args.rom), "--state", str(state), "--tape", str(tape_path), "--output", str(output)]
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        if result.returncode != 0 or not output.is_file():
            outcomes[tape_id] = "unexecuted_capture_failed"
            diagnostics.append(f"{tape_id}: {(result.stderr or result.stdout).strip()}")
            continue
        traces.append(output)
        outcomes[tape_id] = "recorded_source_only"
    return traces, outcomes, diagnostics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--coverage-registry", type=Path, default=DEFAULT_COVERAGE_REGISTRY)
    parser.add_argument("--battle-plan", type=Path, action="append", default=[DEFAULT_BATTLE_PLAN])
    parser.add_argument("--existing-report", type=Path, action="append", default=[])
    parser.add_argument("--recorded-trace", type=Path, action="append", default=[])
    parser.add_argument("--capture-receipt", type=Path, action="append", default=[], help="verified external snapshot receipt")
    parser.add_argument("--state", action="append", default=[], metavar="CHECKPOINT=/ABSOLUTE/STATE")
    parser.add_argument("--capture-state", action="append", default=[], metavar="LABEL=/ABSOLUTE/STATE")
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--oracle-command")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--random-cases", type=int, default=16)
    parser.add_argument("--steps", type=int, default=64)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        registry, checkpoints = load_registry(args.oracle_registry)
        if not args.dry_run:
            require_trusted_oracle(registry)
        plans, plan_diagnostics = load_source_plans(args.battle_plan)
        states = parse_state_assignments(args.state, "--state")
        capture_states = parse_state_assignments(args.capture_state, "--capture-state")
        if args.output_dir.exists() and any(args.output_dir.iterdir()):
            raise OrchestrationError(f"output directory must be new or empty: {args.output_dir}")
        if not args.dry_run:
            if args.rom is None or not args.rom.is_absolute() or not args.rom.is_file():
                raise OrchestrationError("--rom must be an existing absolute path when executing")
            if not args.oracle_command:
                raise OrchestrationError("--oracle-command is required when executing")
            if args.random_cases < 0 or not 1 <= args.steps <= 1000:
                raise OrchestrationError("invalid --random-cases or --steps")
        args.output_dir.mkdir(parents=True, exist_ok=True)
    except (RegistryError, OrchestrationError) as exc:
        print(f"coverage orchestration failed closed: {exc}", file=sys.stderr)
        return 2

    execution: dict[str, Any] = {"differential": {}, "source_tapes": {}, "diagnostics": plan_diagnostics}
    reports = list(args.existing_report)
    if not args.dry_run:
        for checkpoint_id, checkpoint in checkpoints.items():
            if not checkpoint.authenticated:
                execution["differential"][checkpoint_id] = "unexecuted_capture_required"
                continue
            state = states.get(checkpoint_id)
            if state is None:
                execution["differential"][checkpoint_id] = "unexecuted_missing_state"
                continue
            try:
                roundtrip_state(args.oracle_command, args.rom, state, registry, checkpoint.source["state_sha256"])
            except OrchestrationError as exc:
                execution["differential"][checkpoint_id] = "unexecuted_roundtrip_failed"
                execution["diagnostics"].append(f"{checkpoint_id}: {exc}")
                continue
            report = args.output_dir / f"differential-{checkpoint_id}.json"
            ok, status = run_differential(checkpoint_id, state, args, report)
            execution["differential"][checkpoint_id] = status if ok else "failed"
            if ok:
                reports.append(report)
            else:
                execution["diagnostics"].append(f"{checkpoint_id}: {status}")
        captured, source_outcomes, diagnostics = run_capture_ready_tapes(
            plans, capture_states, registry, args, args.output_dir
        )
        execution["source_tapes"].update(source_outcomes)
        execution["diagnostics"].extend(diagnostics)
        supplied_traces = list(args.recorded_trace) + captured
    else:
        for checkpoint_id, checkpoint in checkpoints.items():
            execution["differential"][checkpoint_id] = "would_run" if checkpoint.authenticated and checkpoint_id in states else (
                "unexecuted_missing_state" if checkpoint.authenticated else "unexecuted_capture_required"
            )
        supplied_traces = list(args.recorded_trace)
        for tape_id in plans:
            execution["source_tapes"][tape_id] = "unexecuted_plan"

    executed_tapes: list[str] = []
    invalid_traces: dict[str, str] = {}
    for trace in supplied_traces:
        tape_id, error = validate_source_trace(trace, plans, registry)
        if tape_id is not None:
            executed_tapes.append(tape_id)
            execution["source_tapes"][tape_id] = "validated_source_only"
        else:
            invalid_traces[str(trace)] = error or "unknown validation failure"
    execution["trace_validation"] = {
        "planned": len(plans), "executed": len(set(executed_tapes)),
        "unexecuted": len(set(plans) - set(executed_tapes)), "invalid": invalid_traces,
    }
    dashboard = build_dashboard(
        args.coverage_registry, DEFAULT_FRAMES, DEFAULT_ORACLE, args.oracle_registry,
        reports, [], supplied_traces, args.capture_receipt,
    )
    print_table(dashboard)
    result = {
        "schema": "gamebench.pokemon_emerald.coverage_orchestration.v1",
        "dry_run": args.dry_run,
        "reports": [str(path) for path in reports],
        "execution": execution,
        "dashboard": dashboard,
    }
    result_path = args.output_dir / "coverage-orchestration.json"
    dashboard_path = args.output_dir / "coverage-dashboard.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    dashboard_path.write_text(json.dumps(dashboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"orchestration: {result_path}")
    print(f"dashboard: {dashboard_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
