#!/usr/bin/env python3
"""Export a bounded, concrete candidate tape from the committed May replay.

The historical title-to-MetRival replay is a useful *search seed*, not source
evidence.  This exporter makes a chosen flat-step interval inspectable and
replayable by the mGBA capture command while preserving its exact upstream
replay digest.  The output explicitly remains ``candidate_unvalidated`` until
the capture command writes a live source trace and reload receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


TASK_ROOT = Path(__file__).resolve().parents[1]
if str(TASK_ROOT) not in sys.path:
    sys.path.insert(0, str(TASK_ROOT))

from shared.opening_tape import BEDROOM_CLOCK_TAPE_INDEX, REPLAY_PATH, may_opening_steps  # noqa: E402


BUTTONS = {"a", "b", "select", "start", "right", "left", "up", "down", "r", "l"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def concrete_steps(start: int, end: int) -> list[dict[str, Any]]:
    steps = may_opening_steps()
    if not 0 <= start < end <= len(steps):
        raise ValueError(f"invalid flat-step interval [{start}, {end}); replay has {len(steps)} steps")
    output: list[dict[str, Any]] = []
    for index, step in enumerate(steps[start:end], start=start):
        action = step["action"]
        frames = step["frames"]
        if action == "noop":
            buttons: list[str] = []
        elif action in BUTTONS:
            buttons = [action]
        else:
            raise ValueError(f"unsupported opening action at flat step {index}: {action!r}")
        if not isinstance(frames, int) or frames < 1:
            raise ValueError(f"invalid opening frames at flat step {index}")
        output.append({"buttons": buttons, "frames": frames, "opening_flat_step": index})
    return output


def build_candidate(
    start: int, end: int, checkpoint: str, candidate_id: str, coverage_segment: str | None
) -> dict[str, Any]:
    program = concrete_steps(start, end)
    result = {
        "schema": "gamebench.pokemon_emerald.concrete_capture_tape.v1",
        "id": candidate_id,
        "checkpoint": checkpoint,
        "status": "candidate_unvalidated",
        "purpose": "deterministic mGBA story-route search seed; requires a live trace and reload receipt",
        "candidate_provenance": {
            "source": "fixtures/gold/replays/title_to_met_rival_may.json",
            "source_sha256": file_sha256(REPLAY_PATH),
            "flat_step_interval": {"start_inclusive": start, "end_exclusive": end},
            "bedroom_clock_flat_step": BEDROOM_CLOCK_TAPE_INDEX,
        },
        "program": program,
        "expected_evidence": {
            "minimum": ["per-VBlank source trace", "snapshot SHA-256", "fresh reload receipt"],
            "forbidden_inference": ["Rust terminal world state", "frozen frame", "candidate program alone"],
        },
    }
    if coverage_segment:
        result["coverage_segment"] = coverage_segment
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="bedroom_idle")
    parser.add_argument("--start-index", type=int, default=BEDROOM_CLOCK_TAPE_INDEX)
    parser.add_argument("--end-index", type=int, help="exclusive flat-step end; defaults to replay end")
    parser.add_argument("--id", default="bedroom_clock_to_met_rival_may_candidate")
    parser.add_argument("--coverage-segment", help="declared route segment; validated dashboard label only")
    parser.add_argument("--output", type=Path, required=True, help="new JSON output path")
    args = parser.parse_args()
    if args.output.exists():
        print(f"refusing to overwrite candidate output: {args.output}", file=sys.stderr)
        return 2
    end = args.end_index if args.end_index is not None else len(may_opening_steps())
    try:
        candidate = build_candidate(args.start_index, end, args.checkpoint, args.id, args.coverage_segment)
    except ValueError as exc:
        print(f"candidate export failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    total_frames = sum(segment["frames"] for segment in candidate["program"])
    print(json.dumps({"status": "candidate_unvalidated", "output": str(args.output), "flat_steps": len(candidate["program"]), "vblanks": total_frames}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
