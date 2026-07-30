from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "emit_standard_results.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "gamebench_emit_standard_results",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_standalone_logs_trace_is_relocated_and_indexed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    evals_root = Path(__file__).resolve().parents[4] / "evals"
    out_dir = tmp_path / "tmp-harbor-run"
    trace_bundle = out_dir / "logs" / "trace_v5"
    trace_bundle.mkdir(parents=True)
    (trace_bundle / "manifest.json").write_text("{}\n", encoding="utf-8")
    receipt = {
        "schema_version": "gamebench.harbor.lane_receipt.v1",
        "verify_rc": 0,
        "reward": 0.0606,
        "verifier": {"passed": True},
        "trace_v5": {
            "passed": True,
            "bundle": str(trace_bundle),
        },
    }
    (out_dir / "lane-receipt.json").write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    data_root = tmp_path / "canonical-data"
    monkeypatch.setenv("EVALS_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SYNTH_TRACE_MODE", "required")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--evals-root",
            str(evals_root),
            "--out-dir",
            str(out_dir),
            "--family",
            "code_policy_opt",
            "--task",
            "craftax-singleplayer",
            "--agent",
            "codex",
            "--model",
            "gpt-5.6-luna",
            "--effort",
            "medium",
            "--exit-code",
            "0",
            "--started-at",
            "20260730T060000Z",
        ],
    )

    assert _load_module().main() == 0

    job_dir = (
        data_root
        / "results"
        / "gamebench-harbor-code_policy_opt-standalone"
        / "20260730T060000Z"
        / "craftax-singleplayer-codex"
    )
    moved_bundle = job_dir / "harbor" / "logs" / "trace_v5"
    moved_receipt = json.loads(
        (job_dir / "harbor" / "lane-receipt.json").read_text(encoding="utf-8")
    )
    result = json.loads(
        (job_dir / "job_result.json").read_text(encoding="utf-8")
    )

    assert moved_bundle.is_dir()
    assert moved_receipt["trace_v5"]["bundle"] == str(moved_bundle)
    assert result["status"] == "passed"
    assert result["trace_summary"] == {
        "mode": "required",
        "expected": 1,
        "emitted": 1,
    }
    assert (data_root / "results" / "results.db").is_file()
