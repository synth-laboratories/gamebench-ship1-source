#!/usr/bin/env python3
"""Bundle a source gold task's Python engine + oracle into a jesterky port job.

Writes {"job": {...}} so the workflow's `ledger.job` is seeded. Gives the porter
the full Python source and the scenario ENTRIES (input shape), plus the expected
NEV events for exactly ONE scenario as a format example — the other scenarios are
held out, so the score measures a real port, not a memorized transcript.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

GAMEBENCH = Path(__file__).resolve().parents[2]
SRC_EXTS = (".py",)
SKIP = {"__pycache__"}


def collect_python(root: Path) -> list[dict]:
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_dir() or any(s in p.parts for s in SKIP):
            continue
        if p.suffix in SRC_EXTS:
            files.append({"path": str(p.relative_to(root)), "content": p.read_text()})
    return files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-task", default="frogs-singleplayer")
    ap.add_argument("--out", default=str(Path(__file__).parent / "job.json"))
    ap.add_argument("--example-scenarios", type=int, default=1,
                    help="how many scenarios include their expected events as a format example")
    args = ap.parse_args()

    task_dir = GAMEBENCH / "tasks" / args.source_task
    py_root = task_dir / "gold_python"
    if not py_root.is_dir():
        py_root = task_dir / "gold"  # some tasks name it `gold/`
    files = collect_python(py_root)

    scenarios = json.loads((task_dir / "fixtures" / "gold" / "scenarios" / "scenarios.json").read_text())["scenarios"]
    oracle_doc = json.loads((task_dir / "fixtures" / "gold" / "eventlogs" / "eventlogs.json").read_text())
    # frogs keys eventlogs under "scenarios"; tictactoe under "games".
    oracle_raw = oracle_doc.get("scenarios", oracle_doc.get("games"))
    oracle = (oracle_raw if isinstance(oracle_raw, dict)
              else {v["scenario_id"]: v for v in oracle_raw})

    sample = []
    for i, entry in enumerate(scenarios):
        item = {"entry": entry}
        if i < args.example_scenarios:
            item["expected_events"] = oracle[entry["scenario_id"]]["events"]
        sample.append(item)

    job = {
        "source_task": args.source_task,
        "language_from": "python",
        "language_to": "rust",
        "contract": ("Expose a Rust binary `scenario`: read ONE scenario entry as JSON on stdin, "
                     "write {\"events\": [...]} on stdout. Events must match the Python gold's NEV "
                     "strings and order exactly."),
        "files": files,
        "sample_scenarios": sample,
        "n_scenarios_total": len(scenarios),
    }
    Path(args.out).write_text(json.dumps({"job": job}))
    print(f"bundled {len(files)} python files, {len(scenarios)} scenarios "
          f"({args.example_scenarios} with expected events) → {args.out}")


if __name__ == "__main__":
    main()
