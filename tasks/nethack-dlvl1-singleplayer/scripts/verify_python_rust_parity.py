#!/usr/bin/env python3
"""Compare independent Python/Rust gold lanes and their checkpoint bridge."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIR))

from gold_python.scenarios import run_scenario


def first_difference(expected: Any, actual: Any, path: str = "$") -> str | None:
    if type(expected) is not type(actual):
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)) and expected == actual:
            return None
        return f"{path}: expected {type(expected).__name__}, got {type(actual).__name__}"
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                return f"{path}.{key}: unexpected Rust field"
            if key not in actual:
                return f"{path}.{key}: missing Rust field"
            difference = first_difference(expected[key], actual[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: expected length {len(expected)}, got {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            difference = first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
        return None
    return None if expected == actual else f"{path}: expected {expected!r}, got {actual!r}"


def rust_scenario(entry: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario"],
        input=json.dumps(entry),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def rust_restore(checkpoint: str, actions: list[int | str]) -> dict[str, Any]:
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(TASK_DIR / "gold_rust" / "Cargo.toml"), "--bin", "scenario", "--", "--checkpoint-replay-stdin"],
        input=json.dumps({"checkpoint": checkpoint, "actions": actions}),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def parity_projection(result: dict[str, Any]) -> dict[str, Any]:
    return {"events": result["events"], "nev": result["nev"], "state": result["state"], "readout": result["readout"]}


def main() -> None:
    failures: list[str] = []
    scenarios = sorted((TASK_DIR / "fixtures" / "gold" / "scenarios").glob("*.json"))
    for path in scenarios:
        entry = json.loads(path.read_text())
        python = run_scenario(entry)
        rust = rust_scenario(entry)
        difference = first_difference(parity_projection(python), parity_projection(rust))
        if difference:
            failures.append(f"{path.name}: {difference}")
            continue
        actions = list(entry.get("actions", []))
        cut = max(0, len(actions) // 2)
        if cut and cut < len(actions):
            from gold_python.engine import NethackDlvl1Engine
            from shared.task_resolve import resolve_task

            engine = NethackDlvl1Engine()
            engine.reset(resolve_task({key: value for key, value in entry.items() if key not in {"actions", "expected", "required_nev_kinds"}}))
            for action in actions[:cut]:
                engine.step(action)
            checkpoint = engine.checkpoint_bytes().decode("utf-8")
            for action in actions[cut:]:
                if engine.state["terminated"] or engine.state["truncated"]:
                    break
                engine.step(action)
            restored = rust_restore(checkpoint, actions[cut:])
            difference = first_difference(engine.symbolic_readout(), restored["projection"])
            if difference:
                failures.append(f"{path.name} Python→Rust checkpoint continuation: {difference}")
    if failures:
        raise SystemExit("NetHack Python/Rust parity FAILED\n" + "\n".join(failures))
    print(json.dumps({"status": "pass", "scenarios": [path.stem for path in scenarios], "checkpoint_bridge": "python_to_rust"}, sort_keys=True))


if __name__ == "__main__":
    main()
