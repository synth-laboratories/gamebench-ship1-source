#!/usr/bin/env python3
"""Bounded regression fuzzing for the Emerald frame/action contract.

This harness intentionally has two separate lanes:

* ``--mode rust`` checks an important contract of the in-tree implementation:
  submitting a continuous held button in one request must agree with submitting
  the identical button over smaller transport chunks.  It compares final
  semantic state, RGB bytes, and parity metadata independently.
* ``--mode oracle`` is a strict, VBlank-by-VBlank differential test.  It
  compares the in-tree renderer's *raw 240x160x3 RGB bytes* and its public
  position/map state against a pinned source emulator.  The source emulator is
  supplied by a small JSONL adapter; no screenshot scaling, lossy encoding,
  perceptual metric, or unchecked zero-frame pass is permitted in this lane.

The repository deliberately does not ship a commercial game ROM, a save state,
or an mGBA adapter.  Consequently oracle mode exits with status 2 rather than
silently treating the Rust renderer as the source of truth.  See
``--print-oracle-protocol`` for the adapter contract.

Examples (the default named checkpoint is ``bedroom_idle``):
  python3 scripts/fuzz_emerald_differential.py --mode rust \
    --output /tmp/emerald-rust-contract.json

  python3 scripts/fuzz_emerald_differential.py --mode oracle \
    --oracle-rom /secure/Emerald.gba --oracle-state /secure/bedroom.ss1 \
    --oracle-checkpoint bedroom_idle \
    --oracle-command './tools/mgba_jsonl_adapter' \
    --output /tmp/emerald-pixel-differential.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import shlex
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# Tests load this file by path instead of executing it as a script.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from emerald_oracle_registry import (
    DEFAULT_REGISTRY_PATH,
    OracleCheckpoint,
    RegistryError,
    initial_state_matches,
    normalize_source_semantics,
    require_authenticated,
    require_trusted_oracle,
    resolve_checkpoint,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RGB_BYTES = 240 * 160 * 3
# ``oracle_manifest.json`` remains the bedroom v1 receipt used by existing
# reports. New oracle runs resolve identities through the checkpoint registry.
ORACLE_MANIFEST_PATH = TASK_ROOT / "fixtures" / "gold" / "oracle_manifest.json"
# Keep the checked-in registry as the default, but allow authenticated local
# oracle runs to point at an explicitly prepared registry (for example, a
# locally rebuilt mGBA image whose immutable image id differs from CI's).  The
# identity checks below still require every field in that selected registry;
# this is not a way to bypass provenance.
ORACLE_REGISTRY_PATH = Path(
    os.environ.get("EMERALD_ORACLE_REGISTRY", str(DEFAULT_REGISTRY_PATH))
)
DEFAULT_ORACLE_ROM = (
    TASK_ROOT.parents[2] / "pokeagent-speedrun" / "Emerald-GBAdvance" / "rom.gba"
)
BUTTONS = ("up", "down", "left", "right", "a", "b", "start", "select", "noop")

ORACLE_PROTOCOL = """\
The --oracle-command process must stay alive and speak one JSON object per line
over stdin/stdout.  It owns a pinned mGBA (or equivalent source emulator).

Requests from this harness:
  {"op":"load","rom_path":"/absolute/rom.gba","state_path":"/absolute/state.ss1"}
  {"op":"step","buttons":["down"]}

The local pinned adapter additionally supports capture-only snapshots when its
launcher was given an explicit writable host output directory:
  {"op":"snapshot","output_path":"/oracle-output/new-checkpoint.state"}
This operation is write-once and returns only snapshot/frame/state/identity
digests; it never returns state bytes. A snapshot must be reloaded through a
fresh adapter before it can be registered as a source checkpoint.

For every request, reply with exactly one object containing:
  {"ok":true,"frame_rgb_b64":"..."}

Every response must additionally include source_state with integer player_x,
player_y, map_group, and map_number fields.  The response to ``load`` must also
include the identity actually loaded by the adapter. The harness checks the
two file digests against the selected authenticated registry row before
accepting a comparison:
  {
    "ok": true,
    "frame_rgb_b64": "...",
    "rom_sha256": "<64 lowercase hex chars>",
    "state_sha256": "<64 lowercase hex chars>",
    "emulator": {
      "core": "mGBA",
      "version": "<pinned version>",
      "config_sha256": "<64 lowercase hex chars>"
    }
  },
  "source_state": {
    "player_x": 1, "player_y": 3, "map_group": 1, "map_number": 3
  }

