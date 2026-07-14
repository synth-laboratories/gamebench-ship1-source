#!/usr/bin/env python3
"""Score a candidate Rust port against a GameBench gold task's NEV oracle.

Acceptance criterion (bun-in-rust methodology): the port is graded ONLY by
behavioral parity against a language-independent oracle — the frozen NEV
eventlogs the Python gold produces. Aesthetics, idiom, and internal structure do
not count. Score = fraction of scenarios whose emitted event sequence is byte-for
-byte identical to the oracle.

The candidate Rust crate MUST expose a binary named `scenario` that reads one
scenario entry as JSON on stdin and writes `{"events": [...]}` on stdout — the
exact contract the gold_rust `scenario` bin implements. Everything else about the
crate is the porter's choice.

Usage:
  score_port.py --candidate <rust_dir>            # score a built/buildable crate dir
  score_port.py --from-manifest <manifest.json>   # materialize a jesterky port manifest, then score
  [--source-task frogs-singleplayer]              # which gold task supplies source + oracle
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

GAMEBENCH = Path(__file__).resolve().parents[2]


def source_task_dir(task: str) -> Path:
    d = GAMEBENCH / "tasks" / task
    if not d.is_dir():
        raise SystemExit(f"source task not found: {d}")
    return d


def load_scenarios(task_dir: Path) -> list[dict]:
    p = task_dir / "fixtures" / "gold" / "scenarios" / "scenarios.json"
    return json.loads(p.read_text())["scenarios"]


def load_oracle(task_dir: Path) -> dict[str, list[str]]:
    """scenario_id -> expected NEV event list (the frozen, language-independent oracle)."""
    p = task_dir / "fixtures" / "gold" / "eventlogs" / "eventlogs.json"
    doc = json.loads(p.read_text())
    # tasks differ in the container key: frogs uses "scenarios", tictactoe "games".
    scen = doc.get("scenarios", doc.get("games"))
    if scen is None:
        raise KeyError(f"{p}: no 'scenarios' or 'games' container")
    # eventlogs may be keyed by scenario_id or a parallel list; normalize to a map.
    if isinstance(scen, dict):
        return {sid: v["events"] for sid, v in scen.items()}
    return {v["scenario_id"]: v["events"] for v in scen}


def cargo_build(candidate: Path) -> tuple[bool, str]:
    manifest = candidate / "Cargo.toml"
    if not manifest.is_file():
        return False, f"no Cargo.toml in {candidate}"
    proc = subprocess.run(
        ["cargo", "build", "--quiet", "--manifest-path", str(manifest), "--bin", "scenario"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return False, f"cargo build failed:\n{proc.stderr[-2000:]}"
    return True, "ok"


def run_scenario_bin(candidate: Path, entry: dict) -> tuple[list[str] | None, str]:
    manifest = candidate / "Cargo.toml"
    proc = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(manifest), "--bin", "scenario", "--"],
        input=json.dumps(entry), text=True, capture_output=True,
    )
    if proc.returncode != 0:
        return None, f"scenario bin exited {proc.returncode}: {proc.stderr[-500:]}"
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return None, f"scenario stdout not JSON: {e} (got: {proc.stdout[:200]!r})"
    if not isinstance(out, dict) or "events" not in out:
        return None, "scenario output missing `events`"
    return out["events"], "ok"


def score(candidate: Path, source_task: str) -> dict:
    task_dir = source_task_dir(source_task)
    scenarios = load_scenarios(task_dir)
    oracle = load_oracle(task_dir)

    build_ok, build_detail = cargo_build(candidate)
    per_scenario = []
    passed = 0
    for entry in scenarios:
        sid = entry["scenario_id"]
        expected = oracle.get(sid)
        if not build_ok:
            per_scenario.append({"scenario_id": sid, "ok": False, "reason": "build_failed"})
            continue
        actual, detail = run_scenario_bin(candidate, entry)
        if actual is None:
            per_scenario.append({"scenario_id": sid, "ok": False, "reason": detail})
            continue
        ok = actual == expected
        if ok:
            passed += 1
        per_scenario.append({
            "scenario_id": sid, "ok": ok,
            "reason": "match" if ok else "event_mismatch",
            **({} if ok else {"first_diff": _first_diff(expected, actual)}),
        })
    total = len(scenarios)
    return {
        "schema": "gamebench.dev_port.score.v1",
        "source_task": source_task,
        "build_ok": build_ok,
        "build_detail": build_detail if not build_ok else "ok",
        "passed": passed,
        "total": total,
        "score": round(passed / total, 4) if total else 0.0,
        "per_scenario": per_scenario,
    }


def _first_diff(expected: list[str] | None, actual: list[str]) -> dict:
    expected = expected or []
    for i in range(max(len(expected), len(actual))):
        e = expected[i] if i < len(expected) else None
        a = actual[i] if i < len(actual) else None
        if e != a:
            return {"index": i, "expected": e, "actual": a}
    return {}


def _files_from_manifest(manifest: dict) -> list[dict]:
    """The porter's `files` from a manifest: recorded[].outputs.files, or a
    top-level {files:[...]}. A failed run records neither → []."""
    if isinstance(manifest.get("files"), list):
        return manifest["files"]
    for rec in manifest.get("recorded", []):
        out = rec.get("outputs") or {}
        if isinstance(out.get("files"), list):
            return out["files"]
    return []


def materialize_manifest(manifest_path: Path) -> Path:
    """Write a port manifest's `{files:[{path,content}]}` into a temp crate dir.

    Tolerant of failed runs: a manifest with no files (model failed / truncated
    reply) materializes an empty crate that scores 0.0 (build_failed) — the correct
    data point for a model that produced no port, never an abort.
    """
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    files = _files_from_manifest(manifest) if isinstance(manifest, dict) else []
    dest = Path(tempfile.mkdtemp(prefix="dev_port_candidate_"))
    for f in files:
        rel = f["path"].lstrip("/")
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f["content"])
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--candidate", help="path to a candidate Rust crate dir (with a `scenario` bin)")
    g.add_argument("--from-manifest", help="a jesterky run manifest whose porter output has {files:[...]}")
    ap.add_argument("--source-task", default="frogs-singleplayer")
    ap.add_argument("--out", help="write the score JSON here too")
    args = ap.parse_args()

    candidate = Path(args.candidate) if args.candidate else materialize_manifest(Path(args.from_manifest))
    result = score(candidate, args.source_task)
    # Count the porter's source files only — exclude cargo's build output (target/).
    result["crate_files"] = sum(
        1 for p in candidate.rglob("*")
        if p.is_file() and "target" not in p.relative_to(candidate).parts
    )
    if result["crate_files"] == 0:
        result["build_detail"] = "no port produced (model failed / empty manifest)"
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text)
    # Non-zero exit if not a perfect port, so CI/optimizers can gate on it.
    sys.exit(0 if result["score"] == 1.0 else 1)


if __name__ == "__main__":
    main()
