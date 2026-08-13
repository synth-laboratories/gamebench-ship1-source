#!/usr/bin/env python3
"""Verify a trace-only NLE build and record pet/object call chronology.

The candidate is rebuilt from the pinned NLE source with a bounded ledger at
``dog_invent``, ``dog_goal``, ``dogfood``, ``obj_resists``, and the
``dogmove.c:550`` apport draw.  This harness
first selects a fixed input tape, then runs the exact pinned wheel and the
instrumented candidate.  Public observations, native scalar/RNG boundaries,
and candidate replay must agree before the trace is accepted as source
evidence.  The trace is never passed to either gold lane or its denominator.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from scripts.capture_nle_fixture import (  # noqa: E402
    OBSERVATION_KEYS,
    deterministic_nle_seeds,
    normalise_reset,
    project,
)
from scripts.instrumented_oracle_gate import (  # noqa: E402
    PINNED_BINARY_SHA256,
    PINNED_SOURCE_COMMIT,
    SCHEMA,
    evaluate,
)
from scripts.verify_instrumented_kick_rng_trace import NativeBoundary  # noqa: E402


DEFAULT_ACTIONS = [
    1, 3, 0, 7, 4, 6, 3, 3, 0, 0, 6, 2, 3, 4, 3, 5,
    0, 4, 7, 4, 5, 6, 2, 6, 3, 3, 3, 2, 6, 7, 7, 5,
]
TRACE_KINDS = {
    1: "dog_invent",
    2: "dog_goal",
    3: "dogfood",
    4: "obj_resists",
    5: "dog_apport_rn2",
    6: "rndmonst_selection",
    7: "newmonhp",
    8: "rng_rn2",
    9: "rng_rnd",
}


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


class DogTraceEvent(ctypes.Structure):
    _fields_ = [
        ("kind", ctypes.c_uint32),
        ("entity_id", ctypes.c_uint32),
        ("object_id", ctypes.c_uint32),
        ("object_type", ctypes.c_int32),
        ("object_where", ctypes.c_int32),
        ("object_quantity", ctypes.c_int64),
        ("native_x", ctypes.c_int32),
        ("native_y", ctypes.c_int32),
        ("arg0", ctypes.c_int32),
        ("arg1", ctypes.c_int32),
        ("arg2", ctypes.c_int32),
        ("result", ctypes.c_int32),
        ("moves", ctypes.c_int64),
        ("monstermoves", ctypes.c_int64),
        ("hero_native_x", ctypes.c_int32),
        ("hero_native_y", ctypes.c_int32),
    ]


class DogTraceReader:
    def __init__(self, library_path: Path):
        self.lib = ctypes.CDLL(str(library_path))
        required = (
            "nle_dog_trace_reset",
            "nle_dog_trace_count",
            "nle_dog_trace_overflow",
            "nle_dog_trace_get",
        )
        if any(not hasattr(self.lib, name) for name in required):
            raise RuntimeError("candidate is missing the dog trace ABI")
        self.lib.nle_dog_trace_reset.restype = None
        self.lib.nle_dog_trace_count.restype = ctypes.c_uint32
        self.lib.nle_dog_trace_overflow.restype = ctypes.c_uint8
        self.lib.nle_dog_trace_get.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(DogTraceEvent),
        ]
        self.lib.nle_dog_trace_get.restype = ctypes.c_uint8

    def reset(self) -> None:
        self.lib.nle_dog_trace_reset()

    def events(self) -> list[dict[str, Any]]:
        if self.lib.nle_dog_trace_overflow():
            raise RuntimeError("dog trace overflow")
        count = int(self.lib.nle_dog_trace_count())
        events: list[dict[str, Any]] = []
        for index in range(count):
            event = DogTraceEvent()
            if not self.lib.nle_dog_trace_get(index, ctypes.byref(event)):
                raise RuntimeError(f"dog trace event {index} is unreadable")
            kind = int(event.kind)
            if kind not in TRACE_KINDS:
                raise RuntimeError(f"unknown dog trace kind {kind}")
            if kind in (1, 2, 3, 5, 7) and int(event.entity_id) <= 0:
                raise RuntimeError(f"trace kind {TRACE_KINDS[kind]} has no entity identity")
            if kind in (4, 5) and int(event.object_id) <= 0:
                raise RuntimeError(f"trace kind {TRACE_KINDS[kind]} has no object identity")
            events.append(
                {
                    "ordinal": index,
                    "kind": TRACE_KINDS[kind],
                    "kind_id": kind,
                    "entity_id": int(event.entity_id),
                    "object_id": int(event.object_id),
                    "object_type": int(event.object_type),
                    "object_where": int(event.object_where),
                    "object_quantity": int(event.object_quantity),
                    "native_xy": [int(event.native_x), int(event.native_y)],
                    "args": [int(event.arg0), int(event.arg1), int(event.arg2)],
                    "result": int(event.result),
                    "moves": int(event.moves),
                    "monstermoves": int(event.monstermoves),
                    "hero_native_xy": [int(event.hero_native_x), int(event.hero_native_y)],
                }
            )
        return events


def action_labels(action_ids: list[int], env: Any) -> list[str]:
    labels = []
    for action_id in action_ids:
        if not (0 <= action_id < len(env.actions)):
            raise ValueError(f"action id {action_id} is outside the pinned action table")
        action = env.actions[action_id]
        labels.append(f"{action.__class__.__name__}.{action.name}")
    return labels


def first_difference(left: list[Any], right: list[Any]) -> dict[str, Any] | None:
    if len(left) != len(right):
        return {"reason": "length", "left": len(left), "right": len(right)}
    for index, (a, b) in enumerate(zip(left, right, strict=True)):
        if a != b:
            return {"step": index, "left_sha256": sha256_json(a), "right_sha256": sha256_json(b)}
    return None


def run_case(
    seed: int,
    action_ids: list[int],
    *,
    instrumented: Path | None,
    character: str = "Agent-val-hum-neu-fem",
) -> dict[str, Any]:
    import nle
    from nle import nethack
    from nle.nethack import nethack as nethack_module

    original_dlpath = nethack_module.DLPATH
    if instrumented is not None:
        nethack_module.DLPATH = str(instrumented)
    env = nle.env.NLE(
        character=character,
        observation_keys=OBSERVATION_KEYS,
        actions=tuple(nethack.ACTIONS),
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    try:
        core_seed, display_seed = deterministic_nle_seeds(seed)
        env.seed(core=core_seed, disp=display_seed, reseed=False)
        reset_projection = project(normalise_reset(env.reset()))
        library_path = Path(env.nethack.dlpath)
        boundary = NativeBoundary(library_path)
        trace = DogTraceReader(library_path) if instrumented is not None else None
        labels = action_labels(action_ids, env)
        projections = [reset_projection]
        native = [boundary.snapshot()]
        trace_steps: list[list[dict[str, Any]]] = []
        consumed_actions: list[int] = []
        done = False
        for action_id in action_ids:
            if done:
                break
            if trace is not None:
                trace.reset()
            observation, _, done, _ = env.step(action_id)
            projections.append(project(normalise_reset(observation)))
            native.append(boundary.snapshot())
            consumed_actions.append(action_id)
            if trace is not None:
                trace_steps.append(trace.events())
        return {
            "seed": seed,
            "selected_action_ids": list(action_ids),
            "selected_action_names": labels,
            "consumed_action_ids": consumed_actions,
            "public": projections,
            "native": native,
            "trace_steps": trace_steps,
        }
    finally:
        env.close()
        nethack_module.DLPATH = original_dlpath


def compact_case(case: dict[str, Any], *, include_public: bool = False) -> dict[str, Any]:
    result = {
        "seed": case["seed"],
        "selected_action_ids": case["selected_action_ids"],
        "selected_action_names": case["selected_action_names"],
        "consumed_action_ids": case["consumed_action_ids"],
        "transition_count": len(case["public"]) - 1,
        "public_sha256": sha256_json(case["public"]),
        "native_sha256": sha256_json(case["native"]),
    }
    if "trace_steps" in case:
        result["trace_event_count"] = sum(len(step) for step in case["trace_steps"])
        result["trace_steps"] = case["trace_steps"]
    if include_public:
        result["public"] = case["public"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instrumented-lib", required=True, type=Path)
    parser.add_argument("--instrumented-source", required=True, type=Path)
    parser.add_argument("--trace-patch", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--seeds", nargs="+", type=int, default=[20260725, 20260726, 20260727])
    parser.add_argument("--actions", nargs="+", type=int, default=DEFAULT_ACTIONS)
    parser.add_argument("--include-public", action="store_true")
    parser.add_argument(
        "--character",
        default="Agent-val-hum-neu-fem",
        help="pinned NLE character string; include it in the source-trace identity",
    )
    args = parser.parse_args()
    if len(args.seeds) < 3 or not args.actions:
        raise SystemExit("at least three independent seeds and one preselected action are required")
    if not args.instrumented_lib.is_file() or not args.trace_patch.is_file():
        raise SystemExit("instrumented library and exact trace patch are required")
    source_commit = subprocess.run(
        ["git", "-C", str(args.instrumented_source), "rev-parse", "HEAD"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if source_commit != PINNED_SOURCE_COMMIT:
        raise SystemExit("instrumented source does not resolve to the pinned NLE commit")

    # Select and bind the input tape before any output is inspected.
    selected_actions = list(args.actions)
    baseline = [run_case(seed, selected_actions, instrumented=None, character=args.character) for seed in args.seeds]
    first = [run_case(seed, selected_actions, instrumented=args.instrumented_lib, character=args.character) for seed in args.seeds]
    second = [run_case(seed, selected_actions, instrumented=args.instrumented_lib, character=args.character) for seed in args.seeds]

    public_mismatches = 0
    native_mismatches = 0
    first_differences: list[dict[str, Any]] = []
    for base, candidate in zip(baseline, first, strict=True):
        public_diff = first_difference(base["public"], candidate["public"])
        native_diff = first_difference(base["native"], candidate["native"])
        if public_diff is not None:
            public_mismatches += 1
            first_differences.append({"seed": base["seed"], "plane": "public", **public_diff})
        if native_diff is not None:
            native_mismatches += 1
            first_differences.append({"seed": base["seed"], "plane": "native", **native_diff})

    replay_mismatches = 0
    for left, right in zip(first, second, strict=True):
        if left["public"] != right["public"] or left["native"] != right["native"] or left["trace_steps"] != right["trace_steps"]:
            replay_mismatches += 1

    final_rng_mismatches = sum(
        base["native"][-1] != candidate["native"][-1]
        for base, candidate in zip(baseline, first, strict=True)
    )
    trace_event_count = sum(
        len(events)
        for case in first
        for events in case["trace_steps"]
    )
    if trace_event_count <= 0:
        raise RuntimeError("zero dog trace events: source chronology was not observed")

    candidate = {
        "schema": SCHEMA,
        "identity": {
            "source_commit": source_commit,
            "baseline_binary_sha256": PINNED_BINARY_SHA256,
            "instrumented_binary_sha256": hashlib.sha256(args.instrumented_lib.read_bytes()).hexdigest(),
            "toolchain_identity_sha256": hashlib.sha256(
                (subprocess.run(["clang", "--version"], check=True, text=True, stdout=subprocess.PIPE).stdout + sys.version).encode()
            ).hexdigest(),
            "patch_sha256": hashlib.sha256(args.trace_patch.read_bytes()).hexdigest(),
        },
        "controls": {
            "independent_seed_count": len(args.seeds),
            "transition_count": sum(len(case["public"]) - 1 for case in first),
            "trace_event_count": trace_event_count,
            "public_observation_mismatch_count": public_mismatches,
            "native_boundary_mismatch_count": native_mismatches,
            "final_rng_state_mismatch_count": final_rng_mismatches,
            "trace_replay_mismatch_count": replay_mismatches,
            "two_independent_runs_exact": replay_mismatches == 0,
        },
        "validity": {
            "inputs_selected_before_results": True,
            "trace_read_only_from_gold_perspective": True,
            "trace_excluded_from_gold_runtime": True,
            "trace_excluded_from_conformance_denominator": True,
            "zero_and_unmatched_events_fail_closed": True,
            "public_observations_compared_exactly": True,
            "native_scalar_and_rng_boundaries_compared_exactly": True,
        },
        "input_tape": {
            "character": args.character,
            "action_ids": selected_actions,
            "action_ids_sha256": sha256_json(selected_actions),
            "seed_ids": list(args.seeds),
        },
        "instrumented_source_oracle_eligible": True,
        "first_differences": first_differences,
        "baseline_cases": [compact_case(case, include_public=args.include_public) for case in baseline],
        "instrumented_cases": [compact_case(case, include_public=args.include_public) for case in first],
    }
    initial_gate = evaluate(candidate)
    candidate["instrumented_source_oracle_eligible"] = initial_gate["instrumented_source_oracle_eligible"]
    candidate["gate"] = evaluate(candidate)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "report": str(args.report.resolve()),
                "eligible": candidate["gate"]["instrumented_source_oracle_eligible"],
                "trace_events": trace_event_count,
                "public_mismatches": public_mismatches,
                "native_mismatches": native_mismatches,
                "replay_mismatches": replay_mismatches,
                "failures": candidate["gate"]["failures"],
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if candidate["gate"]["instrumented_source_oracle_eligible"] else 1)


if __name__ == "__main__":
    main()
