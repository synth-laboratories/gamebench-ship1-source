from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
CONTRACT_SCRIPT = SCRIPT_DIR / "harbor_run_contract.py"
WRAPPER_SCRIPT = SCRIPT_DIR / "_run_harbor_agent.sh"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "gamebench_harbor_run_contract",
        CONTRACT_SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_codex_benchmark_rejection_is_not_an_agent_failure(tmp_path: Path) -> None:
    contract = _load_module()
    result = tmp_path / "rollout_result.json"
    reward = tmp_path / "logs" / "verifier" / "reward.txt"
    reward.parent.mkdir(parents=True)
    reward.write_text("0.0\n", encoding="utf-8")
    _write_json(
        result,
        {
            "success": False,
            "error": '{"baseline_score": 0.0303, "best_score": 0.0303}',
            "metadata": {
                "codex_returncode": 0,
                "verifier_returncode": 1,
            },
        },
    )

    status = contract.interpret_codex_result(
        result,
        runner_rc=1,
        reward_path=reward,
    )

    assert status.runner_rc == 1
    assert status.agent_rc == 0
    assert status.verify_rc == 1
    assert status.agent_status is contract.AgentStatus.COMPLETED
    assert status.benchmark_status is contract.BenchmarkStatus.REJECTED
    assert status.failure_kind is contract.FailureKind.BENCHMARK
    assert status.agent_error is None


def test_codex_provider_failure_preserves_agent_error(tmp_path: Path) -> None:
    contract = _load_module()
    result = tmp_path / "rollout_result.json"
    _write_json(
        result,
        {
            "success": False,
            "error": {
                "classification": "provider_error",
                "detail": "Selected model is at capacity.",
            },
            "metadata": {
                "codex_returncode": 1,
                "verifier_returncode": 1,
            },
        },
    )

    status = contract.interpret_codex_result(
        result,
        runner_rc=1,
        reward_path=tmp_path / "missing-reward.txt",
    )

    assert status.agent_status is contract.AgentStatus.FAILED
    assert status.failure_kind is contract.FailureKind.AGENT
    assert status.agent_error == "provider_error: Selected model is at capacity."


def test_required_trace_failure_forces_agent_fault_when_child_codes_are_zero(
    tmp_path: Path,
) -> None:
    contract = _load_module()
    result = tmp_path / "rollout_result.json"
    reward = tmp_path / "logs" / "verifier" / "reward.txt"
    reward.parent.mkdir(parents=True)
    reward.write_text("0.0455\n", encoding="utf-8")
    _write_json(
        result,
        {
            "success": False,
            "error": "required Harbor Responses capture is incomplete",
            "metadata": {
                "codex_returncode": 0,
                "verifier_returncode": 0,
                "trace_v5": {
                    "required_trace_failed": True,
                    "failure": "RuntimeError: incomplete capture",
                },
            },
        },
    )

    status = contract.interpret_codex_result(
        result,
        runner_rc=1,
        reward_path=reward,
    )

    assert status.agent_rc == 1
    assert status.verify_rc == 0
    assert status.agent_status is contract.AgentStatus.FAILED
    assert status.failure_kind is contract.FailureKind.AGENT
    assert "incomplete" in (status.agent_error or "")


def test_missing_codex_child_codes_still_reads_reward(
    tmp_path: Path,
) -> None:
    contract = _load_module()
    result = tmp_path / "rollout_result.json"
    reward = tmp_path / "logs" / "verifier" / "reward.txt"
    reward.parent.mkdir(parents=True)
    reward.write_text("0.1\n", encoding="utf-8")
    _write_json(result, {"success": False, "error": "capture exploded", "metadata": {}})

    status = contract.interpret_codex_result(
        result,
        runner_rc=1,
        reward_path=reward,
    )

    assert status.verify_rc == 125
    assert status.failure_kind is contract.FailureKind.RUNNER
    assert status.benchmark_status is contract.BenchmarkStatus.FAILED
    assert status.agent_error == "capture exploded"


def test_wrapper_prefers_agent_rc_over_verify_rc_125_sentinel() -> None:
    wrapper = WRAPPER_SCRIPT.read_text(encoding="utf-8")
    assert 'VERIFY_RC" -eq 125 && "$AGENT_RC" -ne 0' in wrapper


def test_receipt_reports_raw_best_score_for_rejected_benchmark(
    tmp_path: Path,
) -> None:
    contract = _load_module()
    verifier_dir = tmp_path / "logs" / "verifier"
    verifier_dir.mkdir(parents=True)
    (verifier_dir / "reward.txt").write_text("0.0\n", encoding="utf-8")
    _write_json(
        verifier_dir / "result.json",
        {
            "passed": False,
            "baseline_score": 0.0303,
            "best_score": 0.0303,
            "delta_vs_baseline": 0.0,
        },
    )
    status = contract.host_execution_status(
        agent_rc=0,
        verify_rc=1,
        reward_path=verifier_dir / "reward.txt",
    )

    receipt = contract.build_lane_receipt(
        contract.ReceiptIdentity(
            task_id="craftax-singleplayer",
            agent="codex",
            model="gpt-5.6-luna",
            effort="low",
            out_dir=tmp_path,
        ),
        status,
    )

    assert receipt["schema_version"] == "gamebench.harbor.lane_receipt.v2"
    assert receipt["benchmark_status"] == "rejected"
    assert receipt["failure_kind"] == "benchmark"
    assert receipt["reward"] == 0.0
    assert receipt["best_score"] == 0.0303
    assert "agent_error" not in receipt or receipt["agent_error"] is None


def test_wrapper_delegates_codex_verification_to_the_evals_runner() -> None:
    wrapper = WRAPPER_SCRIPT.read_text(encoding="utf-8")

    assert wrapper.count('bash "$TASK_ROOT/tests/test.sh"') == 1
    assert 'if [[ "$AGENT" != "codex" ]]; then' in wrapper
    assert "harbor_run_contract.py\" inspect-codex" in wrapper
