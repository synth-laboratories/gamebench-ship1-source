#!/usr/bin/env python3
"""Write a stable receipt for one workflow-harness benchmark cell."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_score(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--source-task", required=True)
    parser.add_argument("--wall-seconds", type=int, required=True)
    parser.add_argument("--cap-seconds", type=int, required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--runner-revision", required=True)
    parser.add_argument("--jesterky-bin", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--score", type=Path, required=True)
    args = parser.parse_args()

    score = read_score(args.score)
    receipt = {
        "arm": "workflow",
        "model": args.model,
        "reasoning_effort": args.effort or None,
        "source_task": args.source_task,
        "wall_seconds": args.wall_seconds,
        "cap_seconds": args.cap_seconds,
        "capped": args.exit_code >= 128,
        "jesterky_exit_code": args.exit_code,
        "runner_revision": args.runner_revision,
        "jesterky_bin": args.jesterky_bin,
        "manifest_sha256": file_sha256(args.manifest),
        "score_sha256": file_sha256(args.score),
        "passed": score.get("passed"),
        "total": score.get("total"),
    }
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(args.out.read_text(), end="")


if __name__ == "__main__":
    main()
