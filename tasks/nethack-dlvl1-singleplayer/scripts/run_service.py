#!/usr/bin/env python3
"""Start either own NetHack gold HTTP lane."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=("python", "rust"), required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    if args.lane == "python":
        sys.path.insert(0, str(TASK_DIR))
        import uvicorn
        from gold_python.service import app

        uvicorn.run(app, host=args.host, port=args.port or 8120)
        return
    command = [
        "cargo",
        "run",
        "--manifest-path",
        str(TASK_DIR / "gold_rust" / "Cargo.toml"),
        "--bin",
        "nethack_gold",
        "--",
        "--host",
        args.host,
        "--port",
        str(args.port or 8121),
    ]
    raise SystemExit(subprocess.call(command))


if __name__ == "__main__":
    main()
