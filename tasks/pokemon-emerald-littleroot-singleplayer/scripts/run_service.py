#!/usr/bin/env python3
"""Run the Pokémon Emerald Littleroot Rust gold HTTP service."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess


TASK_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=["rust"], default="rust")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GAMEBENCH_POKEMON_EMERALD_PORT", "8103")),
    )
    args = parser.parse_args()
    subprocess.run(
        [
            "cargo",
            "run",
            "--release",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "emerald_gold",
            "--",
            "--port",
            str(args.port),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
