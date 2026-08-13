#!/usr/bin/env python3
"""Fail-closed call-site RNG chronology for a trace-only NLE candidate.

The candidate must be built from the pinned source with a bounded in-memory
trace at the shared ISAAC ``RND`` primitive.  Each event carries its raw
draw, bound, and a semantic caller return address (``rn2`` or ``rnd``), so a
``rnd()`` call is attributed to its real source call site rather than to
``rnd.c``.  This harness compares the candidate to the exact wheel before a
trace can be reported.  It does not expose events to gold or scoring.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import OBSERVATION_KEYS, deterministic_nle_seeds, normalise_reset, project
from scripts.instrumented_oracle_gate import PINNED_BINARY_SHA256, PINNED_SOURCE_COMMIT, SCHEMA, evaluate
from scripts.nle_rng_state import EXPECTED_CONTEXT_SIZE, EXPECTED_ENTRY_SIZE, EXPECTED_STATE_OFFSET, PinnedNleRngReader, RngEntry, RngSnapshot


YOU_SCALAR_RANGES = ((0, 2000), (2232, 2392))  # pinned struct you; excludes pointer-bearing tail
WALL_DIRECTIONS = (("N", 0, -1), ("E", 1, 0), ("S", 0, 1), ("W", -1, 0))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_patch_bytes(value: bytes) -> bytes:
    """Ignore git's configurable abbreviated object IDs, not patch content."""
    return re.sub(rb"^index [^\n]+$", b"index <normalized>", value, flags=re.MULTILINE)


def source_call_site_id(atos_output: str, call_kind: int) -> str:
    match = re.search(r"\(([^()]+\.c):(\d+)\)$", atos_output)
    if not match or call_kind not in (1, 2):
        raise RuntimeError(f"unmapped trace call site: {atos_output}")
    return f"{Path(match.group(1)).name}:{match.group(2)}:{'rn2' if call_kind == 1 else 'rnd'}"


def offsets(path: Path, names: set[str]) -> dict[str, int]:
    pattern = re.compile(r"^([0-9A-Fa-f]+)\s+\w\s+_(" + "|".join(sorted(names)) + r")$")
    rows = subprocess.run(["nm", "-a", str(path)], check=True, text=True, stdout=subprocess.PIPE).stdout.splitlines()
    found = {match.group(2): int(match.group(1), 16) for row in rows if (match := pattern.match(row))}
    if set(found) != names:
        raise RuntimeError(f"missing trace/runtime symbols: {sorted(names - set(found))}")
    return found


class NativeBoundary:
    """Read-only scalar source boundary usable for wheel/candidate comparison."""

    def __init__(self, dlpath: Path):
        self.path = dlpath
        self.lib = ctypes.CDLL(str(dlpath))
        names = {"rn2", "moves", "monstermoves", "u", "rnglist"}
        self.offsets = offsets(dlpath, names)
        base = int(ctypes.cast(self.lib.rn2, ctypes.c_void_p).value or 0) - self.offsets["rn2"]
        if base <= 0:
            raise RuntimeError("invalid native ASLR base")
        self.base = base
        self.entries = (RngEntry * 2).from_address(base + self.offsets["rnglist"])
        if ctypes.sizeof(RngEntry) != EXPECTED_ENTRY_SIZE or RngEntry.state.offset != EXPECTED_STATE_OFFSET:
            raise RuntimeError("pinned RNG layout mismatch")

    def snapshot(self) -> dict[str, Any]:
        u_address = self.base + self.offsets["u"]
        scalars = b"".join(ctypes.string_at(u_address + start, end - start) for start, end in YOU_SCALAR_RANGES)
        return {
            "moves": ctypes.c_long.from_address(self.base + self.offsets["moves"]).value,
            "monstermoves": ctypes.c_long.from_address(self.base + self.offsets["monstermoves"]).value,
            "player_scalar_sha256": hashlib.sha256(scalars).hexdigest(),
            "core_rng_hex": ctypes.string_at(ctypes.addressof(self.entries[0].state), EXPECTED_CONTEXT_SIZE).hex(),
            "display_rng_hex": ctypes.string_at(ctypes.addressof(self.entries[1].state), EXPECTED_CONTEXT_SIZE).hex(),
            "core_rng_n": int(self.entries[0].state.n),
            "display_rng_n": int(self.entries[1].state.n),
        }


