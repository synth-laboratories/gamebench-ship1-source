#!/usr/bin/env python3
"""Typed boundary between Harbor agent execution and benchmark verification."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

_PROTOCOL_MISMATCH_PREFIX = "harbor_protocol_mismatch"
_SEALED_MODEL_KEYS = frozenset({"model", "model_id"})
_SEALED_VERSION_KEYS = frozenset({"multi_agent_version"})
_REQUEST_IDENTITY_KEYS = frozenset(
    {
        "codex_config_toml_append",
        "expected_model_id",
        "expected_multi_agent_version",
        "effective_model_name",
        "model_name",
    }
)
_TRACE_PATH_KEYS = ("bundle", "raw_codex_jsonl", "native_evaluation")
_MAX_SEALED_FILES = 64
_MAX_SEALED_FILE_BYTES = 20 * 1024 * 1024


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


def _optional_identity(value: Any) -> str | None:
    """Return a sealed identity string, preserving nulls instead of inventing one."""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        text = str(value).strip()
    elif isinstance(value, str):
        text = value.strip()
    else:
        return None
    if not text or text.lower() in {"none", "null"}:
        return None
    return text


def _normalize_model_id(value: Any) -> str | None:
    text = _optional_identity(value)
    if text is None:
        return None
    return text.split("/", 1)[-1]


def _normalize_multi_agent_version(value: Any) -> str | None:
    text = _optional_identity(value)
    return None if text is None else text.lower()


def expected_harbor_protocol_from_env(
    env: Mapping[str, str] | None = None,
) -> tuple[str | None, str | None]:
    source = os.environ if env is None else env
    expected_model = _normalize_model_id(
        source.get("GAMEBENCH_HARBOR_EXPECTED_MODEL_ID")
    )
    expected_version = _normalize_multi_agent_version(
        source.get("GAMEBENCH_HARBOR_EXPECTED_MULTI_AGENT_VERSION")
    )
    return expected_model, expected_version


def _collect_sealed_identity(
    value: Any,
    *,
    models: set[str],
    versions: set[str],
    depth: int = 0,
) -> None:
    if depth > 12 or value is None:
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key)
            if name in _REQUEST_IDENTITY_KEYS:
                continue
            if name in _SEALED_MODEL_KEYS:
                model = _normalize_model_id(child)
                if model is not None:
                    models.add(model)
                continue
            if name in _SEALED_VERSION_KEYS:
                version = _normalize_multi_agent_version(child)
                if version is not None:
                    versions.add(version)
                continue
            _collect_sealed_identity(
                child, models=models, versions=versions, depth=depth + 1
            )
        return
    if isinstance(value, list):
        for child in value[:200]:
            _collect_sealed_identity(
                child, models=models, versions=versions, depth=depth + 1
            )


def _load_json_document(path: Path) -> Any:
    try:
        if path.stat().st_size > _MAX_SEALED_FILE_BYTES:
            return None
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if path.suffix == ".jsonl" or path.name.endswith(".jsonl"):
        records: list[Any] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _trace_file_paths(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    found: list[Path] = []
    for child in sorted(path.rglob("*")):
        if not child.is_file():
            continue
        name = child.name
        if name.endswith(".jsonl") or "trace" in name or name == "manifest.json":
            found.append(child)
        if len(found) >= _MAX_SEALED_FILES:
            break
    return found


def _search_roots(result_path: Path, reward_path: Path | None) -> list[Path]:
    roots = [Path(str(result_path) + ".trace_v5.json")]
    logs = result_path.parent / "logs"
    roots.extend((logs / "trace_v5", logs / "agent"))
    workspace = result_path.parent / "workspace"
    roots.extend(
        (
            workspace / "logs" / "trace_v5",
            workspace / "logs" / "agent",
            workspace / ".codex" / "sessions",
        )
    )
    if reward_path is not None:
        verifier_logs = reward_path.parent
        if verifier_logs.name == "verifier":
            roots.append(verifier_logs.parent)
            roots.append(verifier_logs.parent / "trace_v5")
            roots.append(verifier_logs.parent / "agent")
    unique: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def collect_sealed_harbor_protocol(
    result: Mapping[str, Any],
    *,
    result_path: Path | None = None,
    reward_path: Path | None = None,
) -> tuple[set[str], set[str]]:
    """Collect sealed model/protocol identity. Nulls are omitted, never filled in."""

    models: set[str] = set()
    versions: set[str] = set()
    metadata = result.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    trace_v5 = metadata.get("trace_v5")
    if isinstance(trace_v5, Mapping):
        _collect_sealed_identity(trace_v5, models=models, versions=versions)
        for key in _TRACE_PATH_KEYS:
            raw_path = _optional_identity(trace_v5.get(key))
            if raw_path:
                for path in _trace_file_paths(Path(raw_path)):
                    _collect_sealed_identity(
                        _load_json_document(path), models=models, versions=versions
                    )
    if result_path is not None:
        for root in _search_roots(result_path, reward_path):
            for path in _trace_file_paths(root):
                _collect_sealed_identity(
                    _load_json_document(path), models=models, versions=versions
                )
    return models, versions


def assert_expected_harbor_protocol(
    result: Mapping[str, Any],
    *,
    result_path: Path | None = None,
    reward_path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Refuse unless sealed identity matches expected env. Do not invent identity."""

    expected_model, expected_version = expected_harbor_protocol_from_env(env)
    if expected_model is None and expected_version is None:
        return
    models, versions = collect_sealed_harbor_protocol(
        result, result_path=result_path, reward_path=reward_path
    )
    failures: list[str] = []
    if expected_model is not None:
        sealed_model = ",".join(sorted(models)) if models else "null"
        if expected_model not in models:
            failures.append(
                f"expected_model_id={expected_model} sealed={sealed_model}"
            )
    if expected_version is not None:
        sealed_version = ",".join(sorted(versions)) if versions else "null"
        if versions != {expected_version}:
            failures.append(
                f"expected_multi_agent_version={expected_version} sealed={sealed_version}"
            )
    if failures:
        raise ContractError(_PROTOCOL_MISMATCH_PREFIX + ":" + "; ".join(failures))


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
        try:
            assert_expected_harbor_protocol(
                result, result_path=result_path, reward_path=reward_path
            )
        except ContractError as exc:
            # Protocol mismatch is not a measured score. Keep child codes,
            # fail the lane, and do not treat verifier reward as valid.
            return ExecutionStatus(
                runner_rc=runner_rc,
                agent_rc=agent_rc,
                verify_rc=verify_rc if verify_rc != 0 else 1,
                agent_status=(
                    AgentStatus.COMPLETED if agent_rc == 0 else AgentStatus.FAILED
                ),
                benchmark_status=BenchmarkStatus.FAILED,
                failure_kind=FailureKind.RUNNER,
                agent_error=agent_error if agent_rc != 0 else None,
                contract_error=str(exc),
            )
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
    protocol_mismatch = str(status.contract_error or "").startswith(
        _PROTOCOL_MISMATCH_PREFIX
    )
    reward = _read_reward(reward_path)
    if protocol_mismatch:
        payload["reward"] = None
    elif reward is not None:
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
