#!/usr/bin/env python3
"""Verify the portable Algorithm-C ``COULD_SEE`` implementation against NLE.

This is a source-only validity check.  It captures a reset snapshot from the
pinned NLE 0.9.0 wheel, supplies only reset terrain/flags plus the explicitly
exported boulder/mimic blocker coordinates to the own Python implementation,
and compares every 21x79 ``COULD_SEE`` bit.  It never writes a task, invokes a
gold lane, or treats the result as public ``IN_SIGHT``/lighting parity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.nethack_fov import could_see  # noqa: E402
from scripts.capture_nle_fixture import deterministic_nle_seeds, normalise_reset  # noqa: E402
from scripts.nle_native_map_fov import OBS_COLNO, PINNED_BINARY_SHA256, ROWNO, PinnedNleMapFovReader  # noqa: E402


SCHEMA = "gamebench.nethack.algorithm_c_fov_source_verifier.v1"
SOURCE_REFERENCES = {
    "algorithm": "src/vision.c:2643-2754 (view_from Algorithm C)",
    "path": "src/vision.c:1136-1558 (q1_path/q2_path/q3_path/q4_path)",
    "rows": "src/vision.c:186-242 (vision_reset row pointers and viz_clear)",
    "blockers": "src/vision.c:150-181 (does_block static terrain plus boulder/mimic inputs)",
}


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_seed(seed: int, *, character: str) -> dict[str, Any]:
    import nle
    from nle import nethack

    env = nle.env.NLE(
        character=character,
        observation_keys=("chars", "glyphs", "colors", "blstats", "message", "inv_glyphs", "inv_strs", "inv_letters", "inv_oclasses"),
        actions=tuple(nethack.ACTIONS),
        max_episode_steps=100,
        allow_all_modes=True,
        allow_all_yn_questions=True,
    )
    try:
        core, display = deterministic_nle_seeds(seed)
        configured = tuple(int(value) for value in env.seed(core=core, disp=display, reseed=False))
        if configured != (core, display, False):
            raise RuntimeError("NLE declined pinned seed configuration")
        normalise_reset(env.reset())
        reader = PinnedNleMapFovReader(env.nethack)
        export = reader.snapshot().public_record()
        hero = export["vision_decision_inputs"]["hero"]
        blockers = [
            (int(record["x"]), int(record["y"]))
            for record in export["dynamic_vision_blockers"]["records"]
            if record.get("kind") in {"boulder", "mimic"}
        ]
        predicted = could_see(
            export["full_map_terrain"],
            export["full_map_terrain_flags"],
            int(hero["native_x"]) - 1,
            int(hero["native_y"]),
            dynamic_blockers=blockers,
        )
        expected = export["fov_could_see_mask"]
        mismatches = [
            {"x": x, "y": y, "predicted": bool(predicted[y][x]), "expected": bool(expected[y][x])}
            for y in range(ROWNO)
            for x in range(OBS_COLNO)
            if bool(predicted[y][x]) != bool(expected[y][x])
        ]
        return {
            "seed": int(seed),
            "configured_seeds": list(configured),
            "hero": {"x": int(hero["native_x"]) - 1, "y": int(hero["native_y"])},
            "dynamic_blocker_count": len(blockers),
            "comparisons": ROWNO * OBS_COLNO,
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
            "native_plane_sha256": export["plane_sha256"],
        }
    finally:
        env.close()


def verify(seeds: list[int], *, character: str) -> dict[str, Any]:
    if len(seeds) < 3 or len(set(seeds)) != len(seeds):
        raise ValueError("Algorithm-C source verification requires at least three distinct seeds")
    records = [verify_seed(seed, character=character) for seed in seeds]
    return {
        "schema": SCHEMA,
        "status": "pass" if all(record["mismatch_count"] == 0 for record in records) else "mismatch",
        "source_only": True,
        "gold_implementation_eligible": False,
        "binary_sha256": PINNED_BINARY_SHA256,
        "source_references": SOURCE_REFERENCES,
        "seeds": [int(seed) for seed in seeds],
        "algorithm_sha256": "sha256:" + hashlib.sha256(Path(TASK_DIR / "gold_python" / "nethack_fov.py").read_bytes()).hexdigest(),
        "comparison_count": sum(int(record["comparisons"]) for record in records),
        "mismatch_count": sum(int(record["mismatch_count"]) for record in records),
        "records": records,
        "validity": {
            "reset_source_only": True,
            "dynamic_blockers_explicit": True,
            "future_frame_input": False,
            "public_in_sight_or_lighting_claim": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(20260725, 20260731)))
    parser.add_argument("--character", default="val-hum-fem-law")
    parser.add_argument("--report", type=Path, default=TASK_DIR / "reports" / "algorithm-c-fov-source-verifier.json")
    args = parser.parse_args()
    report = verify([int(seed) for seed in args.seeds], character=str(args.character))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "comparisons": report["comparison_count"], "mismatches": report["mismatch_count"], "report": str(args.report)}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

