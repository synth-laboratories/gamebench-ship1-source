#!/usr/bin/env python3
"""Benchmark Rogue checkpoints."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from engine import RogueEngine
from scenarios import scenario_to_task
from task_resolve import resolve_task


def percentile(values: list[float], pct: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(round((pct / 100.0) * (len(values) - 1))))]


def bench_python(iterations: int) -> dict[str, Any]:
    entry = json.loads((TASK_DIR / "fixtures" / "gold" / "scenarios" / "scenarios.json").read_text())["scenarios"][0]
    engine = RogueEngine()
    engine.reset(resolve_task(scenario_to_task(entry)))
    for action in entry["actions"][:4]:
        engine.step(action)
    save_ms: list[float] = []
    restore_ms: list[float] = []
    sizes: list[int] = []
    for _ in range(iterations):
        start = time.perf_counter()
        blob = engine.checkpoint_bytes()
        save_ms.append((time.perf_counter() - start) * 1000.0)
        clone = RogueEngine()
        start = time.perf_counter()
        clone.restore_checkpoint(blob)
        restore_ms.append((time.perf_counter() - start) * 1000.0)
        sizes.append(len(blob))
    return {"iterations": iterations, "bytes_mean": statistics.mean(sizes), "save_p50_ms": percentile(save_ms, 50), "save_p99_ms": percentile(save_ms, 99), "restore_p50_ms": percentile(restore_ms, 50), "restore_p99_ms": percentile(restore_ms, 99)}


def bench_rust(iterations: int) -> dict[str, Any]:
    proc = subprocess.run(["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "bench", "--", "--iterations", str(iterations)], text=True, capture_output=True, check=True)
    return json.loads(proc.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=["python", "rust", "both"], default="both")
    parser.add_argument("--iterations", type=int, default=300)
    args = parser.parse_args()
    report: dict[str, Any] = {"schema": "gamebench.rogue.checkpoint_bench.v1"}
    if args.lane in {"python", "both"}:
        report["python"] = bench_python(args.iterations)
    if args.lane in {"rust", "both"}:
        report["rust"] = bench_rust(args.iterations)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
