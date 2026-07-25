#!/usr/bin/env python3
"""Run a FrogsGame gold service lane."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=["python", "rust"], default="python")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    port = args.port if args.port is not None else (8096 if args.lane == "python" else 8097)
    if args.lane == "python":
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "service:app",
            "--app-dir",
            str(TASK_DIR / "gold_python"),
            "--host",
            args.host,
            "--port",
            str(port),
        ]
    else:
        cmd = [
            "cargo",
            "run",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "frogs_gold",
            "--",
            "--host",
            args.host,
            "--port",
            str(port),
        ]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
