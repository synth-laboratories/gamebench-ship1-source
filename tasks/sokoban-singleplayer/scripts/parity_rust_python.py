#!/usr/bin/env python3
"""Cross-lane parity: in-process Python engine vs Rust gold_rust library tests + HTTP smoke.

Usage:
  python scripts/parity_rust_python.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parents[1]
FIXTURE = TASK_DIR / "fixtures" / "gold" / "parity" / "parity_mini.json"


def _engine_parity() -> None:
    sys.path[:0] = [str(TASK_DIR), str(TASK_DIR / "gold_python"), str(TASK_DIR / "shared")]
    from engine import SokobanEngine
    from task_resolve import resolve_task

    fixture = json.loads(FIXTURE.read_text())
    task = fixture["task"]
    seed = fixture.get("seed", 0)
    expected = fixture["expected"]
    engine = SokobanEngine()
    engine.reset(resolve_task(task, seed_override=seed))
    readout = engine.symbolic_readout()
    assert readout["ascii"] == expected["reset"]["ascii"], readout["ascii"]
    assert readout["grid_hash"] == expected["reset"]["grid_hash"]
    assert engine.private.config_hash == expected["reset"]["config_hash"]
    assert engine.private.episode_id == expected["reset"]["episode_id"]
    for action in fixture["actions"]:
        engine.step(action)
    after = expected["after_actions"]
    readout = engine.symbolic_readout()
    assert readout["ascii"] == after["ascii"]
    assert readout["grid_hash"] == after["grid_hash"]
    assert engine.private.terminated is after["terminated"]
    assert abs(engine.private.total_reward - after["reward"]) < 1e-9
    assert sorted(engine.private.achievements) == after["achievements"]
    print("python_engine_parity_ok")


def _rust_unit() -> None:
    subprocess.run(
        ["cargo", "test", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml")],
        check=True,
    )
    print("rust_unit_parity_ok")


def _http_smoke(port: int = 8093) -> None:
    proc = subprocess.Popen(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "sokoban_gold",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(TASK_DIR / "gold_rust"),
    )
    try:
        fixture = json.loads(FIXTURE.read_text())
        health = None
        for _ in range(40):
            try:
                health = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1).read())
                break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        assert health and health.get("lane") == "rust", health
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/rollouts",
            data=json.dumps({"task": fixture["task"], "seed": fixture.get("seed", 0)}).encode(),
            headers={"Content-Type": "application/json"},
        )
        roll = json.loads(urllib.request.urlopen(req, timeout=5).read())
        assert roll["readout"]["ascii"] == fixture["expected"]["reset"]["ascii"]
        step_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/rollouts/{roll['rollout_id']}/step",
            data=json.dumps({"action": fixture["actions"][0]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        step = json.loads(urllib.request.urlopen(step_req, timeout=5).read())
        after = fixture["expected"]["after_actions"]
        assert step["terminated"] is after["terminated"]
        assert abs(float(step["reward"]) - after["reward"]) < 1e-9
        assert step["readout"]["ascii"] == after["ascii"]
        assert sorted(step["readout"]["private"]["achievements"]) == after["achievements"]
        print("rust_http_parity_ok")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _curriculum_sample() -> None:
    sys.path[:0] = [str(TASK_DIR), str(TASK_DIR / "gold_python"), str(TASK_DIR / "shared")]
    from engine import SokobanEngine
    from task_resolve import resolve_task

    task = {
        "schema": "gamebench.task.sokoban.v1",
        "task_id": "curriculum_smoke",
        "map": {"use_default": "curriculum_easy"},
        "rules": {"base": "sparse_sokoban"},
        "seed": 0,
    }
    # seed 0 is falsy in Python map resolve → index 0
    py = SokobanEngine()
    py.reset(resolve_task(task, seed_override=None))
    # Drive a few noop-ish steps via cargo test already covers inline; here just resolve.
    assert py.private.puzzle_id
    print("curriculum_resolve_ok", py.private.puzzle_id)


def main() -> int:
    _engine_parity()
    _rust_unit()
    _http_smoke()
    _curriculum_sample()
    print("ALL_PARITY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
