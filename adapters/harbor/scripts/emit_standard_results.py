#!/usr/bin/env python3
"""Move standalone Harbor terminal evidence into the canonical evals results tree."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _data_root(evals_root: Path) -> Path:
    configured = str(os.environ.get("EVALS_DATA_ROOT") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    try:
        common = subprocess.run(
            [
                "git",
                "-C",
                str(evals_root),
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        path = Path(common).resolve()
        if path.name == ".git":
            return path.parent / "data"
    except (OSError, subprocess.CalledProcessError):
        pass
    return evals_root / "data"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evals-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--started-at", required=True)
    args = parser.parse_args()

    evals_root = args.evals_root.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    results_root = (_data_root(evals_root) / "results").resolve()
    if out_dir.is_relative_to(results_root):
        return 0

    stamp = args.started_at
    config_id = f"gamebench-harbor-{args.family}-standalone"
    run_dir = results_root / config_id / stamp
    safe_task = args.task.replace("/", "-")
    job_name = f"{safe_task}-{args.agent}"
    job_dir = run_dir / job_name
    harbor_dir = job_dir / "harbor"
    harbor_dir.mkdir(parents=True, exist_ok=True)

    for name in ("lane-receipt.json", "rollout.json", "rollout_result.json"):
        source = out_dir / name
        if source.is_file():
            shutil.move(str(source), harbor_dir / name)
    source_logs = out_dir / "logs"
    if source_logs.is_dir():
        shutil.move(str(source_logs), harbor_dir / "logs")

    receipt = _read(harbor_dir / "lane-receipt.json")
    if not isinstance(receipt.get("trace_v5"), dict):
        rollout = _read(harbor_dir / "rollout_result.json")
        metadata = rollout.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        if isinstance(metadata.get("trace_v5"), dict):
            receipt["trace_v5"] = dict(metadata["trace_v5"])
    trace = receipt.get("trace_v5")
    if isinstance(trace, dict):
        source_text = str(trace.get("bundle") or "").strip()
        source_bundle = (
            Path(source_text).expanduser().resolve()
            if source_text
            else None
        )
        if (
            source_bundle is not None
            and source_bundle.is_dir()
            and source_bundle.is_relative_to(out_dir)
            and not source_bundle.is_relative_to(harbor_dir)
        ):
            destination = harbor_dir / "logs" / "trace_v5"
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                shutil.rmtree(destination)
            shutil.move(str(source_bundle), destination)
            trace["bundle"] = str(destination)
            receipt["trace_v5"] = trace
            (harbor_dir / "lane-receipt.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    verifier = receipt.get("verifier")
    verifier = verifier if isinstance(verifier, dict) else {}
    reward = receipt.get("reward")
    scored = isinstance(reward, (int, float)) and not isinstance(reward, bool)
    verify_rc = receipt.get("verify_rc")
    passed = args.exit_code == 0 and verify_rc == 0 and scored
    trace = receipt.get("trace_v5")
    trace_emitted = (
        1
        if isinstance(trace, dict)
        and trace.get("passed") is True
        and isinstance(trace.get("capture"), dict)
        else 0
    )
    trace_mode = str(os.environ.get("SYNTH_TRACE_MODE") or "best_effort")
    result = {
        "status": "passed" if passed else "evaluated" if scored else "failed",
        "job": job_name,
        "bench": "gamebench",
        "task": f"{args.task}/{args.family}",
        "lane": "harbor",
        "trace_mode": trace_mode,
        "trace_summary": {
            "mode": trace_mode,
            "expected": 1 if trace_mode == "required" else 0,
            "emitted": trace_emitted,
        },
        "benchmark_status": "passed" if passed else "scored" if scored else None,
        "benchmark_score": float(reward) if scored else None,
        "exit_code": args.exit_code,
        "reason": None if passed else "benchmark_failed" if scored else "verifier_missing",
        "artifacts": {
            "lane-receipt.json": receipt,
            "result.json": verifier,
        },
    }
    (job_dir / "job_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "evals.matrix-run.v1",
        "matrix_id": config_id,
        "matrix_run_id": f"{config_id}:{stamp}",
        "status": "passed" if passed else "completed" if scored else "failed",
        "started_at": stamp,
        "completed_at": stamp,
        "output_root": str(run_dir),
        "jobs": [
            {
                "name": job_name,
                "bench": "gamebench",
                "task": f"{args.task}/{args.family}",
                "lane": "harbor",
                "model": args.model,
                "effort": args.effort,
            }
        ],
    }
    (run_dir / "matrix_run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(evals_root))
    try:
        from core.results.store import ingest_run_dir

        ingest_run_dir(run_dir)
    except Exception as exc:
        print(f"standalone results index warning: {exc}", file=sys.stderr)
    print(f"standard_results={run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
