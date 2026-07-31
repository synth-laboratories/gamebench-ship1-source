#!/usr/bin/env python3
"""Typed boundary between Harbor agent execution and benchmark verification."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping


class ContractError(RuntimeError):
    """Raised when a runner result cannot satisfy the Harbor lane contract."""


class AgentStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class BenchmarkStatus(StrEnum):
    PASSED = "passed"
    REJECTED = "rejected"
    FAILED = "failed"


class FailureKind(StrEnum):
    NONE = "none"
    AGENT = "agent"
    BENCHMARK = "benchmark"
    VERIFIER = "verifier"
    RUNNER = "runner"


@dataclass(frozen=True, slots=True)
class ExecutionStatus:
    """Independent terminal states for the runner, agent, and verifier."""

    runner_rc: int
    agent_rc: int
    verify_rc: int
    agent_status: AgentStatus
    benchmark_status: BenchmarkStatus
    failure_kind: FailureKind
    agent_error: str | None = None
    contract_error: str | None = None
    schema_version: str = "gamebench.harbor.execution_status.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_object(path: Path, *, required: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if required:
            raise ContractError(f"cannot read JSON object {path}: {exc}") from exc
        return {}
    if not isinstance(value, dict):
        if required:
            raise ContractError(f"expected JSON object in {path}")
        return {}
    return value


def _exit_code(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{field} must be an integer")
    if value < 0:
        raise ContractError(f"{field} must be non-negative")
    return value


def _error_text(value: Any) -> str | None:
    if isinstance(value, str):
        text = value
    elif isinstance(value, Mapping):
        parts = (
            value.get("classification"),
            value.get("detail"),
            value.get("message"),
            value.get("reason"),
        )
        text = ": ".join(str(part).strip() for part in parts if str(part or "").strip())
    else:
        text = ""
    normalized = " ".join(text.split())
    return normalized[:1000] or None


def _read_reward(path: Path) -> float | None:
    try:
        return float(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _classify(
    *,
    runner_rc: int,
    agent_rc: int,
    verify_rc: int,
    reward: float | None,
    agent_error: str | None,
    contract_error: str | None = None,
) -> ExecutionStatus:
    agent_status = AgentStatus.COMPLETED if agent_rc == 0 else AgentStatus.FAILED
    if contract_error is not None:
        benchmark_status = BenchmarkStatus.FAILED
        failure_kind = FailureKind.RUNNER
    elif agent_rc != 0:
        benchmark_status = (
            BenchmarkStatus.REJECTED if reward is not None else BenchmarkStatus.FAILED
        )
        failure_kind = FailureKind.AGENT
    elif reward is None:
        benchmark_status = BenchmarkStatus.FAILED
        failure_kind = FailureKind.VERIFIER
    elif verify_rc == 0:
        benchmark_status = BenchmarkStatus.PASSED
        failure_kind = FailureKind.NONE
    else:
        benchmark_status = BenchmarkStatus.REJECTED
        failure_kind = FailureKind.BENCHMARK
    return ExecutionStatus(
        runner_rc=runner_rc,
        agent_rc=agent_rc,
        verify_rc=verify_rc,
        agent_status=agent_status,
        benchmark_status=benchmark_status,
        failure_kind=failure_kind,
        agent_error=agent_error if agent_rc != 0 else None,
        contract_error=contract_error,
    )


def interpret_codex_result(
    result_path: Path,
    *,
    runner_rc: int,
    reward_path: Path,
) -> ExecutionStatus:
    """Recover child exit codes from the combined Codex runner result."""

    result: dict[str, Any] = {}
    try:
        result = _read_object(result_path, required=True)
        metadata = result.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ContractError("rollout result metadata must be an object")
        agent_rc = _exit_code(
            metadata.get("codex_returncode"), field="metadata.codex_returncode"
        )
        verify_rc = _exit_code(
            metadata.get("verifier_returncode"),
            field="metadata.verifier_returncode",
        )
        agent_error = _error_text(result.get("error"))
        trace_v5 = metadata.get("trace_v5")
        # Required Responses capture is part of Harbor agent completion. When
        # Codex/verifier codes are present but the sealed capture failed, treat
        # the lane as an agent fault instead of inventing verify_rc=125.
        if (
            isinstance(trace_v5, Mapping)
            and trace_v5.get("required_trace_failed") is True
            and agent_rc == 0
        ):
            agent_rc = runner_rc or 1
            agent_error = agent_error or _error_text(trace_v5.get("failure"))
        return _classify(
            runner_rc=runner_rc,
            agent_rc=agent_rc,
            verify_rc=verify_rc,
            reward=_read_reward(reward_path),
            agent_error=agent_error,
        )
    except ContractError as exc:
        fallback_rc = runner_rc or 1
        # Prefer a recorded agent/capture error over wiping the reward path.
        # verify_rc=125 remains the sentinel only when child metadata is absent.
        return _classify(
            runner_rc=runner_rc,
            agent_rc=fallback_rc,
            verify_rc=125,
            reward=_read_reward(reward_path),
            agent_error=_error_text(result.get("error")) or str(exc),
            contract_error=str(exc),
        )


def host_execution_status(
    *, agent_rc: int, verify_rc: int, reward_path: Path
) -> ExecutionStatus:
    return _classify(
        runner_rc=agent_rc,
        agent_rc=agent_rc,
        verify_rc=verify_rc,
        reward=_read_reward(reward_path),
        agent_error=None,
    )


@dataclass(frozen=True, slots=True)
class ReceiptIdentity:
    task_id: str
    agent: str
    model: str
    effort: str
    out_dir: Path


def build_lane_receipt(
    identity: ReceiptIdentity,
    status: ExecutionStatus,
) -> dict[str, Any]:
    out = identity.out_dir
    result_path = out / "logs" / "verifier" / "result.json"
    reward_path = out / "logs" / "verifier" / "reward.txt"
    verifier = _read_object(result_path)
    rollout = _read_object(out / "rollout_result.json")
    metadata = rollout.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    status_payload = status.to_dict()
    execution_schema = status_payload.pop("schema_version")
    payload: dict[str, Any] = {
        "schema_version": "gamebench.harbor.lane_receipt.v2",
        "execution_status_schema_version": execution_schema,
        "task_id": identity.task_id,
        "agent": identity.agent,
        "model": identity.model,
        "effort": identity.effort,
        "out_dir": str(out),
        # Compatibility fields for existing panel and evals readers.
        "agent_rc": status.agent_rc,
        "verify_rc": status.verify_rc,
        **status_payload,
    }
    reward = _read_reward(reward_path)
    if reward is not None:
        payload["reward"] = reward
    elif reward_path.is_file():
        payload["reward_raw"] = reward_path.read_text(encoding="utf-8").strip()
    if verifier:
        payload["verifier"] = verifier
    if isinstance(metadata.get("trace_v5"), Mapping):
        payload["trace_v5"] = dict(metadata["trace_v5"])
    for name in (
        "baseline_score",
        "best_score",
        "delta_vs_baseline",
        "best_candidate_id",
        "score_metric",
        "baseline_mean_scout_score",
        "best_mean_scout_score",
        "delta_mean_scout_score",
        "best_scout_candidate_id",
    ):
        payload[name] = verifier.get(name)
    if verifier.get("error"):
        payload["verifier_error"] = verifier["error"]
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect-codex")
    inspect_parser.add_argument("--result", type=Path, required=True)
    inspect_parser.add_argument("--runner-rc", type=int, required=True)
    inspect_parser.add_argument("--reward", type=Path, required=True)
    inspect_parser.add_argument("--output", type=Path, required=True)
    host_parser = subparsers.add_parser("record-host")
    host_parser.add_argument("--agent-rc", type=int, required=True)
    host_parser.add_argument("--verify-rc", type=int, required=True)
    host_parser.add_argument("--reward", type=Path, required=True)
    host_parser.add_argument("--output", type=Path, required=True)
    receipt_parser = subparsers.add_parser("write-receipt")
    receipt_parser.add_argument("--status", type=Path, required=True)
    receipt_parser.add_argument("--receipt", type=Path, required=True)
    receipt_parser.add_argument("--task", required=True)
    receipt_parser.add_argument("--agent", required=True)
    receipt_parser.add_argument("--model", required=True)
    receipt_parser.add_argument("--effort", required=True)
    receipt_parser.add_argument("--out-dir", type=Path, required=True)
    return parser


def _status_from_path(path: Path) -> ExecutionStatus:
    payload = _read_object(path, required=True)
    try:
        return ExecutionStatus(
            runner_rc=_exit_code(payload.get("runner_rc"), field="runner_rc"),
            agent_rc=_exit_code(payload.get("agent_rc"), field="agent_rc"),
            verify_rc=_exit_code(payload.get("verify_rc"), field="verify_rc"),
            agent_status=AgentStatus(str(payload["agent_status"])),
            benchmark_status=BenchmarkStatus(str(payload["benchmark_status"])),
            failure_kind=FailureKind(str(payload["failure_kind"])),
            agent_error=_error_text(payload.get("agent_error")),
            contract_error=_error_text(payload.get("contract_error")),
        )
    except (KeyError, ValueError) as exc:
        raise ContractError(f"invalid execution status {path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "inspect-codex":
        status = interpret_codex_result(
            args.result,
            runner_rc=args.runner_rc,
            reward_path=args.reward,
        )
        _write_json(args.output, status.to_dict())
        print(status.agent_rc, status.verify_rc)
        return 0
    if args.command == "record-host":
        status = host_execution_status(
            agent_rc=args.agent_rc,
            verify_rc=args.verify_rc,
            reward_path=args.reward,
        )
        _write_json(args.output, status.to_dict())
        print(status.agent_rc, status.verify_rc)
        return 0
    status = _status_from_path(args.status)
    receipt = build_lane_receipt(
        ReceiptIdentity(
            task_id=args.task,
            agent=args.agent,
            model=args.model,
            effort=args.effort,
            out_dir=args.out_dir,
        ),
        status,
    )
    _write_json(args.receipt, receipt)
    print(f"receipt: {args.receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
