#!/usr/bin/env python3
"""Record a source-only raw-VBlank tape from the pinned mGBA JSONL adapter.

This tool deliberately has no Rust-service dependency.  It captures a supplied
checkpoint-local program and writes every framebuffer digest and every source
semantic field the adapter exposes.  It is intended for the planned battle
fixtures in this directory, but keeps the input format generic enough for any
small local source checkpoint.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


RGB_BYTES = 240 * 160 * 3
VALID_BUTTONS = {"a", "b", "select", "start", "right", "left", "up", "down", "r", "l"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_response(process: subprocess.Popen[str]) -> dict[str, Any]:
    if process.stdout is None:
        raise RuntimeError("oracle stdout was not opened")
    line = process.stdout.readline()
    if not line:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise RuntimeError(f"oracle closed its JSONL stream: {stderr.strip()}")
    response = json.loads(line)
    if not isinstance(response, dict) or response.get("ok") is not True:
        raise RuntimeError(f"oracle error: {response}")
    return response


def send(process: subprocess.Popen[str], request: dict[str, Any]) -> dict[str, Any]:
    if process.stdin is None:
        raise RuntimeError("oracle stdin was not opened")
    process.stdin.write(canonical_json(request) + "\n")
    process.stdin.flush()
    return read_response(process)


def checked_frame(response: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    encoded = response.get("frame_rgb_b64")
    source_state = response.get("source_state")
    if not isinstance(encoded, str) or not isinstance(source_state, dict):
        raise RuntimeError("oracle response omitted frame_rgb_b64 or source_state")
    rgb = base64.b64decode(encoded, validate=True)
    if len(rgb) != RGB_BYTES:
        raise RuntimeError(f"oracle returned {len(rgb)} RGB bytes, expected {RGB_BYTES}")
    digest = sha256(rgb)
    if response.get("frame_rgb_sha256") != digest:
        raise RuntimeError("oracle frame_rgb_sha256 does not match raw RGB bytes")
    return digest, source_state


def expand_program(tape: dict[str, Any]) -> list[tuple[str, list[str]]]:
    program = tape.get("program")
    if not isinstance(program, list) or not program:
        raise ValueError("tape.program must be a non-empty list of concrete action segments")
    ticks: list[tuple[str, list[str]]] = []
    for index, segment in enumerate(program):
        if not isinstance(segment, dict):
            raise ValueError(f"program[{index}] must be an object")
        buttons = segment.get("buttons", [])
        frames = segment.get("frames")
        if not isinstance(buttons, list) or not all(isinstance(button, str) for button in buttons):
            raise ValueError(f"program[{index}].buttons must be a string list")
        if not isinstance(frames, int) or frames <= 0:
            raise ValueError(f"program[{index}].frames must be a positive integer")
        unknown = sorted(set(buttons) - VALID_BUTTONS)
        if unknown or len(buttons) != len(set(buttons)):
            raise ValueError(f"program[{index}] has invalid buttons: {unknown or buttons}")
        # Preserve declared order for readability while equivalence is set-based.
        held = list(buttons)
        for _ in range(frames):
            ticks.append((f"segment:{index}", held))
    return ticks


def frame_record(
    *,
    vblank: int,
    segment: str | None,
    held: list[str],
    previous_held: list[str],
    response: dict[str, Any],
) -> dict[str, Any]:
    rgb_sha256, source_state = checked_frame(response)
    held_set = set(held)
    previous_set = set(previous_held)
    return {
        "vblank": vblank,
        "segment": segment,
        "input": {
            "held": held,
            "pressed": [button for button in held if button not in previous_set],
            "released": [button for button in previous_held if button not in held_set],
        },
        "frame_rgb_sha256": rgb_sha256,
        "source_state": source_state,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-command", required=True, help="long-lived JSONL oracle command")
    parser.add_argument("--rom", type=Path, required=True, help="absolute source ROM path")
    parser.add_argument("--state", type=Path, required=True, help="absolute local checkpoint state path")
    parser.add_argument("--tape", type=Path, required=True, help="concrete source-only tape JSON")
    parser.add_argument("--output", type=Path, required=True, help="new output JSON path")
    parser.add_argument(
        "--snapshot-output",
        help=(
            "optional container-local /oracle-output/<name>.state path; requires "
            "an oracle launched with the explicit snapshot directory mount"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing trace: {args.output}")
    if not args.rom.is_absolute() or not args.state.is_absolute():
        raise SystemExit("--rom and --state must be absolute paths")
    if not args.rom.is_file() or not args.state.is_file():
        raise SystemExit("--rom and --state must name existing local files")
    tape = json.loads(args.tape.read_text(encoding="utf-8"))
    if not isinstance(tape, dict):
        raise SystemExit("tape root must be an object")
    ticks = expand_program(tape)
    command = shlex.split(args.oracle_command)
    if not command:
        raise SystemExit("--oracle-command was empty")
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    try:
        loaded = send(process, {"op": "load", "rom_path": str(args.rom), "state_path": str(args.state)})
        if loaded.get("frame_number") != 0:
            raise RuntimeError("oracle load did not establish frame_number 0")
        initial_sha, _ = checked_frame(loaded)
        identity = {
            "rom_sha256": loaded.get("rom_sha256"),
            "state_sha256": loaded.get("state_sha256"),
            "emulator": loaded.get("emulator"),
            "config": loaded.get("config"),
            "local_rom_sha256": sha256_file(args.rom),
            "local_state_sha256": sha256_file(args.state),
        }
        if identity["rom_sha256"] != identity["local_rom_sha256"]:
            raise RuntimeError("oracle loaded a ROM different from --rom")
        if identity["state_sha256"] != identity["local_state_sha256"]:
            raise RuntimeError("oracle loaded a state different from --state")
        frames = [frame_record(vblank=0, segment=None, held=[], previous_held=[], response=loaded)]
        previous_held: list[str] = []
        for vblank, (segment, held) in enumerate(ticks, start=1):
            response = send(process, {"op": "step", "buttons": held})
            if response.get("frame_number") != vblank:
                raise RuntimeError(
                    f"oracle frame number drifted at VBlank {vblank}: "
                    f"{response.get('frame_number')!r}"
                )
            frames.append(frame_record(
                vblank=vblank, segment=segment, held=held, previous_held=previous_held, response=response,
            ))
            previous_held = held
        snapshot: dict[str, Any] | None = None
        if args.snapshot_output is not None:
            snapshot = send(process, {"op": "snapshot", "output_path": args.snapshot_output})
            if snapshot.get("frame_number") != len(ticks):
                raise RuntimeError("snapshot frame number does not match the recorded terminal VBlank")
            if snapshot.get("frame_rgb_sha256") != frames[-1]["frame_rgb_sha256"]:
                raise RuntimeError("snapshot framebuffer differs from the recorded terminal VBlank")
            if snapshot.get("source_state") != frames[-1]["source_state"]:
                raise RuntimeError("snapshot source_state differs from the recorded terminal VBlank")
        result = {
            "schema": "gamebench.pokemon_emerald.source_vblank_tape.v1",
            "comparison": {"kind": "source_only", "rust_compared": False},
            "tape": {key: value for key, value in tape.items() if key != "program"},
            "program": tape["program"],
            "source_identity": identity,
            "initial_frame_rgb_sha256": initial_sha,
            "frame_count": len(frames),
            "frames": frames,
        }
        if snapshot is not None:
            result["terminal_snapshot"] = {
                "snapshot_path": snapshot.get("snapshot_path"),
                "snapshot_state_sha256": snapshot.get("snapshot_state_sha256"),
            }
        result["trace_sha256"] = sha256(canonical_json(result).encode("utf-8"))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    finally:
        if process.stdin is not None:
            process.stdin.close()
        process.wait(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