frame_rgb_b64 must decode to exactly 115200 bytes in row-major 240x160 RGB888
order, after one VBlank.  "step" is called once per VBlank; adapters must not
coalesce frames, scale, crop, apply shaders, or encode a screenshot.
Additional source debug hashes may be included in source_state.  On errors
reply {"ok":false,"error":"..."}.
"""


class HarnessError(RuntimeError):
    """A setup or protocol error that must not become a pass."""


@dataclass
class OracleReplayFrame:
    """One uncompressed source/Rust VBlank captured while replaying a tape.

    The normal corpus report intentionally records compact, JSON-friendly proof
    entries.  Minimisation needs the original RGB and readout objects while it
    repeatedly asks whether a candidate still fails, so it keeps those only in
    memory in this separate type.
    """

    vblank: int
    button: str | None
    rust_rgb: bytes
    source_rgb: bytes
    rust_readout: dict[str, Any]
    source_response: dict[str, Any]
    semantic_equal: bool


def classify_failure_surface(
    frame: OracleReplayFrame,
    preceding_buttons: Iterable[str],
    checkpoint: OracleCheckpoint | None = None,
) -> dict[str, Any]:
    """Best-effort, evidence-bearing failure attribution.

    The JSONL source protocol exposes map/position and selected debug hashes,
    not mGBA's complete task list.  Do not pretend this is a debugger verdict:
    every label carries the evidence and a confidence level.
    """

    world = frame.rust_readout.get("world")
    if not isinstance(world, dict):
        world = {}
    source = frame.source_response.get("source_state")
    if not isinstance(source, dict):
        source = {}
    evidence: list[str] = []
    rust_map = world.get("map")
    transition_keys = (
        "transition",
        "menu_transition_frames",
        "warp",
        "fade",
        "map_load",
    )
    if any(world.get(key) not in (None, False, 0) for key in transition_keys):
        evidence.append("Rust readout reports an active transition/fade field")
    if checkpoint is not None:
        try:
            source_map = normalize_source_semantics(checkpoint, source).get("map")
        except RegistryError:
            source_map = None
        if source_map is not None and rust_map not in (None, source_map):
            evidence.append("source and Rust map identities disagree at this checkpoint")
    elif rust_map not in (None, "mays_house2_f") or (
        source.get("map_group"), source.get("map_number")
    ) != (1, 3):
        evidence.append("source or Rust map identity is outside the bedroom field")
    if evidence:
        return {"surface": "transition", "confidence": "high", "evidence": evidence}

    menu_keys = (
        "menu_open",
        "menu_cursor",
        "menu_selection",
        "bedroom_menu_open_frames",
        "active_screen",
        "message",
    )
    ui_readout = any(world.get(key) not in (None, False) for key in menu_keys)
    if ui_readout:
        evidence.append("Rust readout reports a menu/modal/opening state")
    recent = list(preceding_buttons)[-8:]
    ui_buttons = [button for button in recent if button in ("start", "select", "a", "b")]
    if ui_buttons:
        evidence.append("recent tape includes UI buttons: " + ",".join(ui_buttons))
    if evidence:
        return {
            "surface": "menu_ui",
            "confidence": "high" if ui_readout else "medium",
            "evidence": evidence,
        }
    return {
        "surface": "field",
        "confidence": "medium",
        "evidence": ["no reported transition/menu state or recent UI button"],
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_oracle_checkpoint(checkpoint_id: str | None) -> tuple[dict[str, Any], OracleCheckpoint]:
    """Resolve a named, authenticated source boundary or fail before launch."""
    try:
        registry, checkpoint = resolve_checkpoint(checkpoint_id, ORACLE_REGISTRY_PATH)
        require_trusted_oracle(registry)
        require_authenticated(checkpoint)
        return registry, checkpoint
    except RegistryError as exc:
        raise HarnessError(str(exc)) from exc


def reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else canonical_json(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HarnessError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise HarnessError(f"{method} {url} failed: {exc.reason}") from exc


def http_bytes(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.read()
    except urllib.error.URLError as exc:
        raise HarnessError(f"GET {url} failed: {exc.reason}") from exc


class EmeraldService:
    """A service started by this harness and therefore safe for it to stop."""

    def __init__(self, binary: Path) -> None:
        self.port = reserve_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.process = subprocess.Popen(
            [str(binary), "serve", "--port", str(self.port)],
            cwd=TASK_ROOT / "gold_rust",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

    def wait_until_ready(self) -> None:
        # The native renderer embeds authenticated RGB receipt sheets. Cold
        # startup decodes those assets before Axum binds its listener, so a
        # strict 20-second probe can report a false harness failure on a
        # healthy release binary. Keep the timeout bounded but leave room for
        # the measured cold path on CI and slower local disks.
        startup_timeout = 60
        deadline = time.monotonic() + startup_timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                raise HarnessError(f"emerald_gold exited during startup: {stderr.strip()}")
            try:
                http_json(f"{self.base_url}/health")
                return
            except HarnessError:
                time.sleep(0.1)
        raise HarnessError(
            f"emerald_gold did not become healthy within {startup_timeout} seconds"
        )

    def create_rollout(self, checkpoint: str) -> str:
        response = http_json(
            f"{self.base_url}/rollouts", "POST", {"checkpoint": checkpoint}
        )
        rollout_id = response.get("rollout_id")
        if not isinstance(rollout_id, str) or not rollout_id:
            raise HarnessError(f"invalid create-rollout response: {response!r}")
        return rollout_id

    def submit(self, rollout_id: str, action: str, frames: int) -> dict[str, Any]:
        response = http_json(
            f"{self.base_url}/rollouts/{rollout_id}/step",
            "POST",
            {"action": action, "frames": frames},
        )
        if not isinstance(response, dict):
            raise HarnessError(f"invalid action response: {response!r}")
        return response

    def readout(self, rollout_id: str) -> dict[str, Any]:
        response = http_json(f"{self.base_url}/rollouts/{rollout_id}/readout")
        if not isinstance(response, dict):
            raise HarnessError(f"invalid readout response: {response!r}")
        return response

    def frame(self, rollout_id: str) -> bytes:
        rgb = http_bytes(f"{self.base_url}/rollouts/{rollout_id}/frame")
        if len(rgb) != EXPECTED_RGB_BYTES:
            raise HarnessError(
                f"service returned {len(rgb)} RGB bytes, expected {EXPECTED_RGB_BYTES}"
            )
        return rgb

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


def resolve_binary() -> Path:
    supplied = os.environ.get("EMERALD_GOLD_BIN")
    candidates = [Path(supplied)] if supplied else []
    candidates.append(TASK_ROOT / "gold_rust" / "target" / "release" / "emerald_gold")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise HarnessError(
        "release emerald_gold binary not found. Build it first with "
        "`cargo build --release --manifest-path gold_rust/Cargo.toml`, or set EMERALD_GOLD_BIN."
    )


@dataclass(frozen=True)
class TransportCase:
    name: str
    checkpoint: str
    action: str
    total_frames: int
    chunks: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "checkpoint": self.checkpoint,
            "action": self.action,
            "total_frames": self.total_frames,
            "chunks": list(self.chunks),
        }


def generated_transport_cases(seed: int, count: int) -> list[TransportCase]:
    """Small, deterministic, whole-action fuzz corpus plus mandatory regression probes."""
    required = [
        TransportCase("bedroom_down_32_as_16_16", "bedroom_idle", "down", 32, (16, 16)),
        TransportCase("bedroom_down_48_as_16_16_16", "bedroom_idle", "down", 48, (16, 16, 16)),
        TransportCase("bedroom_up_32_as_16_16", "bedroom_idle", "up", 32, (16, 16)),
        TransportCase("bedroom_left_32_as_16_16", "bedroom_idle", "left", 32, (16, 16)),
        TransportCase("bedroom_right_32_as_16_16", "bedroom_idle", "right", 32, (16, 16)),
    ]
    rng = random.Random(seed)
    checkpoints = ("bedroom_idle", "truck_arrival", "rival_outside_lab")
    actions = ("up", "down", "left", "right", "a", "b", "noop")
    cases = list(required)
    for index in range(count):
        chunk_count = rng.choice((2, 3))
        cases.append(
            TransportCase(
                name=f"seed_{seed}_case_{index:03d}",
                checkpoint=rng.choice(checkpoints),
                action=rng.choice(actions),
                total_frames=16 * chunk_count,
                chunks=(16,) * chunk_count,
            )
        )
    return cases


def compact_semantic_readout(readout: dict[str, Any]) -> dict[str, Any]:
    """Exclude image/provenance fields so state and pixel mismatches stay distinct."""
    return {
        "frame_index": readout.get("frame_index"),
        "world": readout.get("world"),
    }


def parity_view(readout: dict[str, Any]) -> dict[str, Any]:
    return {
        "parity_status": readout.get("parity_status"),
        "reference_diff": readout.get("reference_diff"),
    }


def execute_program(
    service: EmeraldService, checkpoint: str, program: Iterable[tuple[str, int]]
) -> dict[str, Any]:
    rollout_id = service.create_rollout(checkpoint)
    for action, frames in program:
        service.submit(rollout_id, action, frames)
    readout = service.readout(rollout_id)
    rgb = service.frame(rollout_id)
    return {
        "readout": readout,
        "semantic": compact_semantic_readout(readout),
        "parity": parity_view(readout),
        "rgb_sha256": sha256(rgb),
    }


def run_transport_case(service: EmeraldService, case: TransportCase) -> dict[str, Any]:
    direct = execute_program(service, case.checkpoint, ((case.action, case.total_frames),))
    chunked = execute_program(
        service, case.checkpoint, ((case.action, chunk) for chunk in case.chunks)
    )
    semantic_equal = direct["semantic"] == chunked["semantic"]
    rgb_equal = direct["rgb_sha256"] == chunked["rgb_sha256"]
    parity_equal = direct["parity"] == chunked["parity"]
    classifications: list[str] = []
    if not semantic_equal or not rgb_equal:
        classifications.append("transport_state_or_pixel_divergence")
    if semantic_equal and rgb_equal and not parity_equal:
        classifications.append("transport_metadata_divergence")
    return {
        **case.as_dict(),
        "direct": direct,
        "chunked": chunked,
        "semantic_equal": semantic_equal,
        "rgb_equal": rgb_equal,
        "parity_equal": parity_equal,
        "classifications": classifications,
    }


def run_rust_transport_fuzz(seed: int, random_cases: int) -> dict[str, Any]:
    binary = resolve_binary()
    service = EmeraldService(binary)
    try:
        service.wait_until_ready()
        results = [
            run_transport_case(service, case)
            for case in generated_transport_cases(seed, random_cases)
        ]
    finally:
        service.close()
    failures = [result for result in results if result["classifications"]]
    return {
        "lane": "rust_transport_contract",
        "seed": seed,
        "binary": str(binary),
        "case_count": len(results),
        "violation_count": len(failures),
        "result": "pass" if not failures else "violations_found",
        "cases": results,
    }


class JsonlOracle:
    def __init__(
        self,
        command: str,
        rom_path: Path,
        state_path: Path,
        rom_sha256: str,
        state_sha256: str,
        registry: dict[str, Any],
        checkpoint: OracleCheckpoint,
    ) -> None:
        self.rom_path = rom_path
        self.state_path = state_path
        self.rom_sha256 = rom_sha256
        self.state_sha256 = state_sha256
        self.emulator: dict[str, Any] = {}
        self.config: dict[str, Any] | None = None
        self.registry = registry
        self.checkpoint = checkpoint
        self.expected_frame_number = -1
        self.loaded_rgb = b""
        self.last_load_response: dict[str, Any] = {}
        self.process = subprocess.Popen(
            shlex.split(command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        try:
            self.load()
        except Exception:
            self.close()
            raise

    def load(self) -> bytes:
        rgb, load_response = self.request(
            {
                "op": "load",
                "rom_path": str(self.rom_path),
                "state_path": str(self.state_path),
            }
        )
        if load_response.get("rom_sha256") != self.rom_sha256:
            raise HarnessError("oracle adapter did not confirm the pinned ROM SHA-256")
        if load_response.get("state_sha256") != self.state_sha256:
            raise HarnessError("oracle adapter did not confirm the pinned save-state SHA-256")
        emulator = load_response.get("emulator")
        if not isinstance(emulator, dict) or not all(
            isinstance(emulator.get(field), str) and emulator[field]
            for field in ("core", "version", "config_sha256")
        ):
            raise HarnessError(
                "oracle load response must identify emulator core, version, and config_sha256"
            )
        if emulator != self.registry["oracle"]["emulator"]:
            raise HarnessError(
                "oracle emulator identity does not match fixtures/gold/oracle_registry.json"
            )
        self.emulator = emulator
        config = load_response.get("config")
        if config != self.registry["oracle"]["config"]:
            raise HarnessError(
                "oracle runtime config does not match fixtures/gold/oracle_registry.json"
            )
        if emulator["config_sha256"] != sha256(
            canonical_json(config).encode("utf-8")
        ):
            raise HarnessError("oracle config_sha256 does not authenticate its config")
        self.config = config
        actual_initial = load_response.get("source_state")
        if not isinstance(actual_initial, dict) or not initial_state_matches(
            self.checkpoint, actual_initial
        ):
            raise HarnessError("oracle initial source state does not match the named registry checkpoint")
        self.loaded_rgb = rgb
        self.last_load_response = load_response
        return rgb

    def request(self, request: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
        if self.process.poll() is not None:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise HarnessError(f"oracle adapter exited: {stderr.strip()}")
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(canonical_json(request) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise HarnessError(f"oracle adapter produced no response: {stderr.strip()}")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HarnessError(f"oracle adapter returned invalid JSON: {line!r}") from exc
        if not response.get("ok"):
            raise HarnessError(f"oracle adapter error: {response.get('error', response)!r}")
        encoded = response.get("frame_rgb_b64")
        if not isinstance(encoded, str):
            raise HarnessError("oracle response has no frame_rgb_b64 string")
        try:
            rgb = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise HarnessError("oracle frame_rgb_b64 is not valid base64") from exc
        if len(rgb) != EXPECTED_RGB_BYTES:
            raise HarnessError(
                f"oracle returned {len(rgb)} RGB bytes, expected {EXPECTED_RGB_BYTES}"
            )
        claimed_rgb_sha256 = response.get("frame_rgb_sha256")
        actual_rgb_sha256 = sha256(rgb)
        if claimed_rgb_sha256 != actual_rgb_sha256:
            raise HarnessError("oracle response frame_rgb_sha256 does not match RGB bytes")
        expected_frame_number = (
            0
            if request.get("op") == "load"
            else self.expected_frame_number + 1
        )
        if response.get("frame_number") != expected_frame_number:
            raise HarnessError(
                "oracle response frame_number is not the expected deterministic sequence"
            )
        self.expected_frame_number = expected_frame_number
        return rgb, response

    def step(self, buttons: list[str]) -> tuple[bytes, dict[str, Any]]:
        return self.request({"op": "step", "buttons": buttons})

    def close(self) -> None:
        if self.process.poll() is None:
            if self.process.stdin is not None and not self.process.stdin.closed:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)


def oracle_preflight(
    rom_path: Path | None,
    state_path: Path | None,
    command: str | None,
    checkpoint: OracleCheckpoint,
    registry: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    source = require_authenticated(checkpoint).source
    assert source is not None
    if rom_path is None:
        problems.append("no --oracle-rom supplied")
    elif not rom_path.is_file():
        problems.append(f"ROM not found: {rom_path}")
    elif file_sha256(rom_path) != registry["rom_sha256"]:
        problems.append("ROM SHA-256 does not match the oracle registry")
    if state_path is None:
        problems.append("no --oracle-state supplied")
    elif not state_path.is_file():
        problems.append(f"save state not found: {state_path}")
    elif file_sha256(state_path) != source["state_sha256"]:
        problems.append(
            f"save state SHA-256 does not match authenticated checkpoint {checkpoint.checkpoint_id}"
        )
    if not command:
        problems.append("no --oracle-command supplied")
    else:
        command_parts = shlex.split(command)
        if not command_parts:
            problems.append("--oracle-command was empty")
        elif not (Path(command_parts[0]).is_file() or shutil.which(command_parts[0])):
            problems.append(f"oracle adapter executable not found: {command_parts[0]}")
    return problems


def expand_segments(segments: Iterable[tuple[str, int]]) -> list[str]:
    tape: list[str] = []
    for button, frames in segments:
        tape.extend([button] * frames)
    return tape


def segment_boundaries(segments: Iterable[tuple[str, int]]) -> list[int]:
    boundaries: list[int] = []
    total = 0
    for _, frames in segments:
        total += frames
        boundaries.append(total)
    return boundaries


def compress_tape(tape: Iterable[str]) -> list[tuple[str, int]]:
    segments: list[tuple[str, int]] = []
    for button in tape:
        if segments and segments[-1][0] == button:
            previous_button, frames = segments[-1]
            segments[-1] = (previous_button, frames + 1)
        else:
            segments.append((button, 1))
    return segments


def source_tapes(
    seed: int,
    count: int,
    steps: int,
    checkpoint: OracleCheckpoint,
    segment: str = "bedroom",
) -> list[dict[str, Any]]:
    """Deterministic VBlank tapes for one authenticated source boundary.

    Bedroom retains its historical named corpus so old reports remain directly
    comparable. Other named checkpoints begin with neutral/input-probe tapes;
    route-specific tapes are added only after a source state exists.
    """
    rng = random.Random(seed)
    bedroom_segments: list[tuple[str, tuple[tuple[str, int], ...], str]] = [
        (
            "fixture_down_48",
            (("down", 16), ("down", 16), ("down", 16)),
            "checked-in source fixture",
        ),
        (
            "fixture_up_48",
            (("up", 16), ("up", 16), ("up", 16)),
            "checked-in source fixture",
        ),
        (
            "fixture_left_48",
            (("left", 16), ("left", 16), ("left", 16)),
            "checked-in source fixture",
        ),
        (
            "fixture_right_48",
            (("right", 16), ("right", 16), ("right", 16)),
            "checked-in source fixture",
        ),
        ("fixture_start_16", (("start", 16),), "checked-in source fixture"),
        ("fixture_a_16", (("a", 16),), "checked-in source fixture"),
        (
            "fixture_select_modal_open_close",
            # mGBA observes: invisible Select owner on V1, border first
            # visible on V5, input-ready on V64, B close visible for two
            # further VBlanks, and field ownership at V67.  Keeping the
            # adjacent no-op segments is intentional: each edge is a semantic
            # comparison boundary even though the held physical key is equal.
            (("select", 1), ("noop", 3), ("noop", 1), ("noop", 59), ("b", 1), ("noop", 2)),
            "source-observed Select registration modal boundaries",
        ),
        (
            "fixture_start_menu_handoff",
            # Start owns V1-V8.  The direction on V9 is handed once to the
            # just-installed menu task; the following held direction must not
            # auto-repeat.  This is a controller ownership handoff, not a
            # menu-navigation throughput benchmark.
            (("start", 1), ("noop", 7), ("up", 1), ("up", 1)),
            "source-observed Start opening to menu input-owner handoff",
        ),
        (
            "fixture_bedroom_north_exit_settle",
            # This is the source-authenticated upstairs stair route from
            # concrete/bedroom_to_downstairs_v1.json.  The two final 16-frame
            # Up segments cross the north stair/warp boundary; the neutral
            # settle period retains transition, map, and first stable field
            # frames in one VBlank proof tape.
            (("right", 16), ("up", 16), ("left", 16), ("up", 16), ("up", 16), ("noop", 128)),
            "authenticated bedroom north-exit/stair boundary route",
        ),
        (
            "published_bedroom_explorer_seed1",
            (
                ("down", 16),
                ("down", 16),
                ("right", 16),
                ("right", 16),
                ("down", 16),
                ("left", 16),
                ("down", 16),
                ("down", 16),
            ),
            "published GameBench rollout trace",
        ),
    ]
    # For non-bedroom checkpoints the caller's --steps value is the useful
    # contract: short probes catch turn-in-place semantics, while a longer
    # probe is required to exercise a door fade/warp all the way through its
    # destination arrival.  Preserve the historical bedroom corpus lengths
    # below so its frozen regression numbers remain comparable.
    generic_probe_steps = steps if checkpoint.checkpoint_id != "bedroom_idle" else 16
    generic_segments = [
        (
            f"{checkpoint.checkpoint_id}_idle_{generic_probe_steps}",
            (("noop", generic_probe_steps),),
            "checkpoint idle probe",
        ),
        *[
            (
                f"{checkpoint.checkpoint_id}_{button}_{generic_probe_steps}",
                ((button, generic_probe_steps),),
                "checkpoint physical-input probe",
            )
            for button in ("up", "down", "left", "right", "a", "b", "start", "select")
        ],
    ]
    if segment == "clock_tv" and checkpoint.checkpoint_id == "bedroom_idle":
        # Checked-in source program from the authenticated bedroom boundary.
        # It covers the clock interaction, TV broadcast, Mom's downstairs
        # dialogue, and the first stable downstairs state in one continuous
        # tape; keeping it whole prevents a checkpoint reload from masking
        # task ownership or fade timing errors.
        mandatory_segments = [
            (
                "fixture_bedroom_clock_tv_downstairs",
                (
                    ("up", 16),
                    ("a", 1),
                    ("a", 1),
                    ("a", 1),
                    ("noop", 72),
                    *tuple(
                        item
                        for _ in range(12)
                        for item in (("a", 1), ("noop", 240))
                    ),
                    ("up", 1),
                    ("noop", 1),
                    ("a", 1),
                    ("noop", 240),
                    ("noop", 240),
                ),
                "checked-in source clock/TV/downstairs program",
            )
        ]
    elif segment == "mays_house_exit" and checkpoint.checkpoint_id == "bedroom_idle":
        # This is intentionally a separate corpus from the frozen bedroom
        # gate. It starts at the authenticated upstairs state, crosses the
        # north stair into May's 1F, waits for the source downstairs script,
        # acknowledges the fourteen rival pages (including the source's extra
        # debounce edge), then walks through the house exit into Littleroot.
        # Keep the complete tape: the transition and the dialogue/object-event
        # ownership are one contiguous source segment.
        mandatory_segments = [
            (
                "fixture_mays_house_1f_transition",
                (("right", 16), ("up", 16), ("left", 16), ("up", 32), ("noop", 128)),
                "authenticated upstairs stair → Mays House 1F transition",
            ),
            (
                "fixture_mays_house_1f_exit_to_littleroot",
                (
                    ("up", 64),
                    ("down", 128),
                    ("noop", 600),
                    *tuple(
                        item
                        for _ in range(14)
                        for item in (("a", 1), ("noop", 300))
                    ),
                    ("down", 128),
                ),
                "authenticated Mays House 1F dialogue and house-exit warp",
            ),
        ]
    elif segment == "littleroot_field" and checkpoint.checkpoint_id == "littleroot_field_ready":
        # The settled Mays-house exit is the authenticated boundary for the
        # next contiguous region. Keep long one-direction holds here: the
        # field camera must continue its one-pixel rail across logical tile
        # commits, and a blocked Up edge must remain a live animation task
        # rather than becoming a free walk or a stationary rollout.
        mandatory_segments = [
            (
                "fixture_littleroot_field_left_144",
                (("left", 144),),
                "authenticated Littleroot westward camera/collision rail",
            ),
            (
                "fixture_littleroot_field_right_48",
                (("right", 48),),
                "authenticated Littleroot eastward camera/collision rail",
            ),
            (
                "fixture_littleroot_field_down_48",
                (("down", 48),),
                "authenticated Littleroot southward field rail",
            ),
            (
                "fixture_littleroot_field_up_blocked_16",
                (("up", 16),),
                "authenticated Littleroot blocked north-edge task",
            ),
        ]
    elif segment == "route101" and checkpoint.checkpoint_id in {
        "route101_post_lab",
        "route101_north_lane",
        "route101_west_lane",
        "route101_mid_lane",
        "route101_east_lane",
    }:
        # These are source-authenticated settled lane receipts. Keep an idle
        # boundary beside the next calibrated one-direction pulse so a
        # compositor can never hide a bad saved-state sprite behind movement.
        route101_lane_tapes = {
            "route101_post_lab": (
                ("noop", 16),
                ("up", 16),
            ),
            "route101_north_lane": (
                ("noop", 16),
                ("left", 16),
                ("up", 16),
            ),
            "route101_west_lane": (
                ("noop", 16),
                ("up", 16),
            ),
            "route101_mid_lane": (
                ("noop", 16),
                ("right", 16),
            ),
            "route101_east_lane": (
                ("noop", 16),
                ("left", 16),
            ),
        }
        lane_segments = route101_lane_tapes[checkpoint.checkpoint_id]
        mandatory_segments = [
            (
                f"fixture_{checkpoint.checkpoint_id}_settled",
                # An authenticated checkpoint receipt is the frame returned
                # immediately after reload. Keep this tape empty so a later
                # object-animation VBlank cannot be mislabelled as a static
                # checkpoint failure; the following pulse tape owns timing.
                (("noop", 0),),
                "authenticated settled Route 101 lane boundary",
            ),
            (
                f"fixture_{checkpoint.checkpoint_id}_next_pulse",
                lane_segments,
                "authenticated Route 101 corridor pulse",
            ),
        ]
    elif segment == "route101_wild_battle" and checkpoint.checkpoint_id in {
        "route101_wild_battle",
        "route101_wild_command",
        "route101_wild_after_turn_one",
        "route101_wild_after_turn_two",
        "route101_wild_after_turn_three",
        "route101_wild_after_turn_four",
        "route101_wild_after_turn_five",
        "route101_wild_after_turn_six",
        "route101_wild_victory_resume",
    }:
        # Keep the authenticated wild-battle checkpoints on their native
        # ownership boundaries.  In particular, the entry receipt owns the
        # ``Wild WURMPLE appeared!`` printer, while the command receipt owns
        # the first player-ball/send-out task.  A generic eight-button probe
        # would skip that handoff and make a stationary/settled battle look
        # correct, so every tape below is a source-authenticated program.
        if checkpoint.checkpoint_id == "route101_wild_battle":
            mandatory_segments = [
                (
                    "fixture_route101_wild_entry_idle_64",
                    (("noop", 64),),
                    "authenticated wild-entry message and trainer rail",
                ),
                (
                    "fixture_route101_wild_entry_to_command_61",
                    (("a", 1), ("noop", 60)),
                    "authenticated entry-message dismissal/send-out handoff",
                ),
            ]
        elif checkpoint.checkpoint_id == "route101_wild_command":
            mandatory_segments = [
                (
                    "fixture_route101_wild_command_idle_64",
                    (("noop", 64),),
                    "authenticated first player-ball command handoff",
                ),
                (
                    "fixture_route101_wild_default_move_64",
                    (("a", 1), ("noop", 30), ("a", 1), ("noop", 32)),
                    "authenticated first wild-battle move ownership",
                ),
            ]
        elif checkpoint.checkpoint_id == "route101_wild_victory_resume":
            mandatory_segments = [
                (
                    "fixture_route101_wild_victory_resume_300",
                    (("noop", 300),),
                    "authenticated post-victory Route 101 field resume",
                ),
            ]
        else:
            mandatory_segments = [
                (
                    f"fixture_{checkpoint.checkpoint_id}_idle_64",
                    (("noop", 64),),
                    "authenticated wild-battle turn checkpoint",
                ),
                (
                    f"fixture_{checkpoint.checkpoint_id}_default_move_64",
                    (("a", 1), ("noop", 30), ("a", 1), ("noop", 32)),
                    "authenticated wild-battle turn replay",
                ),
            ]
    elif segment == "starter_picker" and checkpoint.checkpoint_id == "starter_picker":
        # The picker is the first post-rescue boundary with a source-
        # authenticated affine/UI task. Keep input edges separate from the
        # long reveal tape so a compositor cannot hide a bad handoff behind a
        # later confirmation state.
        mandatory_segments = [
            (
                "fixture_starter_picker_idle_16",
                (("noop", 16),),
                "authenticated starter picker idle/hand rail",
            ),
            (
                "fixture_starter_picker_left_settle",
                (("left", 1), ("noop", 16)),
                "authenticated Treecko selection transition",
            ),
            (
                "fixture_starter_picker_right_settle",
                (("right", 1), ("noop", 16)),
                "authenticated Torchic selection transition",
            ),
            (
                "fixture_starter_picker_confirm_reveal",
                (("a", 1), ("noop", 31)),
                "authenticated starter confirmation/reveal choreography",
            ),
        ]
    elif segment == "starter_battle" and checkpoint.checkpoint_id == "starter_battle":
        # The battle checkpoint begins at the authenticated command-ready
        # receipt. These probes establish presentation and input ownership;
        # turn/outcome tapes remain a separate closure target.
        mandatory_segments = [
            (
                "fixture_starter_battle_idle_16",
                (("noop", 16),),
                "authenticated starter battle command-ready idle",
            ),
            (
                "fixture_starter_battle_left_16",
                (("left", 16),),
                "authenticated starter battle cursor probe",
            ),
            (
                "fixture_starter_battle_a_16",
                (("a", 1), ("noop", 15)),
                "authenticated starter battle command handoff",
            ),
            (
                "fixture_starter_battle_bag_16",
                (("right", 1), ("noop", 1), ("a", 1), ("noop", 13)),
                "authenticated action-cursor → BAG selection handoff",
            ),
            (
                "fixture_starter_battle_party_16",
                (("down", 1), ("noop", 1), ("a", 1), ("noop", 13)),
                "authenticated action-cursor → party selection handoff",
            ),
        ]
    else:
        mandatory_segments = bedroom_segments if checkpoint.checkpoint_id == "bedroom_idle" else generic_segments
    tapes = [
        {
            "name": name,
            "origin": origin,
            "segments": [
                {"button": button, "frames": frames} for button, frames in segments
            ],
            "semantic_boundaries": segment_boundaries(segments),
            "tape": expand_segments(segments),
        }
        for name, segments, origin in mandatory_segments
    ]
    for index in range(count):
        tape = [rng.choice(BUTTONS) for _ in range(steps)]
        segments = compress_tape(tape)
        tapes.append(
            {
                "name": f"random_seed_{seed}_{index:03d}",
                "origin": "deterministic random fuzz",
                "segments": [
                    {"button": button, "frames": frames}
                    for button, frames in segments
                ],
                "semantic_boundaries": segment_boundaries(segments),
                "tape": tape,
            }
        )
    return tapes


def pixel_diff_summary(actual: bytes, expected: bytes) -> dict[str, Any]:
    changed_channels = 0
    changed_pixels = 0
    max_channel_delta = 0
    absolute_delta_sum = 0
    for offset in range(0, EXPECTED_RGB_BYTES, 3):
        pixel_changed = False
        for channel in range(3):
            delta = abs(actual[offset + channel] - expected[offset + channel])
            if delta:
                changed_channels += 1
                pixel_changed = True
                max_channel_delta = max(max_channel_delta, delta)
                absolute_delta_sum += delta
        changed_pixels += int(pixel_changed)
    return {
        "changed_pixels": changed_pixels,
        "total_pixels": 240 * 160,
        "changed_channels": changed_channels,
        "total_channels": EXPECTED_RGB_BYTES,
        "max_channel_delta": max_channel_delta,
        "mean_absolute_channel_delta": absolute_delta_sum / EXPECTED_RGB_BYTES,
    }


def source_semantic_view(
    response: dict[str, Any], checkpoint: OracleCheckpoint
) -> dict[str, Any]:
    source_state = response.get("source_state")
    if not isinstance(source_state, dict):
        raise HarnessError("oracle response has no source_state object")
    try:
        return normalize_source_semantics(checkpoint, source_state)
    except RegistryError as exc:
        raise HarnessError(str(exc)) from exc


def rust_semantic_view(readout: dict[str, Any]) -> dict[str, Any]:
    world = readout.get("world")
    if not isinstance(world, dict):
        raise HarnessError("Rust readout has no world object")
    return {"player": world.get("player"), "map": world.get("map")}


def trace_tick(
    *,
    vblank: int,
    button: str | None,
    rust_rgb: bytes,
    source_rgb: bytes,
    rust_readout: dict[str, Any],
    source_response: dict[str, Any],
    semantic_comparable: bool,
    checkpoint: OracleCheckpoint,
) -> dict[str, Any]:
    source_state = source_response.get("source_state")
    world = rust_readout.get("world")
    if not isinstance(source_state, dict) or not isinstance(world, dict):
        raise HarnessError("cannot record proof tape without source and Rust state")
    semantic_equal = (
        rust_semantic_view(rust_readout) == source_semantic_view(source_response, checkpoint)
        if semantic_comparable
        else None
    )
    return {
        "vblank": vblank,
        "button": button,
        "rust_frame_index": rust_readout.get("frame_index"),
        "source_frame_number": source_response.get("frame_number"),
        "rust_rgb_sha256": sha256(rust_rgb),
        "source_rgb_sha256": sha256(source_rgb),
        "pixels_equal": rust_rgb == source_rgb,
        "rust_state_sha256": sha256(canonical_json(world).encode("utf-8")),
        "source_state_sha256": source_state.get("state_sha256"),
        "semantic_comparable": semantic_comparable,
        "semantic_equal": semantic_equal,
        "rust_semantic": (
            rust_semantic_view(rust_readout) if semantic_comparable else None
        ),
        "source_semantic": (
            source_semantic_view(source_response, checkpoint) if semantic_comparable else None
        ),
    }


def write_ppm(path: Path, rgb: bytes) -> None:
    if path.exists():
        raise HarnessError(f"refusing to overwrite mismatch artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        output.write(b"P6\n240 160\n255\n")
        output.write(rgb)


def mismatch_record(
    *,
    case_name: str,
    artifact_dir: Path,
    vblank: int,
    button: str | None,
    rust_rgb: bytes,
    source_rgb: bytes,
    rust_readout: dict[str, Any],
    source_response: dict[str, Any],
    semantic_comparable: bool,
    checkpoint: OracleCheckpoint,
    persist_frames: bool = True,
) -> dict[str, Any]:
    safe_name = "".join(
        character if character.isalnum() or character in ("-", "_") else "_"
        for character in case_name
    )
    rust_path = artifact_dir / f"{safe_name}-vblank-{vblank:04d}-rust.ppm"
    source_path = artifact_dir / f"{safe_name}-vblank-{vblank:04d}-source.ppm"
    if persist_frames:
        write_ppm(rust_path, rust_rgb)
        write_ppm(source_path, source_rgb)
    rust_semantic = rust_semantic_view(rust_readout)
    source_semantic = source_semantic_view(source_response, checkpoint)
    pixels_equal = rust_rgb == source_rgb
    semantic_equal = rust_semantic == source_semantic if semantic_comparable else None
    if pixels_equal and semantic_equal is True:
        classification = "exact"
    elif pixels_equal and semantic_equal is None:
        classification = "pixel_exact_semantics_not_compared"
    elif not pixels_equal and semantic_equal is False:
        classification = "semantic_and_pixel_divergence"
    elif not pixels_equal:
        classification = "pixel_divergence"
    else:
        classification = "semantic_divergence"
    return {
        "vblank": vblank,
        "button": button,
        "classification": classification,
        "pixels_equal": pixels_equal,
        "semantic_equal": semantic_equal,
        "semantic_comparison": (
            "task action boundary"
            if semantic_comparable
            else "not comparable between task action boundaries"
        ),
        "rust_rgb_sha256": sha256(rust_rgb),
        "source_rgb_sha256": sha256(source_rgb),
        "pixel_diff": pixel_diff_summary(rust_rgb, source_rgb),
        "rust_frame_ppm": str(rust_path) if persist_frames else None,
        "source_frame_ppm": str(source_path) if persist_frames else None,
        "rust_semantic": rust_semantic,
        "source_semantic": source_semantic,
        "source_state": source_response.get("source_state"),
    }


def replay_oracle_tape(
    service: EmeraldService,
    oracle: JsonlOracle,
    tape: list[str],
    checkpoint: OracleCheckpoint,
) -> list[OracleReplayFrame]:
    """Replay a raw VBlank tape from the authenticated source checkpoint.

    This is deliberately independent of the reporting cadence used by the main
    corpus.  A minimised proof compares semantics on *every* VBlank, so it can
    retain the first semantic divergence even when deleting inputs changes run
    length and therefore changes the original segment boundaries.
    """

    rollout_id = service.create_rollout(checkpoint.rust_checkpoint)
    source_rgb = oracle.load()
    source = require_authenticated(checkpoint).source
    assert source is not None
    if sha256(source_rgb) != source["initial_rgb_sha256"]:
        raise HarnessError("mGBA source boundary changed while minimising a tape")
    source_response = oracle.last_load_response
    rust_rgb = service.frame(rollout_id)
    rust_readout = service.readout(rollout_id)
    if rust_readout.get("frame_index") != 0:
        raise HarnessError("Rust rollout did not begin at frame_index 0 during minimisation")
    frames = [
        OracleReplayFrame(
            vblank=0,
            button=None,
            rust_rgb=rust_rgb,
            source_rgb=source_rgb,
            rust_readout=rust_readout,
            source_response=source_response,
            semantic_equal=(
                rust_semantic_view(rust_readout) == source_semantic_view(source_response, checkpoint)
            ),
        )
    ]
    for vblank, button in enumerate(tape, start=1):
        service.submit(rollout_id, button, 1)
        rust_rgb = service.frame(rollout_id)
        rust_readout = service.readout(rollout_id)
        if rust_readout.get("frame_index") != vblank:
            raise HarnessError("Rust frame index drifted during minimisation replay")
        source_rgb, source_response = oracle.step([] if button == "noop" else [button])
        frames.append(
            OracleReplayFrame(
                vblank=vblank,
                button=button,
                rust_rgb=rust_rgb,
                source_rgb=source_rgb,
                rust_readout=rust_readout,
                source_response=source_response,
                semantic_equal=(
                    rust_semantic_view(rust_readout) == source_semantic_view(source_response, checkpoint)
                ),
            )
        )
    return frames


def first_selected_divergence(
    frames: Iterable[OracleReplayFrame], selected: str
) -> OracleReplayFrame | None:
    if selected not in ("pixel", "semantic"):
        raise ValueError(f"unsupported minimisation target: {selected}")
    for frame in frames:
        if selected == "pixel" and frame.rust_rgb != frame.source_rgb:
            return frame
        if selected == "semantic" and not frame.semantic_equal:
            return frame
    return None


def ddmin_tape(
    tape: list[str], reproduces: Any
) -> list[str]:
    """Deterministically delete VBlank samples, then neutralise remaining keys.

    ``reproduces`` must be a pure predicate over a fresh replay.  This classic
    complement-based delta debugger never mutates the input tape and stops at a
    1-minimal subsequence under deletions; the final no-op pass makes the proof
    easier to read without claiming globally minimal input.
    """

    current = list(tape)
    if not reproduces(current):
        raise HarnessError("refusing to minimise a tape that does not reproduce its target")
    # A failure occurring in a prefix remains observable in every longer prefix,
    # so binary search avoids spending minimisation budget on irrelevant tails.
    low, high = 1, len(current)
    while low < high:
        middle = (low + high) // 2
        if reproduces(current[:middle]):
            high = middle
        else:
            low = middle + 1
    current = current[:high]
    granularity = 2
    while len(current) >= 2:
        chunk = max(1, (len(current) + granularity - 1) // granularity)
        reduced = False
        for start in range(0, len(current), chunk):
            candidate = current[:start] + current[start + chunk :]
            if candidate and reproduces(candidate):
                current = candidate
                granularity = max(2, granularity - 1)
                reduced = True
                break
        if not reduced:
            if granularity >= len(current):
                break
            granularity = min(len(current), granularity * 2)
    for index, button in enumerate(current):
        if button == "noop":
            continue
        candidate = list(current)
        candidate[index] = "noop"
        if reproduces(candidate):
            current = candidate
    return current


def minimise_case(
    *,
    service: EmeraldService,
    oracle: JsonlOracle,
    tape_spec: dict[str, Any],
    selected: str,
    artifact_dir: Path,
    identity: dict[str, Any],
    checkpoint: OracleCheckpoint,
    max_replays: int,
    ppu_capture_root: Path | None = None,
    ppu_rom: Path | None = None,
    ppu_state: Path | None = None,
) -> dict[str, Any]:
    """Produce a self-contained, pinned proof tape for one selected failure."""

    original_tape = list(tape_spec["tape"])
    replay_count = 0
    budget_exhausted = False

    def reproduces(candidate: list[str]) -> bool:
        nonlocal replay_count, budget_exhausted
        # Reserve one authenticated replay to verify and serialize the final
        # candidate, so ``replay_count`` never exceeds the advertised cap.
        if replay_count >= max_replays - 1:
            budget_exhausted = True
            return False
        replay_count += 1
        target = first_selected_divergence(
            replay_oracle_tape(service, oracle, candidate, checkpoint), selected
        )
        # A shorter tape that happens to fail for some unrelated reason is not
        # a safe reduction of this probe.  Keep the *first selected* boundary
        # at the VBlank observed in the full tape; ddmin can still trim its
        # irrelevant tail and neutralise actions while retaining the event.
        return target is not None and target.vblank == original_target.vblank

    # Verify before shrinking: a target absent from the full tape is a skipped
    # result, never a silently successful minimisation.
    original_frames = replay_oracle_tape(service, oracle, original_tape, checkpoint)
    replay_count += 1
    original_target = first_selected_divergence(original_frames, selected)
    if original_target is None:
        return {
            "selected": selected,
            "status": "target_not_present",
            "original_vblanks": len(original_tape),
            "oracle_identity": identity,
        }
    minimized_tape = ddmin_tape(original_tape, reproduces)
    minimized_frames = replay_oracle_tape(service, oracle, minimized_tape, checkpoint)
    replay_count += 1
    target = first_selected_divergence(minimized_frames, selected)
    if target is None:
        raise HarnessError("minimiser emitted a tape that no longer reproduces its target")
    prefix = minimized_tape[: target.vblank]
    safe_name = "".join(
        char if char.isalnum() or char in ("-", "_") else "_"
        for char in tape_spec["name"]
    )
    proof_dir = artifact_dir / "minimized"
    proof_path = proof_dir / f"{safe_name}-{selected}.json"
    if proof_path.exists():
        raise HarnessError(f"refusing to overwrite minimised proof: {proof_path}")
    target_record = mismatch_record(
        case_name=f"minimized-{safe_name}-{selected}",
        artifact_dir=proof_dir,
        vblank=target.vblank,
        button=target.button,
        rust_rgb=target.rust_rgb,
        source_rgb=target.source_rgb,
        rust_readout=target.rust_readout,
        source_response=target.source_response,
        semantic_comparable=True,
        checkpoint=checkpoint,
    )
    proof = {
        "schema": "gamebench.pokemon_emerald.minimized_oracle_tape.v1",
        "selected_divergence": selected,
        "oracle_identity": identity,
        "origin": {"case": tape_spec["name"], "seed_tape_sha256": sha256(canonical_json(original_tape).encode("utf-8"))},
        "original_vblanks": len(original_tape),
        "minimized_vblanks": len(minimized_tape),
        "preserved_first_selected_vblank": original_target.vblank,
        "minimized_segments": [
            {"button": button, "frames": frames}
            for button, frames in compress_tape(minimized_tape)
        ],
        "first_selected_divergence": target_record,
        "attribution": classify_failure_surface(target, prefix, checkpoint),
        "replay_count": replay_count,
        "search_complete": not budget_exhausted,
        "max_replays": max_replays,
        "proof_tape": [
            trace_tick(
                vblank=frame.vblank,
                button=frame.button,
                rust_rgb=frame.rust_rgb,
                source_rgb=frame.source_rgb,
                rust_readout=frame.rust_readout,
                source_response=frame.source_response,
                semantic_comparable=True,
                checkpoint=checkpoint,
            )
            for frame in minimized_frames
        ],
    }
    proof["proof_tape_sha256"] = sha256(canonical_json(proof["proof_tape"]).encode("utf-8"))
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ppu_capture: dict[str, Any] | None = None
    if ppu_capture_root is not None:
        if ppu_rom is None or ppu_state is None:
            raise HarnessError("PPU capture was selected without an authenticated ROM/state")
        ppu_capture_root.mkdir(parents=True, exist_ok=True)
        capture_name = f"{safe_name}-{selected}-vblank-{target.vblank:04d}"
        capture_dir = ppu_capture_root / capture_name
        tape_path = proof_dir / f"{safe_name}-{selected}-ppu-tape.json"
        if capture_dir.exists() or tape_path.exists():
            raise HarnessError("refusing to overwrite minimized PPU capture evidence")
        tape_path.write_text(json.dumps(minimized_tape) + "\n", encoding="utf-8")
        command = [
            sys.executable,
            str(SCRIPT_DIR / "capture_emerald_ppu_receipt.py"),
            "--checkpoint", checkpoint.checkpoint_id,
            "--rom", str(ppu_rom), "--state", str(ppu_state),
            "--tape", str(tape_path), "--vblank", str(target.vblank),
            "--output-dir", str(capture_dir),
        ]
        capture_dir.mkdir()
        try:
            subprocess.run(command, check=True, text=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            raise HarnessError(
                "authenticated minimized PPU capture failed closed: "
                + (exc.stderr.strip() or exc.stdout.strip() or str(exc))
            ) from exc
        receipt_path = capture_dir / "receipt.json"
        if not receipt_path.is_file():
            raise HarnessError("PPU capture completed without a receipt")
        ppu_capture = {
            "status": "captured",
            "receipt_path": str(receipt_path),
            "tape_path": str(tape_path),
            "vblank": target.vblank,
        }
    return {
        "selected": selected,
        "status": "reproduced",
        "original_vblanks": len(original_tape),
        "minimized_vblanks": len(minimized_tape),
        "preserved_first_selected_vblank": original_target.vblank,
        "first_selected_divergence": target_record,
        "attribution": proof["attribution"],
        "proof_path": str(proof_path),
        "replay_count": replay_count,
        "search_complete": not budget_exhausted,
        "max_replays": max_replays,
        "ppu_capture": ppu_capture,
    }


def run_oracle_pixel_fuzz(
    seed: int,
    random_cases: int,
    steps: int,
    rom_path: Path,
    state_path: Path,
    command: str,
    artifact_dir: Path,
    registry: dict[str, Any],
    checkpoint: OracleCheckpoint,
    minimize_mismatches: str = "none",
    minimize_limit: int = 0,
    minimize_max_replays: int = 64,
    ppu_capture_root: Path | None = None,
    segment: str = "bedroom",
) -> dict[str, Any]:
    """Compare RGB buffers every VBlank, recording first and final tape divergences."""
    binary = resolve_binary()
    rom_sha256 = file_sha256(rom_path)
    state_sha256 = file_sha256(state_path)
    source = require_authenticated(checkpoint).source
    assert source is not None
    if rom_sha256 != registry["rom_sha256"]:
        raise HarnessError(
            "oracle ROM does not match the pinned Pokémon Emerald (USA, Europe) SHA-256"
        )
    if state_sha256 != source["state_sha256"]:
        raise HarnessError(
            f"oracle state does not match authenticated checkpoint {checkpoint.checkpoint_id}"
        )

    service: EmeraldService | None = None
    oracle: JsonlOracle | None = None
    try:
        service = EmeraldService(binary)
        service.wait_until_ready()
        oracle = JsonlOracle(
            command,
            rom_path,
            state_path,
            rom_sha256,
            state_sha256,
            registry,
            checkpoint,
        )
        cases: list[dict[str, Any]] = []
        for case_index, tape_spec in enumerate(
            source_tapes(seed, random_cases, steps, checkpoint, segment)
        ):
            # The checkpoint is deliberately not used as a source of truth.  A
            # source state is loaded afresh for each tape, and the named
            # checkpoint is merely the equivalent in-tree starting point.
            rollout_id = service.create_rollout(checkpoint.rust_checkpoint)
            if case_index == 0:
                source_initial = oracle.loaded_rgb
                source_initial_response = oracle.last_load_response
            else:
                source_initial = oracle.load()
                source_initial_response = oracle.last_load_response
            source_initial_sha256 = sha256(source_initial)
            if source_initial_sha256 != source["initial_rgb_sha256"]:
                raise HarnessError(
                    f"mGBA source boundary does not match {checkpoint.checkpoint_id} RGB fixture"
                )
            rust_initial = service.frame(rollout_id)
            rust_initial_readout = service.readout(rollout_id)
            if rust_initial_readout.get("frame_index") != 0:
                raise HarnessError("Rust rollout did not begin at frame_index 0")
            first_mismatch: dict[str, Any] | None = None
            final_comparison: dict[str, Any] | None = None
            # Diagnostic mode persists every source/Rust frame, rather than
            # only the first and final divergent frames.  This is useful for
            # phase-sensitive animation debugging while keeping normal runs
            # bounded and unchanged.
            persist_all_frames = os.environ.get("EMERALD_FUZZ_SAVE_ALL_FRAMES") == "1"
            compared_source_frames = 1
            initial_semantic_equal = (
                rust_semantic_view(rust_initial_readout)
                == source_semantic_view(source_initial_response, checkpoint)
            )
            pixel_mismatch_frames = int(rust_initial != source_initial)
            semantic_boundary_mismatches = int(not initial_semantic_equal)
            proof_tape = [
                trace_tick(
                    vblank=0,
                    button=None,
                    rust_rgb=rust_initial,
                    source_rgb=source_initial,
                    rust_readout=rust_initial_readout,
                    source_response=source_initial_response,
                    semantic_comparable=True,
                    checkpoint=checkpoint,
                )
            ]
            initial_record = None
            if persist_all_frames:
                initial_record = mismatch_record(
                    case_name=tape_spec["name"],
                    artifact_dir=artifact_dir,
                    vblank=0,
                    button=None,
                    rust_rgb=rust_initial,
                    source_rgb=source_initial,
                    rust_readout=rust_initial_readout,
                    source_response=source_initial_response,
                    semantic_comparable=True,
                    checkpoint=checkpoint,
                )
            if rust_initial != source_initial or not initial_semantic_equal:
                first_mismatch = initial_record or mismatch_record(
                    case_name=tape_spec["name"],
                    artifact_dir=artifact_dir,
                    vblank=0,
                    button=None,
                    rust_rgb=rust_initial,
                    source_rgb=source_initial,
                    rust_readout=rust_initial_readout,
                    source_response=source_initial_response,
                    semantic_comparable=True,
                    checkpoint=checkpoint,
                )
            semantic_boundaries = set(tape_spec["semantic_boundaries"])
            rust_rgb = rust_initial
            source_rgb = source_initial
            rust_readout = rust_initial_readout
            source_response = source_initial_response
            for frame_index, button in enumerate(tape_spec["tape"], start=1):
                service.submit(rollout_id, button, 1)
                rust_rgb = service.frame(rollout_id)
                rust_readout = service.readout(rollout_id)
                if rust_readout.get("frame_index") != frame_index:
                    raise HarnessError(
                        "Rust rollout frame_index did not advance exactly one VBlank"
                    )
                source_rgb, source_response = oracle.step(
                    [] if button == "noop" else [button]
                )
                compared_source_frames += 1
                pixels_equal = rust_rgb == source_rgb
                semantic_comparable = frame_index in semantic_boundaries
                semantic_equal = (
                    rust_semantic_view(rust_readout)
                    == source_semantic_view(source_response, checkpoint)
                    if semantic_comparable
                    else None
                )
                pixel_mismatch_frames += int(not pixels_equal)
                semantic_boundary_mismatches += int(semantic_equal is False)
                proof_tape.append(
                    trace_tick(
                        vblank=frame_index,
                        button=button,
                        rust_rgb=rust_rgb,
                        source_rgb=source_rgb,
                        rust_readout=rust_readout,
                        source_response=source_response,
                        semantic_comparable=semantic_comparable,
                        checkpoint=checkpoint,
                    )
                )
                frame_record = None
                if persist_all_frames:
                    frame_record = mismatch_record(
                        case_name=tape_spec["name"],
                        artifact_dir=artifact_dir,
                        vblank=frame_index,
                        button=button,
                        rust_rgb=rust_rgb,
                        source_rgb=source_rgb,
                        rust_readout=rust_readout,
                        source_response=source_response,
                        semantic_comparable=semantic_comparable,
                        checkpoint=checkpoint,
                    )
                if first_mismatch is None and (
                    not pixels_equal or semantic_equal is False
                ):
                    first_mismatch = frame_record or mismatch_record(
                        case_name=tape_spec["name"],
                        artifact_dir=artifact_dir,
                        vblank=frame_index,
                        button=button,
                        rust_rgb=rust_rgb,
                        source_rgb=source_rgb,
                        rust_readout=rust_readout,
                        source_response=source_response,
                        semantic_comparable=semantic_comparable,
                        checkpoint=checkpoint,
                    )

            final_vblank = len(tape_spec["tape"])
            final_semantic_comparable = (
                final_vblank == 0 or final_vblank in semantic_boundaries
            )
            final_semantic_equal = (
                rust_semantic_view(rust_readout)
                == source_semantic_view(source_response, checkpoint)
                if final_semantic_comparable
                else None
            )
            final_diverged = rust_rgb != source_rgb or final_semantic_equal is False
            if final_diverged:
                if (
                    first_mismatch is not None
                    and first_mismatch["vblank"] == final_vblank
                ):
                    final_comparison = first_mismatch
                else:
                    final_comparison = mismatch_record(
                        case_name=tape_spec["name"],
                        artifact_dir=artifact_dir,
                        vblank=final_vblank,
                        button=tape_spec["tape"][-1] if tape_spec["tape"] else None,
                        rust_rgb=rust_rgb,
                        source_rgb=source_rgb,
                        rust_readout=rust_readout,
                        source_response=source_response,
                        semantic_comparable=final_semantic_comparable,
                        checkpoint=checkpoint,
                        persist_frames=not persist_all_frames,
                    )
            else:
                final_comparison = mismatch_record(
                    case_name=tape_spec["name"],
                    artifact_dir=artifact_dir,
                    vblank=final_vblank,
                    button=tape_spec["tape"][-1] if tape_spec["tape"] else None,
                    rust_rgb=rust_rgb,
                    source_rgb=source_rgb,
                    rust_readout=rust_readout,
                    source_response=source_response,
                    semantic_comparable=final_semantic_comparable,
                    checkpoint=checkpoint,
                    persist_frames=False,
                )
            cases.append(
                {
                    "case": case_index,
                    **tape_spec,
                    "initial_rgb_sha256": source_initial_sha256,
                    "compared_source_frames": compared_source_frames,
                    "pixel_mismatch_frames": pixel_mismatch_frames,
                    "semantic_boundary_mismatches": semantic_boundary_mismatches,
                    "proof_tape_sha256": sha256(
                        canonical_json(proof_tape).encode("utf-8")
                    ),
                    "proof_tape": proof_tape,
                    "first_mismatch": first_mismatch,
                    "final_comparison": final_comparison,
                    "result": "exact" if first_mismatch is None else "divergence",
                }
            )
        minimized_cases: list[dict[str, Any]] = []
        if minimize_mismatches != "none":
            if minimize_limit < 1:
                raise HarnessError("--minimize-limit must be positive when minimisation is enabled")
            identity = {
                "rom_sha256": rom_sha256,
                "state_sha256": state_sha256,
                "oracle_registry_sha256": file_sha256(ORACLE_REGISTRY_PATH),
                "oracle_checkpoint": checkpoint.checkpoint_id,
                "emulator": oracle.emulator,
                "config": oracle.config,
                "initial_rgb_sha256": source["initial_rgb_sha256"],
            }
            for case in cases:
                if len(minimized_cases) >= minimize_limit:
                    break
                # The full primary run remains the authoritative failure count.
                # The fresh replay in minimise_case verifies the chosen target
                # before it emits any artifact.
                if case["result"] != "exact":
                    result = minimise_case(
                        service=service,
                        oracle=oracle,
                        tape_spec=case,
                        selected=minimize_mismatches,
                        artifact_dir=artifact_dir,
                        identity=identity,
                        checkpoint=checkpoint,
                        max_replays=minimize_max_replays,
                        ppu_capture_root=ppu_capture_root,
                        ppu_rom=rom_path,
                        ppu_state=state_path,
                    )
                    if result["status"] == "reproduced":
                        minimized_cases.append({"case": case["name"], **result})
    finally:
        if oracle is not None:
            oracle.close()
        if service is not None:
            service.close()
    divergences = [case for case in cases if case["first_mismatch"] is not None]
    if not cases or sum(case["compared_source_frames"] for case in cases) == 0:
        raise HarnessError("oracle lane compared zero source frames")
    pixel_divergences = [
        case for case in divergences if case["pixel_mismatch_frames"] > 0
    ]
    semantic_divergences = [
        case
        for case in divergences
        if case["semantic_boundary_mismatches"] > 0
        or case["first_mismatch"]["semantic_equal"] is False
    ]
    assert oracle is not None
    return {
        "lane": "source_behavior_oracle",
        "seed": seed,
        "rom_path": str(rom_path),
        "rom_sha256": rom_sha256,
        "state_path": str(state_path),
        "state_sha256": state_sha256,
        "oracle_checkpoint": checkpoint.checkpoint_id,
        "coverage_segment": segment,
        "rust_checkpoint": checkpoint.rust_checkpoint,
        "adapter_command": command,
        "oracle_manifest_path": str(ORACLE_MANIFEST_PATH),
        "oracle_manifest_sha256": file_sha256(ORACLE_MANIFEST_PATH),
        "oracle_registry_path": str(ORACLE_REGISTRY_PATH),
        "oracle_registry_sha256": file_sha256(ORACLE_REGISTRY_PATH),
        "emulator": oracle.emulator,
        "emulator_config": oracle.config,
        "pixel_comparison": {
            "frame_width": 240,
            "frame_height": 160,
            "pixel_format": "RGB888",
            "tolerance": 0,
            "cadence": "every VBlank",
            "reports_first_divergence": True,
            "replays_full_tape_after_first_divergence": True,
            "semantic_comparison": "initial state and task action boundaries",
        },
        "minimization": {
            "schema": "gamebench.pokemon_emerald.minimization_summary.v1",
            "selected": minimize_mismatches,
            "limit": minimize_limit if minimize_mismatches != "none" else 0,
            "max_replays_per_proof": minimize_max_replays if minimize_mismatches != "none" else 0,
            "proofs": minimized_cases,
        },
        "mismatch_artifact_dir": str(artifact_dir) if divergences else None,
        "case_count": len(cases),
        "compared_source_frames": sum(
            case["compared_source_frames"] for case in cases
        ),
        "divergence_count": len(divergences),
        "pixel_divergence_count": len(pixel_divergences),
        "semantic_divergence_count": len(semantic_divergences),
        "pixel_mismatch_frames": sum(
            case["pixel_mismatch_frames"] for case in cases
        ),
        "semantic_boundary_mismatches": sum(
            case["semantic_boundary_mismatches"] for case in cases
        ),
        "result": "exact" if not divergences else "divergences_found",
        "cases": cases,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    if path.exists():
        raise HarnessError(f"refusing to overwrite existing report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("rust", "oracle", "both"), default="both")
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--random-cases", type=int, default=16)
    parser.add_argument("--steps", type=int, default=64, help="VBlanks per oracle tape")
    parser.add_argument(
        "--segment",
        choices=(
            "bedroom",
            "mays_house_exit",
            "clock_tv",
            "littleroot_exterior",
            "littleroot_field",
            "route101",
            "route101_wild_battle",
            "starter_picker",
            "starter_battle",
        ),
        default="bedroom",
        help="source corpus to replay; bedroom is the frozen default gate",
    )
    parser.add_argument("--output", type=Path, help="new JSON report path")
    parser.add_argument("--oracle-rom", type=Path, default=None)
    parser.add_argument("--oracle-state", type=Path, default=None)
    parser.add_argument(
        "--oracle-checkpoint",
        type=str,
        default=None,
        help="named authenticated source boundary from fixtures/gold/oracle_registry.json",
    )
    parser.add_argument(
        "--capture-minimized-ppu-dir",
        type=Path,
        help="opt-in external root for one authenticated full-PPU receipt per minimized failure",
    )
    parser.add_argument("--oracle-command", type=str, default=None)
    parser.add_argument(
        "--minimize-mismatches",
        choices=("none", "pixel", "semantic"),
        default="none",
        help="opt-in delta debugging of up to --minimize-limit failing oracle tapes",
    )
    parser.add_argument(
        "--minimize-limit",
        type=int,
        default=3,
        help="maximum minimized oracle proofs to emit (only used when enabled)",
    )
    parser.add_argument(
        "--minimize-max-replays",
        type=int,
        default=64,
        help="bounded fresh replays per proof; a capped search remains a valid proof",
    )
    parser.add_argument("--print-oracle-protocol", action="store_true")
    args = parser.parse_args()
    if args.random_cases < 0:
        parser.error("--random-cases must be non-negative")
    if args.steps < 1 or args.steps > 1_000:
        parser.error("--steps must be between 1 and 1000")
    if args.minimize_limit < 1:
        parser.error("--minimize-limit must be positive")
    if args.minimize_max_replays < 2:
        parser.error("--minimize-max-replays must be at least 2")
    if not args.print_oracle_protocol and args.output is None:
        parser.error("--output is required")
    return args


def main() -> int:
    args = parse_args()
    if args.print_oracle_protocol:
        print(ORACLE_PROTOCOL, end="")
        return 0
    assert args.output is not None
    if args.output.exists():
        print(f"error: refusing to overwrite existing report: {args.output}", file=sys.stderr)
        return 2
    report: dict[str, Any] = {
        "schema_version": 3,
        "harness": "fuzz_emerald_differential.py",
        "seed": args.seed,
        "mode": args.mode,
        "minimize_mismatches": args.minimize_mismatches,
        "lanes": [],
    }
    has_violations = False
    preflight_failed = False
    try:
        if args.mode in ("rust", "both"):
            rust_report = run_rust_transport_fuzz(args.seed, args.random_cases)
            report["lanes"].append(rust_report)
            has_violations |= rust_report["result"] != "pass"
        if args.mode in ("oracle", "both"):
            registry, checkpoint = load_oracle_checkpoint(args.oracle_checkpoint)
            rom_path = args.oracle_rom or Path(os.environ.get("EMERALD_ORACLE_ROM", DEFAULT_ORACLE_ROM))
            state_path = args.oracle_state or (
                Path(os.environ["EMERALD_ORACLE_STATE"])
                if "EMERALD_ORACLE_STATE" in os.environ
                else None
            )
            problems = oracle_preflight(
                rom_path, state_path, args.oracle_command, checkpoint, registry
            )
            if problems:
                source_identity: dict[str, str] = {"rom_path": str(rom_path)}
                if rom_path.is_file():
                    source_identity["rom_sha256"] = file_sha256(rom_path)
                if state_path is not None:
                    source_identity["state_path"] = str(state_path)
                    if state_path.is_file():
                        source_identity["state_sha256"] = file_sha256(state_path)
                report["lanes"].append(
                    {
                        "lane": "source_behavior_oracle",
                        "result": "preflight_failed",
                        "oracle_checkpoint": checkpoint.checkpoint_id,
                        "problems": problems,
                        "source_identity": source_identity,
                        "required_protocol": "Use --print-oracle-protocol for the strict JSONL contract.",
                    }
                )
                preflight_failed = True
            else:
                assert state_path is not None and args.oracle_command is not None
                oracle_report = run_oracle_pixel_fuzz(
                    args.seed,
                    args.random_cases,
                    args.steps,
                    rom_path,
                    state_path,
                    args.oracle_command,
                    args.output.parent / f"{args.output.stem}-artifacts",
                    registry,
                    checkpoint,
                    args.minimize_mismatches,
                    args.minimize_limit,
                    args.minimize_max_replays,
                    args.capture_minimized_ppu_dir,
                    args.segment,
                )
                report["lanes"].append(oracle_report)
                has_violations |= oracle_report["result"] != "exact"
    except HarnessError as exc:
        report["fatal_error"] = str(exc)
        write_report(args.output, report)
        print(f"wrote {args.output}\nerror: {exc}", file=sys.stderr)
        return 2
    write_report(args.output, report)
    print(f"wrote {args.output}")
    if preflight_failed:
        return 2
    return 1 if has_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
