#!/usr/bin/env python3
"""Select and run the Rust scenario binary with an explicit provenance choice."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence


TASK_DIR = Path(__file__).resolve().parents[1]
RELEASE_SCENARIO = TASK_DIR / "gold_rust" / "target" / "release" / "scenario"


def scenario_command(arguments: Sequence[str] = ()) -> list[str]:
    """Return the exact command for a Rust replay.

    Cargo remains the default so source edits cannot be masked by a stale
    release artifact.  Long campaigns can opt into a rebuilt release binary
    with ``NETHACK_USE_RELEASE_SCENARIO=1`` or an explicit executable path via
    ``NETHACK_RUST_SCENARIO``.
    """

    override = os.environ.get("NETHACK_RUST_SCENARIO", "").strip()
    if override:
        binary = Path(override).expanduser()
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise RuntimeError(f"NETHACK_RUST_SCENARIO is not executable: {binary}")
        return [str(binary), *arguments]
    use_release = os.environ.get("NETHACK_USE_RELEASE_SCENARIO", "").lower() in {"1", "true", "yes"}
    if use_release:
        if not RELEASE_SCENARIO.is_file() or not os.access(RELEASE_SCENARIO, os.X_OK):
            raise RuntimeError(
                "NETHACK_USE_RELEASE_SCENARIO requested but the release binary is missing; "
                "run cargo build --release --manifest-path gold_rust/Cargo.toml first"
            )
        return [str(RELEASE_SCENARIO), *arguments]
    return [
        "cargo",
        "run",
        "--quiet",
        "--manifest-path",
        str(TASK_DIR / "gold_rust" / "Cargo.toml"),
        "--bin",
        "scenario",
        "--",
        *arguments,
    ]


def run_scenario(payload: Any, arguments: Sequence[str] = ()) -> dict[str, Any]:
    """Run one JSON scenario and decode its JSON response."""

    completed = subprocess.run(
        scenario_command(arguments),
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return dict(json.loads(completed.stdout))
