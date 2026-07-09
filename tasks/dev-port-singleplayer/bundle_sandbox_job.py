#!/usr/bin/env python3
"""Bundle a source gold task into a jesterky **sandbox** port job.

Unlike `bundle_job.py` (which inlines the source as prompt text for a blind port),
this seeds an actual workspace the agent runs in: the Python gold source, the
scenario ENTRIES, the oracle events for a TRAIN subset, and a `check.py` the agent
runs to self-verify. The held-out scenarios' oracle is NOT seeded — scoring on
them (via `score_port.py`) measures a real port, not a memorized transcript.

Emits `{"job": {"files": [{path, content}], ...}}` — `job.files` is what the
sandbox's `files_input` writes to the workspace.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

GAMEBENCH = Path(__file__).resolve().parents[2]

CHECK_PY = '''#!/usr/bin/env python3
"""In-workspace checker: run the candidate Rust `scenario` bin over the TRAIN
scenarios and diff against the seeded oracle. Iterate until this is all-green,
then you are (probably) done — held-out scenarios are graded the same way.

    python check.py            # build once, run every train scenario
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent
scenarios = json.loads((HERE / "scenarios.json").read_text())["scenarios"]
oracle = json.loads((HERE / "train_eventlogs.json").read_text())  # {sid: [events]}
train = [s for s in scenarios if s["scenario_id"] in oracle]

build = subprocess.run(["cargo", "build", "--quiet", "--bin", "scenario"],
                       cwd=HERE, capture_output=True, text=True)
if build.returncode != 0:
    print("BUILD FAILED\\n" + build.stderr[-3000:]); sys.exit(1)

passed = 0
for s in train:
    p = subprocess.run(["cargo", "run", "--quiet", "--bin", "scenario", "--"],
                       cwd=HERE, input=json.dumps(s), capture_output=True, text=True)
    if p.returncode != 0:
        print(f"{s['scenario_id']}: scenario bin exited {p.returncode}: {p.stderr[-300:]}"); continue
    try:
        got = json.loads(p.stdout)["events"]
    except Exception as e:
        print(f"{s['scenario_id']}: bad stdout ({e}): {p.stdout[:200]!r}"); continue
    exp = oracle[s["scenario_id"]]
    if got == exp:
        passed += 1
    else:
        i = next((k for k in range(max(len(got), len(exp)))
                  if (got[k] if k < len(got) else None) != (exp[k] if k < len(exp) else None)), 0)
        print(f"{s['scenario_id']}: MISMATCH @#{i} expected={exp[i] if i<len(exp) else None!r} "
              f"got={got[i] if i<len(got) else None!r}")
print(f"\\nTRAIN {passed}/{len(train)} scenarios pass")
sys.exit(0 if passed == len(train) else 1)
'''


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-task", default="tictactoe-singleplayer")
    ap.add_argument("--out", default=str(Path(__file__).parent / "job.sandbox.json"))
    ap.add_argument("--train", type=int, default=4, help="scenarios whose oracle is seeded")
    args = ap.parse_args()

    task_dir = GAMEBENCH / "tasks" / args.source_task
    py_root = task_dir / "gold_python"
    if not py_root.is_dir():
        py_root = task_dir / "gold"

    files: list[dict] = []
    # Python gold source, under gold_python/ in the workspace (for reference/running).
    for p in sorted(py_root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        files.append({"path": f"gold_python/{p.relative_to(py_root)}", "content": p.read_text()})

    scenarios = json.loads((task_dir / "fixtures/gold/scenarios/scenarios.json").read_text())
    files.append({"path": "scenarios.json", "content": json.dumps(scenarios, indent=2)})

    oracle_doc = json.loads((task_dir / "fixtures/gold/eventlogs/eventlogs.json").read_text())
    oracle_raw = oracle_doc.get("scenarios", oracle_doc.get("games"))
    oracle = (oracle_raw if isinstance(oracle_raw, dict)
              else {v["scenario_id"]: v for v in oracle_raw})
    train_ids = [s["scenario_id"] for s in scenarios["scenarios"][: args.train]]
    train_oracle = {sid: oracle[sid]["events"] for sid in train_ids}
    files.append({"path": "train_eventlogs.json", "content": json.dumps(train_oracle, indent=2)})
    files.append({"path": "check.py", "content": CHECK_PY})

    job = {
        "source_task": args.source_task,
        "n_scenarios_total": len(scenarios["scenarios"]),
        "n_train": len(train_ids),
        "files": files,
    }
    Path(args.out).write_text(json.dumps({"job": job}))
    print(f"bundled {len(files)} workspace files "
          f"({len(train_ids)} train scenarios seeded, "
          f"{len(scenarios['scenarios']) - len(train_ids)} held out) → {args.out}")


if __name__ == "__main__":
    main()
