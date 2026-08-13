#!/usr/bin/env python3
"""Launch the Rust HTTP adapter using the task's standard service wrapper."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("GAMEBENCH_SMB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    port = args.port or int(os.environ.get("GAMEBENCH_SMB_PORT", "8099"))
    command = [
        "cargo",
        "run",
        "--release",
        "--manifest-path",
        str(TASK_DIR / "gold_rust" / "Cargo.toml"),
        "--bin",
        "super_mario_bros_service",
        "--",
        "--host",
        args.host,
        "--port",
        str(port),
    ]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