class TraceReader:
    def __init__(self, boundary: NativeBoundary, build: Path):
        self.boundary, self.build = boundary, build
        lib = boundary.lib
        for name in ("nle_rng_trace_reset", "nle_rng_trace_count", "nle_rng_trace_overflow", "nle_rng_trace_get"):
            if not hasattr(lib, name):
                raise RuntimeError("candidate does not expose the required trace ABI")
        lib.nle_rng_trace_count.restype = ctypes.c_uint
        lib.nle_rng_trace_overflow.restype = ctypes.c_uint8
        lib.nle_rng_trace_get.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint)]
        lib.nle_rng_trace_get.restype = ctypes.c_uint8

    def reset(self) -> None:
        self.boundary.lib.nle_rng_trace_reset()

    def events(self) -> list[dict[str, Any]]:
        if self.boundary.lib.nle_rng_trace_overflow():
            raise RuntimeError("trace overflow")
        count = int(self.boundary.lib.nle_rng_trace_count())
        if count <= 0:
            raise RuntimeError("zero trace events")
        result = []
        for index in range(count):
            raw, semantic, bound, value, kind = ctypes.c_uint64(), ctypes.c_uint64(), ctypes.c_int(), ctypes.c_int(), ctypes.c_uint()
            if not self.boundary.lib.nle_rng_trace_get(index, ctypes.byref(raw), ctypes.byref(semantic), ctypes.byref(bound), ctypes.byref(value), ctypes.byref(kind)):
                raise RuntimeError("unmatched trace event")
            offset = int(semantic.value) - self.boundary.base
            if offset <= 0 or kind.value not in (1, 2) or not (0 <= value.value < bound.value):
                raise RuntimeError("invalid trace event bounds/caller/value")
            source = subprocess.run(["atos", "-o", str(self.build), "-arch", "arm64", hex(offset)], check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
            result.append({"ordinal": index, "call_site_id": source_call_site_id(source, kind.value), "bound": bound.value, "value": value.value})
        return result


def action_ids(env: Any) -> dict[str, int]:
    return {f"{action.__class__.__name__}.{action.name}": index for index, action in enumerate(env.actions)}


def run_case(seed: int, *, instrumented: Path | None) -> dict[str, Any]:
    import nle
    from nle import nethack
    from nle.nethack import nethack as nethack_module

    original = nethack_module.DLPATH
    if instrumented is not None:
        nethack_module.DLPATH = str(instrumented)
    env = nle.env.NLE(character="Agent-val-hum-neu-fem", observation_keys=OBSERVATION_KEYS, actions=tuple(nethack.ACTIONS), allow_all_modes=True, allow_all_yn_questions=True)
    try:
        core, display = deterministic_nle_seeds(seed)
        env.seed(core=core, disp=display, reseed=False)
        reset = project(normalise_reset(env.reset()))
        x, y = int(reset["blstats"][0]), int(reset["blstats"][1])
        direction = next((name for name, dx, dy in WALL_DIRECTIONS if chr(int(reset["chars"][y + dy][x + dx])) in "|-"), None)
        if direction is None:
            raise RuntimeError(f"seed {seed}: no reset-visible wall KICK target")
        boundary = NativeBoundary(Path(env.nethack.dlpath))
        wheel_rng = PinnedNleRngReader(env.nethack) if instrumented is None else None
        before = boundary.snapshot()
        ids = action_ids(env)
        prompt = project(normalise_reset(env.step(ids["Command.KICK"])[0]))
        after_prompt = boundary.snapshot()
        trace = TraceReader(boundary, instrumented) if instrumented is not None else None
        if trace:
            trace.reset()
        result = project(normalise_reset(env.step(ids[f"CompassDirection.{direction}"])[0]))
        after_result = boundary.snapshot()
        events = trace.events() if trace else []
        exact_draws = wheel_rng.exact_call_count(  # source wheel only; candidate equality below makes it a control
            RngSnapshot(bytes.fromhex(after_prompt["core_rng_hex"]), bytes.fromhex(after_prompt["display_rng_hex"]), after_prompt["core_rng_n"], after_prompt["display_rng_n"], wheel_rng._binary_sha256),
            RngSnapshot(bytes.fromhex(after_result["core_rng_hex"]), bytes.fromhex(after_result["display_rng_hex"]), after_result["core_rng_n"], after_result["display_rng_n"], wheel_rng._binary_sha256),
            "core",
        ) if wheel_rng else None
        return {"seed": seed, "direction": direction, "public": {"reset": reset, "prompt": prompt, "result": result}, "native": {"before": before, "after_prompt": after_prompt, "after_result": after_result}, "trace_events": events, "wheel_exact_core_draws": exact_draws}
    finally:
        env.close()
        nethack_module.DLPATH = original


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instrumented-lib", required=True, type=Path)
    parser.add_argument("--instrumented-source", required=True, type=Path)
    parser.add_argument("--trace-patch", required=True, type=Path)
    parser.add_argument("--seeds", nargs="+", type=int, default=[20260725, 20260726, 20260727])
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if not args.instrumented_lib.is_file() or not (args.instrumented_source / "src" / "rnd.c").is_file() or not args.trace_patch.is_file() or len(args.seeds) < 3:
        raise SystemExit("instrumented library/source/patch and at least three heldout seeds are required")
    source_commit = subprocess.run(["git", "-C", str(args.instrumented_source), "rev-parse", "HEAD"], check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    if source_commit != PINNED_SOURCE_COMMIT:
        raise SystemExit("instrumented source does not resolve to the pinned NLE commit")
    actual_patch = subprocess.run(["git", "-C", str(args.instrumented_source), "diff", "--", "src/rnd.c"], check=True, stdout=subprocess.PIPE).stdout
    expected_patch = args.trace_patch.read_bytes()
    if hashlib.sha256(normalized_patch_bytes(actual_patch)).digest() != hashlib.sha256(normalized_patch_bytes(expected_patch)).digest():
        raise SystemExit("instrumented rnd.c diff does not exactly match the supplied trace patch")
    baseline = [run_case(seed, instrumented=None) for seed in args.seeds]
    first = [run_case(seed, instrumented=args.instrumented_lib) for seed in args.seeds]
    second = [run_case(seed, instrumented=args.instrumented_lib) for seed in args.seeds]
    public_mismatches = sum(base["public"] != candidate["public"] for base, candidate in zip(baseline, first, strict=True))
    native_mismatches = sum(base["native"] != candidate["native"] for base, candidate in zip(baseline, first, strict=True))
    replay_mismatches = sum(left != right for left, right in zip(first, second, strict=True))
    for base, candidate in zip(baseline, first, strict=True):
        if len(candidate["trace_events"]) != base["wheel_exact_core_draws"]:
            raise RuntimeError(f"seed {base['seed']}: trace count does not equal exact wheel draw count")
        if not any(event["call_site_id"] == "dokick.c:1241:rn2" for event in candidate["trace_events"]):
            raise RuntimeError(f"seed {base['seed']}: reset-wall KICK decision call site absent")
    candidate = {"schema": SCHEMA, "identity": {"source_commit": source_commit, "baseline_binary_sha256": PINNED_BINARY_SHA256, "instrumented_binary_sha256": sha256_file(args.instrumented_lib), "toolchain_identity_sha256": hashlib.sha256((subprocess.run(["clang", "--version"], text=True, stdout=subprocess.PIPE).stdout + sys.version).encode()).hexdigest(), "patch_sha256": sha256_file(args.trace_patch)}, "controls": {"independent_seed_count": len(args.seeds), "transition_count": len(first), "trace_event_count": sum(len(case["trace_events"]) for case in first), "public_observation_mismatch_count": public_mismatches, "native_boundary_mismatch_count": native_mismatches, "final_rng_state_mismatch_count": sum(base["native"]["after_result"]["core_rng_hex"] != current["native"]["after_result"]["core_rng_hex"] or base["native"]["after_result"]["display_rng_hex"] != current["native"]["after_result"]["display_rng_hex"] for base, current in zip(baseline, first, strict=True)), "trace_replay_mismatch_count": replay_mismatches, "two_independent_runs_exact": replay_mismatches == 0}, "validity": {"inputs_selected_before_results": True, "trace_read_only_from_gold_perspective": True, "trace_excluded_from_gold_runtime": True, "trace_excluded_from_conformance_denominator": True, "zero_and_unmatched_events_fail_closed": True}, "instrumented_source_oracle_eligible": False, "kick_cases": first}
    # Ask the gate whether the evidence is otherwise complete, then bind the
    # claim to that result and evaluate once more so a false self-claim can
    # never pass by accident.
    candidate["instrumented_source_oracle_eligible"] = True
    result = evaluate(candidate)
    candidate["instrumented_source_oracle_eligible"] = result["instrumented_source_oracle_eligible"]
    candidate["gate"] = evaluate(candidate)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"report": str(args.report.resolve()), "eligible": candidate["gate"]["instrumented_source_oracle_eligible"], "failures": candidate["gate"]["failures"]}, sort_keys=True))
    raise SystemExit(0 if candidate["gate"]["instrumented_source_oracle_eligible"] else 1)


if __name__ == "__main__":
    main()
