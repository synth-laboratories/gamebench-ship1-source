#!/usr/bin/env python3
"""Run an Overcooked v2 gold lane HTTP service."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=["python"], default="python")
    parser.add_argument("--host", default=os.environ.get("GAMEBENCH_OVERCOOKED_V2_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    port = args.port or int(os.environ.get("GAMEBENCH_OVERCOOKED_V2_PORT", "8094"))
    for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import uvicorn

    uvicorn.run("gold_python.service:app", host=args.host, port=port, reload=False)


if __name__ == "__main__":
    main()
