#!/usr/bin/env python3
"""Start the dependency-free Python gold HTTP service."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gold_python.service import serve


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8094)
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
