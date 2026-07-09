#!/usr/bin/env python3
"""Write a structured artifact when a single-harness model session never runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--source-task", required=True)
    parser.add_argument("--wall-seconds", type=int, required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()

    text = args.log.read_text(errors="replace")
    if "Insufficient Balance" in text:
        failure_class = "provider_balance"
        provider_status = 402
        detail = "Provider rejected the request before the first model response: Insufficient Balance."
    else:
        failure_class = "model_execution_failed"
        provider_status = None
        detail = "The Codex session exited before producing a crate."

    session = re.search(r"session id:\s*(\S+)", text)
    artifact = {
        "arm": "single_harness",
        "model": args.model,
        "source_task": args.source_task,
        "status": "not_scored",
        "failure_class": failure_class,
        "provider_status": provider_status,
        "detail": detail,
        "wall_seconds": args.wall_seconds,
        "codex_exit_code": args.exit_code,
        "codex_session_id": session.group(1) if session else None,
        "transcript_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "transcript_bytes": len(text.encode()),
    }
    args.out.write_text(json.dumps(artifact, indent=2) + "\n")
    print(args.out.read_text(), end="")


if __name__ == "__main__":
    main()
