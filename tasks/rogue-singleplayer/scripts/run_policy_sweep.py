#!/usr/bin/env python3
"""Run one Rogue code-policy candidate on a sealed, supervised Rust suite."""

from __future__ import annotations

import argparse
import atexit
import hashlib
import http.client
import json
import math
import os
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.parse
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from containers.codepolicy.policy_subprocess import (
    CandidatePolicyFailure,
    IsolatedPolicyProcess,
    POLICY_PROCESS_CANDIDATE_FAILURE_EXIT_CODE,
    cleanup_isolated_policy_containers,
)
from containers.codepolicy.rollout_code_policy import rollout_code_policy


EXIT_CANDIDATE_EPISODE_TIMEOUT = 41
EXIT_EPISODE_WORKER_FAILURE = 42
EXIT_EVALUATOR_INFRASTRUCTURE_FAILURE = 43
_ACTIVE_CHILDREN: dict[int, subprocess.Popen[str]] = {}


class CandidateEpisodeTimeout(TimeoutError):
    """A candidate episode exceeded the benchmark-owned deadline."""


class EpisodeWorkerFailure(RuntimeError):
    """An episode worker failed outside the candidate policy boundary."""


def policy_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binary_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_suite(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Rogue suite must be an object")
    return payload


def suite_tasks(suite: Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(suite.get("tasks"), list):
        tasks: list[dict[str, Any]] = []
        for index, raw in enumerate(suite["tasks"]):
            if not isinstance(raw, Mapping):
                raise ValueError(f"suite task {index} must be an object")
            task = deepcopy(dict(raw))
            task.setdefault("task_id", f"{suite['suite_id']}_task_{index}")
            task.setdefault("seed", index + 1)
            if "grid" not in task:
                raise ValueError(f"suite task {task['task_id']} missing grid")
            tasks.append(task)
        return tasks
    task_path = str(suite.get("task_template", "tasks/policy_dev_template.json"))
    max_steps = int(suite.get("max_steps", 40))
    return [
        {
            "task_id": f"{suite['suite_id']}_seed_{int(seed)}",
            "seed": int(seed),
            "task_path": task_path,
            "max_steps": max_steps,
        }
        for seed in suite["seeds"]
    ]


def task_payload_for(task: Mapping[str, Any]) -> dict[str, Any]:
    if "grid" in task:
        return deepcopy(dict(task))
    task_path = Path(str(task.get("task_path", "tasks/policy_dev_template.json")))
    resolved = task_path if task_path.is_absolute() else TASK_DIR / task_path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    payload["task_id"] = str(task["task_id"])
    payload["seed"] = int(task["seed"])
    rules = dict(payload.get("rules") or {})
    overrides = dict(rules.get("overrides") or {})
    overrides["max_steps"] = int(task.get("max_steps", 40))
    rules["overrides"] = overrides
    payload["rules"] = rules
    return payload


class _HttpSession:
    def __init__(self, base_url: str) -> None:
        parsed = urllib.parse.urlparse(base_url.rstrip("/"))
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
            raise ValueError("Rogue Rust scorer must bind loopback HTTP")
        self.host = parsed.hostname
        self.port = int(parsed.port or 80)
        self._conn: http.client.HTTPConnection | None = None

    def request_json(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, separators=(",", ":"))
        headers = {"Content-Type": "application/json", "Connection": "keep-alive"}
        for attempt in range(2):
            if self._conn is None:
                self._conn = http.client.HTTPConnection(self.host, self.port, timeout=30)
            try:
                self._conn.request(method, path, body=body, headers=headers)
                response = self._conn.getresponse()
                raw = response.read()
                if response.status >= 400:
                    raise RuntimeError(f"Rogue Rust scorer HTTP {response.status}")
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(parsed, dict):
                    raise RuntimeError("Rogue Rust scorer returned non-object JSON")
                return parsed
            except (http.client.HTTPException, ConnectionError, TimeoutError, OSError):
                if self._conn is not None:
                    self._conn.close()
                self._conn = None
                if attempt:
                    raise
        raise RuntimeError("Rogue Rust scorer request failed")


def _failure_modes(result: Mapping[str, Any]) -> list[str]:
    details = result["reward_info"]["details"]
    private = result["state"]["private"]
    if details["outcome"] == "success":
        return []
    modes: list[str] = []
    if int(details.get("invalid_action_count", 0)) > 0:
        modes.append("invalid_command")
    if private.get("terminal_reason") == "death" or int(private.get("hp", 1)) <= 0:
        modes.append("death")
    if int(private.get("dungeon_level", 1)) <= 1 and not private.get("terminated"):
        modes.append("no_descent")
    if int(private.get("step_index", 0)) <= 1:
        modes.append("no_progress")
    if details["outcome"] == "truncated":
        modes.append("truncated")
    return modes or ["failed"]


def _rust_rollout(
    *, policy_path: Path, task: Mapping[str, Any], base_url: str, include_trace: bool
) -> dict[str, Any]:
    http = _HttpSession(base_url)
    seed = int(task["seed"])
    maximum = int(task.get("max_steps", 40))
    created = http.request_json(
        "POST", "/rollouts", {"task": task_payload_for(task), "seed": seed}
    )
    rollout_id = str(created["rollout_id"])
    latest = created
    readout = dict(created["readout"])
    candidate = IsolatedPolicyProcess(policy_path)
    turns: list[dict[str, Any]] = []
    invalid_actions = 0
    ply = 0
    try:
        while (
            not bool(latest.get("terminated"))
            and not bool(latest.get("truncated"))
            and ply < maximum
        ):
            valid_actions = [str(value) for value in readout.get("valid_actions") or []]
            decision = candidate(
                observation_text=str(readout.get("observation_text") or ""),
                session={"lane": "rust", "ply": ply},
                valid_actions=valid_actions,
                engine=None,
                seed=None,
                ply=ply,
                readout=readout,
            )
            action = str((decision.get("actions") or [""])[0])
            if action not in valid_actions:
                invalid_actions += 1
            latest = http.request_json(
                "POST", f"/rollouts/{rollout_id}/step", {"action": action}
            )
            readout = dict(latest["readout"])
            if include_trace:
                turns.append(
                    {
                        "ply": ply,
                        "action": action,
                        "policy_reason": str(decision.get("policy_reason") or ""),
                        "grid_hash": str(readout.get("grid_hash") or ""),
                    }
                )
            ply += 1
        events = http.request_json("GET", f"/rollouts/{rollout_id}/event_log")
        private = dict(readout.get("private") or {})
        public = dict(readout.get("public") or {})
        reward = float(latest.get("reward", private.get("total_reward", 0.0)))
        outcome = (
            "success"
            if reward >= 1.0
            else "truncated"
            if bool(latest.get("truncated")) or ply >= maximum
            else "failure"
        )
        progress = dict(readout.get("progress_metrics") or {})
        result: dict[str, Any] = {
            "trace_correlation_id": f"rogue-codepolicy-rust-{seed}",
            "rollout_id": rollout_id,
            "success_status": "success",
            "status_detail": outcome,
            "reward_info": {
                "outcome_reward": reward,
                "details": {
                    "seed": seed,
                    "task_id": str(readout.get("task_id") or task["task_id"]),
                    "outcome": outcome,
                    "steps": int(private.get("step_index", ply)),
                    "invalid_action_count": invalid_actions,
                    "policy_path": str(policy_path.resolve()),
                    **progress,
                },
            },
            "state": {"public": public, "private": private},
            "progress_metrics": progress,
            "artifact": [{"artifact_type": "turns", "turns": turns}],
            "benchmark_isolation": dict(candidate.isolation_receipt),
        }
        if include_trace:
            result["events"] = list(events.get("legacy") or [])
            result["nev"] = list(events.get("events") or [])
        return result
    finally:
        candidate.close()


def _python_rollout(
    *, policy_path: Path, task: Mapping[str, Any], include_trace: bool
) -> dict[str, Any]:
    candidate = IsolatedPolicyProcess(policy_path)
    try:
        result = rollout_code_policy(
            policy_path=policy_path,
            seed=int(task["seed"]),
            task_payload=task_payload_for(task),
            max_steps=int(task.get("max_steps", 40)),
            include_trace=include_trace,
            candidate_fn=candidate,
        )
        result["benchmark_isolation"] = dict(candidate.isolation_receipt)
        return result
    finally:
        candidate.close()


def _terminate_child(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _terminate_all_children() -> None:
    for process in list(_ACTIVE_CHILDREN.values()):
        _terminate_child(process)


def _episode_worker() -> int:
    request = json.load(sys.stdin)
    if not isinstance(request, Mapping):
        raise ValueError("episode worker request must be an object")
    try:
        lane = str(request["lane"])
        if lane == "rust":
            result = _rust_rollout(
                policy_path=Path(str(request["policy_path"])).resolve(),
                task=dict(request["task"]),
                base_url=str(request["base_url"]),
                include_trace=bool(request.get("include_trace")),
            )
        elif lane == "python":
            result = _python_rollout(
                policy_path=Path(str(request["policy_path"])).resolve(),
                task=dict(request["task"]),
                include_trace=bool(request.get("include_trace")),
            )
        else:
            raise ValueError("episode worker lane must be python or rust")
        result_path = Path(str(request["result_path"])).resolve()
        result_path.write_text(
            json.dumps(result, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return 0
    except CandidatePolicyFailure:
        return POLICY_PROCESS_CANDIDATE_FAILURE_EXIT_CODE


def _supervised_episode(
    *, policy_path: Path, task: Mapping[str, Any], lane: str, base_url: str,
    include_trace: bool, timeout_seconds: float
) -> dict[str, Any]:
    started = time.monotonic()
    env = os.environ.copy()
    env["FACTORYBENCH_POLICY_RUNNER_PID"] = str(os.getpid())
    with tempfile.TemporaryDirectory(prefix="rogue-episode-result-") as tmp:
        result_path = Path(tmp) / "result.json"
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--episode-worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            close_fds=True,
            cwd=TASK_DIR,
            env=env,
        )
        _ACTIVE_CHILDREN[process.pid] = process
        try:
            request = {
                "policy_path": str(policy_path),
                "task": dict(task),
                "lane": lane,
                "base_url": base_url,
                "include_trace": include_trace,
                "result_path": str(result_path),
            }
            try:
                _stdout, _stderr = process.communicate(
                    json.dumps(request, separators=(",", ":")),
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                _terminate_child(process)
                raise CandidateEpisodeTimeout() from exc
            if process.returncode == POLICY_PROCESS_CANDIDATE_FAILURE_EXIT_CODE:
                raise CandidatePolicyFailure()
            if process.returncode != 0 or not result_path.is_file():
                detail = (_stderr or "").strip()
                raise EpisodeWorkerFailure(
                    f"episode worker returncode={process.returncode}; stderr={detail}"
                )
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if not isinstance(result, dict):
                raise EpisodeWorkerFailure()
            result["benchmark_supervision"] = {
                "contract": "process_group_episode_timeout.v1",
                "timeout_seconds": float(timeout_seconds),
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "worker_returncode": process.returncode,
                "result_channel": "host_only_file",
            }
            return result
        finally:
            _ACTIVE_CHILDREN.pop(process.pid, None)
            _terminate_child(process)
            cleanup_isolated_policy_containers(
                runner_pid=os.getpid(), worker_pid=process.pid
            )


def _reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_rust_scorer(binary: Path) -> tuple[subprocess.Popen[str], str]:
    port = _reserve_port()
    process = subprocess.Popen(
        [str(binary), "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        close_fds=True,
        cwd=TASK_DIR,
    )
    _ACTIVE_CHILDREN[process.pid] = process
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Rogue Rust scorer exited during startup")
        try:
            health = _HttpSession(base_url).request_json("GET", "/health")
            if health.get("ok") is True and health.get("lane") == "rust":
                return process, base_url
        except (RuntimeError, OSError, ValueError):
            time.sleep(0.05)
    raise RuntimeError("Rogue Rust scorer health deadline exceeded")


def _policy_score(report: Mapping[str, Any], *, metric: str) -> float:
    if metric == "mean_synth_shaped_reward":
        return float(report["mean_synth_shaped_reward"])
    if metric == "mean_scout_score":
        return float(report["mean_scout_score"])
    if metric == "success_rate":
        return float(report["success_rate"])
    raise ValueError(f"unsupported Rogue score metric: {metric}")


def run_policy_sweep(
    *, policy_path: Path, suite: Mapping[str, Any], output_path: Path,
    lane: str, rust_binary: Path | None, include_trace: bool = False,
    episode_timeout_seconds: float
) -> dict[str, Any]:
    started = time.time()
    if episode_timeout_seconds <= 0 or not math.isfinite(episode_timeout_seconds):
        raise ValueError("episode timeout must be finite and positive")
    tasks = suite_tasks(suite)
    score_metric = str(suite.get("score_metric", "mean_synth_shaped_reward"))
    if lane not in {"python", "rust"}:
        raise ValueError("Rogue sweep lane must be python or rust")
    if lane == "rust":
        if rust_binary is None:
            raise ValueError("Rogue Rust sweep requires --rust-binary")
        scorer, base_url = _start_rust_scorer(rust_binary)
    else:
        scorer, base_url = None, ""
    results: list[dict[str, Any]] = []
    try:
        for task in tasks:
            results.append(
                _supervised_episode(
                    policy_path=policy_path,
                    task=task,
                    lane=lane,
                    base_url=base_url,
                    include_trace=include_trace,
                    timeout_seconds=episode_timeout_seconds,
                )
            )
    finally:
        if scorer is not None:
            _ACTIVE_CHILDREN.pop(scorer.pid, None)
            _terminate_child(scorer)
    rewards = [float(item["reward_info"]["outcome_reward"]) for item in results]
    scout = [float(item["reward_info"]["details"].get("scout_score", 0.0)) for item in results]
    shaped = [float(item["reward_info"]["details"].get("synth_shaped_reward", 0.0)) for item in results]
    successes = sum(item["reward_info"]["details"]["outcome"] == "success" for item in results)
    failure_counts = Counter(mode for item in results for mode in _failure_modes(item))
    report: dict[str, Any] = {
        "schema": "gamebench.rogue.policy_sweep_summary.v2",
        "env_family": "rogue-singleplayer",
        "source_witnessed": True,
        "claim_status": (
            "rust_gold_http" if lane == "rust" else "source_witnessed_python_proxy"
        ),
        "suite_id": str(suite["suite_id"]),
        "suite_path": None,
        "suite_source": "stdin",
        "score_metric": score_metric,
        "max_steps": int(suite.get("max_steps", 40)),
        "lane": lane,
        "engine_mode": "rust_http" if lane == "rust" else "python",
        "policy_isolation": "os_sandbox_observation_action.v2",
        "episode_timeout_seconds": float(episode_timeout_seconds),
        "policy_path": str(policy_path),
        "policy_sha256": policy_sha256(policy_path),
        "scorer_binary_sha256": (
            binary_sha256(rust_binary) if rust_binary is not None else None
        ),
        "seeds": [int(task["seed"]) for task in tasks],
        "n_seeds": len(tasks),
        "successes": successes,
        "success_rate": round(successes / len(tasks), 4) if tasks else 0.0,
        "mean_reward": round(statistics.mean(rewards), 4) if rewards else 0.0,
        "mean_scout_score": round(statistics.mean(scout), 4) if scout else 0.0,
        "mean_synth_shaped_reward": round(statistics.mean(shaped), 4) if shaped else 0.0,
        "invalid_action_count": sum(int(item["reward_info"]["details"].get("invalid_action_count", 0)) for item in results),
        "failure_mode_counts": dict(sorted(failure_counts.items())),
        "episode_summaries": [
            {
                "seed": int(item["reward_info"]["details"]["seed"]),
                "rollout_id": str(item["rollout_id"]),
                "reward": float(item["reward_info"]["outcome_reward"]),
                "scout_score": float(item["reward_info"]["details"].get("scout_score", 0.0)),
                "synth_shaped_reward": float(item["reward_info"]["details"].get("synth_shaped_reward", 0.0)),
                "supervision": item["benchmark_supervision"],
                "policy_isolation": item["benchmark_isolation"],
            }
            for item in results
        ],
        "elapsed_s": round(time.time() - started, 3),
        "episodes": results if include_trace else [],
    }
    report["score"] = round(_policy_score(report, metric=score_metric), 4)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _write_failure(
    output_path: Path,
    *,
    code: str,
    origin: str,
    exit_code: int,
    failure_class: str | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "schema": "gamebench.rogue.policy_sweep_failure.v1",
                "status": "failed",
                "exit_code": exit_code,
                "failure": {
                    "code": code,
                    "origin": origin,
                    "failure_class": failure_class,
                },
            },
            indent=2,
            sort_keys=True,
        ) + "\n"
    )


def main() -> int:
    if sys.argv[1:] == ["--episode-worker"]:
        return _episode_worker()
    parser = argparse.ArgumentParser(description="Run an isolated Rogue Rust policy sweep")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--suite-stdin", action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--suite")
    parser.add_argument("--lane", choices=("python", "rust"), default="python")
    parser.add_argument("--rust-binary")
    parser.add_argument("--episode-timeout-seconds", type=float, required=True)
    parser.add_argument("--include-trace", action="store_true")
    args = parser.parse_args()
    output = Path(args.output).expanduser().resolve()
    if args.suite_stdin == bool(args.suite):
        raise ValueError("provide exactly one of --suite-stdin or --suite")
    atexit.register(_terminate_all_children)
    if os.name == "posix":
        def terminate(signum: int, _frame: Any) -> None:
            _terminate_all_children()
            raise SystemExit(128 + signum)
        signal.signal(signal.SIGTERM, terminate)
        signal.signal(signal.SIGINT, terminate)
    try:
        suite = (
            json.load(sys.stdin)
            if args.suite_stdin
            else load_suite(Path(args.suite).expanduser().resolve())
        )
        if not isinstance(suite, Mapping):
            raise ValueError("sealed suite must be an object")
        report = run_policy_sweep(
            policy_path=Path(args.policy).expanduser().resolve(),
            suite=dict(suite),
            output_path=output,
            lane=str(args.lane),
            rust_binary=(
                Path(args.rust_binary).expanduser().resolve()
                if args.rust_binary
                else None
            ),
            include_trace=bool(args.include_trace),
            episode_timeout_seconds=float(args.episode_timeout_seconds),
        )
    except CandidatePolicyFailure:
        _write_failure(output, code="candidate_policy_failure", origin="candidate", exit_code=POLICY_PROCESS_CANDIDATE_FAILURE_EXIT_CODE)
        return POLICY_PROCESS_CANDIDATE_FAILURE_EXIT_CODE
    except CandidateEpisodeTimeout:
        _write_failure(output, code="candidate_episode_timeout", origin="candidate", exit_code=EXIT_CANDIDATE_EPISODE_TIMEOUT)
        return EXIT_CANDIDATE_EPISODE_TIMEOUT
    except EpisodeWorkerFailure:
        _write_failure(output, code="episode_worker_failure", origin="evaluator", exit_code=EXIT_EPISODE_WORKER_FAILURE)
        return EXIT_EPISODE_WORKER_FAILURE
    except BaseException as exc:
        _write_failure(
            output,
            code="evaluator_infrastructure_failure",
            origin="evaluator",
            exit_code=EXIT_EVALUATOR_INFRASTRUCTURE_FAILURE,
            failure_class=type(exc).__name__,
        )
        return EXIT_EVALUATOR_INFRASTRUCTURE_FAILURE
    print(json.dumps({key: report[key] for key in ("suite_id", "lane", "score_metric", "score", "n_seeds", "elapsed_s")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
