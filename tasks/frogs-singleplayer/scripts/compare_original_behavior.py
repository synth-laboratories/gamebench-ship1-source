#!/usr/bin/env python3
"""Compare FrogsGame tool-call behavior against the local upstream-derived reference."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from engine import FrogsEngine
from task_resolve import resolve_task


DEFAULT_ORIGINAL = Path("/Users/joshpurtell/Documents/GitHub/evals/reportbench/tasks/frogsgame_fbc_qwen35_4b_1/workspace/prepare.py")


def load_original(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("frogsgame_original_prepare", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot import original prepare.py: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.FrogGame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", default=str(DEFAULT_ORIGINAL))
    args = parser.parse_args()
    original_cls = load_original(Path(args.original).expanduser().resolve())
    board = json.loads((TASK_DIR / "defaults" / "classic_4x4.json").read_text())["board"]
    task = {
        "schema": "gamebench.task.frogs.v1",
        "task_id": "original_compare",
        "seed": 0,
        "board": board,
        "rules": {"base": "classic_frogs", "overrides": {"max_steps": 32, "max_tool_calls": 200}},
    }
    checks = [
        [("get_state", {})],
        [("place_frog", {"row": -1, "col": 0})],
        [("place_frog", {"row": 0, "col": 1}), ("place_frog", {"row": 0, "col": 3})],
        [("place_frog", {"row": 0, "col": 0}), ("place_frog", {"row": 1, "col": 1})],
        [("remove_frog", {"row": 0, "col": 0})],
        [("place_frog", {"row": 0, "col": 1}), ("check_violations", {}), ("submit", {})],
        [
            ("place_frog", {"row": 0, "col": 1}),
            ("remove_frog", {"row": 0, "col": 1}),
            ("reset", {}),
            ("get_state", {}),
        ],
        [
            ("place_frog", {"row": 0, "col": 1}),
            ("place_frog", {"row": 1, "col": 3}),
            ("place_frog", {"row": 2, "col": 0}),
            ("place_frog", {"row": 3, "col": 2}),
            ("submit", {}),
        ],
    ]
    failures: list[dict[str, Any]] = []
    for index, sequence in enumerate(checks):
        original = original_cls([row[:] for row in board], max_tool_calls=200)
        ours = FrogsEngine()
        ours.reset(resolve_task(task))
        for tool_name, tool_args in sequence:
            original_result = _call_original(original, tool_name, tool_args)
            ours_result = ours.execute_tool_call(tool_name, tool_args)
            if original_result != ours_result:
                failures.append(
                    {
                        "sequence": index,
                        "tool": tool_name,
                        "args": tool_args,
                        "original": original_result,
                        "ours": ours_result,
                    }
                )
                break
        if original.tool_call_count != ours.private.tool_call_count:
            failures.append(
                {
                    "sequence": index,
                    "tool": "tool_call_count",
                    "original": original.tool_call_count,
                    "ours": ours.private.tool_call_count,
                }
            )
        if original.frog_positions != sorted(ours.public.frogs):
            failures.append(
                {
                    "sequence": index,
                    "tool": "frog_positions",
                    "original": original.frog_positions,
                    "ours": sorted(ours.public.frogs),
                }
            )
    report = {
        "schema": "gamebench.frogs.original_behavior_compare.v1",
        "original": str(Path(args.original).expanduser().resolve()),
        "checks": len(checks),
        "match": not failures,
        "failures": failures,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


def _call_original(game: Any, tool_name: str, args: dict[str, Any]) -> Any:
    if tool_name == "place_frog":
        return game.place_frog(int(args.get("row", -1)), int(args.get("col", -1)))
    if tool_name == "remove_frog":
        return game.remove_frog(int(args.get("row", -1)), int(args.get("col", -1)))
    if tool_name == "get_state":
        return game.get_state()
    if tool_name == "check_violations":
        return game.check_violations()
    if tool_name == "submit":
        return game.submit()
    if tool_name == "reset":
        return game.reset()
    return {"error": f"Unknown tool: '{tool_name}'."}


if __name__ == "__main__":
    main()
