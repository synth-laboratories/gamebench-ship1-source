#!/usr/bin/env python3
"""Run one Craftax code-policy candidate on a fixed suite."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from containers.codepolicy.rollout_code_policy import compile_check_policy, load_policy_module, rollout_code_policy
from containers.codepolicy.rust_repl_session import RustReplSession, ensure_rust_repl_binary
from scoring import achievement_success_score


_WORKER_RUST_REPL: RustReplSession | None = None
_WORKER_POLICY_CACHE: dict[str, Any] = {}
MAX_RUST_REPL_ACTION_BATCH = 16
RUST_REPL_VALID_ACTIONS = [
    "noop",
    "left",
    "right",
    "up",
    "down",
    "do",
    "sleep",
    "place_stone",
    "place_table",
    "place_furnace",
    "place_plant",
    "make_wood_pickaxe",
    "make_stone_pickaxe",
    "make_iron_pickaxe",
    "make_wood_sword",
    "make_stone_sword",
    "make_iron_sword",
    "rest",
    "descend",
    "ascend",
    "make_diamond_pickaxe",
    "make_diamond_sword",
    "make_iron_armour",
    "make_diamond_armour",
    "shoot_arrow",
    "make_arrow",
    "cast_spell",
    "place_torch",
    "drink_potion_red",
    "drink_potion_green",
    "drink_potion_blue",
    "drink_potion_pink",
    "drink_potion_cyan",
    "drink_potion_yellow",
    "read_book",
    "enchant_sword",
    "enchant_armour",
    "make_torch",
    "level_up_dexterity",
    "level_up_strength",
    "level_up_intelligence",
    "enchant_bow",
]


def policy_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_suite(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def failure_modes_for_result(result: dict[str, Any]) -> list[str]:
    details = result["reward_info"]["details"]
    modes: list[str] = []
    if int(details.get("invalid_action_count", 0)) > 0:
        modes.append("invalid_action")
    if details["outcome"] == "truncated":
        modes.append("truncated")
    if int(details.get("achievement_count", 0)) == 0:
        modes.append("no_achievements")
    if "collect_wood" not in details.get("achievements", []):
        modes.append("missed_collect_wood")
    return modes or ["progress"]


def _python_rollout_job(payload: tuple[str, int, str, int, bool]) -> dict[str, Any]:
    policy_path_s, seed, task_path, max_steps, include_trace = payload
    policy_path = Path(policy_path_s)
    candidate_fn = load_policy_module(policy_path)
    return rollout_code_policy(
        policy_path=policy_path,
        seed=seed,
        task_path=task_path,
        max_steps=max_steps,
        include_trace=include_trace,
        candidate_fn=candidate_fn,
        policy_engine_sim=False,
    )


def _init_rust_worker() -> None:
    global _WORKER_RUST_REPL
    ensure_rust_repl_binary()
    _WORKER_RUST_REPL = RustReplSession()


def _rust_rollout_job(payload: tuple[str, int, str, int, bool]) -> dict[str, Any]:
    global _WORKER_RUST_REPL
    if _WORKER_RUST_REPL is None:
        _init_rust_worker()
    policy_path_s, seed, task_path, max_steps, include_trace = payload
    policy_path = Path(policy_path_s)
    candidate_fn = _load_worker_policy(policy_path_s, policy_path)
    return rollout_code_policy_rust_repl(
        policy_path=policy_path,
        seed=seed,
        task_path=task_path,
        max_steps=max_steps,
        include_trace=include_trace,
        candidate_fn=candidate_fn,
        repl=_WORKER_RUST_REPL,
    )


def _load_worker_policy(policy_path_s: str, policy_path: Path) -> Any:
    candidate_fn = _WORKER_POLICY_CACHE.get(policy_path_s)
    if candidate_fn is None:
        candidate_fn = load_policy_module(policy_path)
        _WORKER_POLICY_CACHE[policy_path_s] = candidate_fn
    return candidate_fn


def _python_rollout_batch_job(
    payloads: list[tuple[str, int, str, int, bool]],
) -> list[tuple[int, dict[str, Any]]]:
    results: list[tuple[int, dict[str, Any]]] = []
    for policy_path_s, seed, task_path, max_steps, include_trace in payloads:
        policy_path = Path(policy_path_s)
        candidate_fn = _load_worker_policy(policy_path_s, policy_path)
        results.append(
            (
                seed,
                rollout_code_policy(
                    policy_path=policy_path,
                    seed=seed,
                    task_path=task_path,
                    max_steps=max_steps,
                    include_trace=include_trace,
                    candidate_fn=candidate_fn,
                    policy_engine_sim=False,
                ),
            )
        )
    return results


def _rust_rollout_batch_job(
    payloads: list[tuple[str, int, str, int, bool]],
) -> list[tuple[int, dict[str, Any]]]:
    global _WORKER_RUST_REPL
    if _WORKER_RUST_REPL is None:
        _init_rust_worker()
    results: list[tuple[int, dict[str, Any]]] = []
    for policy_path_s, seed, task_path, max_steps, include_trace in payloads:
        policy_path = Path(policy_path_s)
        candidate_fn = _load_worker_policy(policy_path_s, policy_path)
        results.append(
            (
                seed,
                rollout_code_policy_rust_repl(
                    policy_path=policy_path,
                    seed=seed,
                    task_path=task_path,
                    max_steps=max_steps,
                    include_trace=include_trace,
                    candidate_fn=candidate_fn,
                    repl=_WORKER_RUST_REPL,
                ),
            )
        )
    return results


def run_policy_sweep(
    *,
    policy_path: Path,
    suite_path: Path,
    output_path: Path,
    include_trace: bool = False,
    lane: str = "python",
    base_url: str = "http://127.0.0.1:8098",
    parallel: int = 1,
    summary_only: bool = False,
    progress: Callable[[int, int, int, float], None] | None = None,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    started = time.time()
    compile_check_policy(policy_path)
    policy_fn = load_policy_module(policy_path)
    suite = load_suite(suite_path)
    seeds = [int(seed) for seed in suite["seeds"]]
    task_path = str(suite.get("task_template", "tasks/policy_dev_template.json"))
    max_steps = int(
        max_steps_override if max_steps_override is not None else suite.get("max_steps", 80)
    )
    total = len(seeds)
    completed = 0

    def emit_progress(seed: int) -> None:
        nonlocal completed
        completed += 1
        if progress is not None:
            progress(completed, total, seed, time.time() - started)

    if lane == "python":
        job_payloads = [
            (str(policy_path), seed, task_path, max_steps, include_trace) for seed in seeds
        ]

        def rollout_fn(seed: int) -> dict[str, Any]:
            payload = (str(policy_path), seed, task_path, max_steps, include_trace)
            return _python_rollout_job(payload)

    elif lane == "rust":
        ensure_rust_repl_binary()
        job_payloads = [
            (str(policy_path), seed, task_path, max_steps, include_trace) for seed in seeds
        ]

        def rollout_fn(seed: int) -> dict[str, Any]:
            payload = (str(policy_path), seed, task_path, max_steps, include_trace)
            return _rust_rollout_job(payload)

    elif lane == "rust_http":
        rollout_fn = lambda seed: rollout_code_policy_http(
            policy_path=policy_path,
            seed=seed,
            task_path=task_path,
            max_steps=max_steps,
            include_trace=include_trace,
            candidate_fn=policy_fn,
            base_url=base_url,
        )
    else:
        raise ValueError(f"unsupported lane: {lane}")

    workers = max(1, int(parallel))
    use_process_pool = lane in {"python", "rust"} and workers > 1 and len(seeds) > 1
    executor_kind = "process" if use_process_pool else "thread"
    if workers == 1 or len(seeds) == 1:
        results = []
        for seed in seeds:
            results.append(rollout_fn(seed))
            emit_progress(seed)
    else:
        results = [None] * len(seeds)
        seed_index = {seed: idx for idx, seed in enumerate(seeds)}
        pool_cls = ProcessPoolExecutor if executor_kind == "process" else ThreadPoolExecutor
        pool_kwargs: dict[str, Any] = {"max_workers": workers}
        if lane == "rust":
            pool_kwargs["initializer"] = _init_rust_worker
        with pool_cls(**pool_kwargs) as pool:
            if lane in {"python", "rust"}:
                if max_steps >= 1000:
                    job_chunks = [[payload] for payload in job_payloads]
                else:
                    job_chunks = [
                        job_payloads[index::workers]
                        for index in range(min(workers, len(job_payloads)))
                    ]
                batch_job = _python_rollout_batch_job if lane == "python" else _rust_rollout_batch_job
                futures = {pool.submit(batch_job, chunk): chunk for chunk in job_chunks}
            else:
                futures = {pool.submit(rollout_fn, seed): seed for seed in seeds}
            for future in as_completed(futures):
                if lane in {"python", "rust"}:
                    for seed, result in future.result():
                        results[seed_index[seed]] = result
                        emit_progress(seed)
                else:
                    seed = futures[future]
                    results[seed_index[seed]] = future.result()
                    emit_progress(seed)
    rewards = [float(item["reward_info"]["outcome_reward"]) for item in results]
    achievement_counts = [
        int(item["reward_info"]["details"].get("achievement_count", 0)) for item in results
    ]
    achievement_frequency: Counter[str] = Counter()
    for item in results:
        achievement_frequency.update(item["reward_info"]["details"].get("achievements", []))
    failure_counts = Counter(mode for item in results for mode in failure_modes_for_result(item))
    unique_achievements = sorted(
        {
            achievement
            for item in results
            for achievement in item["reward_info"]["details"].get("achievements", [])
        }
    )
    report = {
        "schema": "gamebench.craftax.policy_sweep_summary.v1",
        "env_family": "craftax-singleplayer",
        "suite_id": str(suite["suite_id"]),
        "suite_path": str(suite_path),
        "max_steps": max_steps,
        "lane": lane,
        "engine_mode": "rust_repl" if lane == "rust" else "rust_http" if lane == "rust_http" else "python",
        "base_url": base_url if lane == "rust_http" else None,
        "policy_path": str(policy_path),
        "policy_sha256": policy_sha256(policy_path),
        "seeds": seeds,
        "n_seeds": len(seeds),
        "score": round(achievement_success_score(dict(achievement_frequency), len(seeds)), 4),
        "mean_reward": round(statistics.mean(rewards), 4) if rewards else 0.0,
        "reward_distribution": distribution_stats(rewards),
        "achievement_count_distribution": distribution_stats([float(v) for v in achievement_counts]),
        "episode_summaries": [
            {
                "seed": int(item["reward_info"]["details"].get("seed", seeds[index])),
                "reward": round(float(item["reward_info"]["outcome_reward"]), 4),
                "achievement_count": int(item["reward_info"]["details"].get("achievement_count", 0)),
                "achievements": sorted(item["reward_info"]["details"].get("achievements", [])),
            }
            for index, item in enumerate(results)
        ],
        "achievement_frequency": dict(sorted(achievement_frequency.items())),
        "unique_achievement_count": len(unique_achievements),
        "unique_achievements": unique_achievements,
        "invalid_action_count": sum(int(item["reward_info"]["details"].get("invalid_action_count", 0)) for item in results),
        "failure_mode_counts": dict(sorted(failure_counts.items())),
        "elapsed_s": round(time.time() - started, 3),
        "episodes": [] if summary_only else results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def rollout_code_policy_rust_repl(
    *,
    policy_path: Path,
    seed: int,
    task_path: str,
    max_steps: int,
    include_trace: bool,
    candidate_fn: Any,
    repl: RustReplSession,
) -> dict[str, Any]:
    task = _load_task(task_path, seed=seed)
    step_readout_mode = "full" if include_trace else "policy"
    latest = repl.reset(task=task, seed=seed, readout_mode=step_readout_mode)
    readout = latest["readout"]
    turns: list[dict[str, Any]] = []
    session: dict[str, Any] = {"rollout_id": f"rust-repl-{seed}", "ply": 0, "lane": "rust"}
    ply = 0
    while not latest.get("terminated", False) and not latest.get("truncated", False) and ply < max_steps:
        session["ply"] = ply
        decision = candidate_fn(
            observation_text=readout["observation_text"],
            session=session,
            valid_actions=readout.get("valid_actions", RUST_REPL_VALID_ACTIONS),
            engine=None,
            seed=seed,
            ply=ply,
            readout=readout,
        )
        raw_actions = decision.get("actions") or ["noop"]
        actions = [str(action) for action in raw_actions]
        if not actions:
            actions = ["noop"]
        actions = actions[: max(1, min(MAX_RUST_REPL_ACTION_BATCH, max_steps - ply))]
        action = actions[0]
        if include_trace or len(actions) == 1:
            latest = repl.step(action, readout_mode=step_readout_mode)
            steps_executed = 1
        else:
            latest = repl.steps(actions, readout_mode=step_readout_mode)
            steps_executed = int(latest.get("steps_executed", len(actions)))
        readout = latest["readout"]
        if include_trace:
            private = readout["private"]
            turns.append(
                {
                    "ply": ply,
                    "action": action,
                    "policy_reason": decision.get("policy_reason", ""),
                    "reward_last": private.get("reward_last", 0.0),
                    "reward_total": private.get("total_reward", 0.0),
                    "achievements": sorted(private.get("achievements", [])),
                    "grid_hash": readout["grid_hash"],
                }
            )
        ply += steps_executed
    final_readout = readout if include_trace else repl.readout(readout_mode="full")["readout"]
    private = final_readout["private"]
    achievements = sorted(private.get("achievements", []))
    outcome = "success" if achievements else "truncated" if latest.get("truncated", False) or ply >= max_steps else "failure"
    return {
        "trace_correlation_id": f"craftax-codepolicy-rust-repl-{seed}",
        "rollout_id": session["rollout_id"],
        "success_status": "success",
        "status_detail": outcome,
        "reward_info": {
            "outcome_reward": float(private.get("total_reward", 0.0)),
            "details": {
                "seed": seed,
                "task_id": final_readout.get("task_id", "unknown"),
                "outcome": outcome,
                "steps": int(private.get("step_index", ply)),
                "invalid_action_count": int(private.get("invalid_action_count", 0)),
                "achievement_count": len(achievements),
                "achievements": achievements,
                "policy_path": str(policy_path.expanduser().resolve()),
                "lane": "rust",
                "engine_mode": "rust_repl",
                "engine_clone": False,
            },
        },
        "state": {"public": final_readout["public"], "private": private},
        "artifact": [{"artifact_type": "turns", "turns": turns}],
    }


def rollout_code_policy_http(
    *,
    policy_path: Path,
    seed: int,
    task_path: str,
    max_steps: int,
    include_trace: bool,
    candidate_fn: Any,
    base_url: str,
) -> dict[str, Any]:
    task = _load_task(task_path, seed=seed)
    http = _http_session(base_url)
    root = http.request_json("POST", "/rollouts", {"task": task, "seed": seed})
    rollout_id = str(root["rollout_id"])
    turns: list[dict[str, Any]] = []
    readout = root["readout"]
    latest = root
    session: dict[str, Any] = {"rollout_id": rollout_id, "ply": 0, "lane": "rust"}
    ply = 0
    while not latest.get("terminated", False) and not latest.get("truncated", False) and ply < max_steps:
        session["ply"] = ply
        decision = candidate_fn(
            observation_text=readout["observation_text"],
            session=session,
            valid_actions=readout.get("valid_actions", []),
            engine=None,
            seed=seed,
            ply=ply,
            readout=readout,
        )
        raw_actions = decision.get("actions") or ["noop"]
        action = str(raw_actions[0])
        latest = http.request_json("POST", f"/rollouts/{rollout_id}/step", {"action": action})
        readout = latest["readout"]
        if include_trace:
            step_readout = readout
            private = step_readout["private"]
            turns.append(
                {
                    "ply": ply,
                    "action": action,
                    "policy_reason": decision.get("policy_reason", ""),
                    "reward_last": private.get("reward_last", 0.0),
                    "reward_total": private.get("total_reward", 0.0),
                    "achievements": sorted(private.get("achievements", [])),
                    "grid_hash": step_readout["grid_hash"],
                }
            )
        ply += 1
    final_readout = latest["readout"]
    private = final_readout["private"]
    achievements = sorted(private.get("achievements", []))
    outcome = "success" if achievements else "truncated" if latest.get("truncated", False) or ply >= max_steps else "failure"
    try:
        http.request_json("DELETE", f"/rollouts/{rollout_id}")
    except RuntimeError:
        pass
    result: dict[str, Any] = {
        "trace_correlation_id": f"craftax-codepolicy-rust-{seed}",
        "rollout_id": rollout_id,
        "success_status": "success",
        "status_detail": outcome,
        "reward_info": {
            "outcome_reward": float(private.get("total_reward", 0.0)),
            "details": {
                "seed": seed,
                "task_id": final_readout.get("task_id", "unknown"),
                "outcome": outcome,
                "steps": int(private.get("step_index", ply)),
                "invalid_action_count": int(private.get("invalid_action_count", 0)),
                "achievement_count": len(achievements),
                "achievements": achievements,
                "policy_path": str(policy_path.expanduser().resolve()),
                "lane": "rust_http",
                "engine_clone": False,
            },
        },
        "state": {"public": final_readout["public"], "private": private},
        "artifact": [{"artifact_type": "turns", "turns": turns}],
    }
    if include_trace:
        events = http.request_json("GET", f"/rollouts/{rollout_id}/event_log")
        result["events"] = events.get("legacy", [])
        result["nev"] = events.get("events", [])
    return result


class _HttpSession:
    """One keep-alive HTTP connection per thread (large win for per-step rollouts)."""

    def __init__(self, base_url: str) -> None:
        parsed = urllib.parse.urlparse(base_url.rstrip("/"))
        self.base_url = base_url.rstrip("/")
        self.host = parsed.hostname or "127.0.0.1"
        if parsed.port is not None:
            self.port = int(parsed.port)
        elif parsed.scheme == "https":
            self.port = 443
        else:
            self.port = 80
        self._conn: http.client.HTTPConnection | None = None

    def _connect(self) -> http.client.HTTPConnection:
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
        self._conn = http.client.HTTPConnection(self.host, self.port, timeout=120)
        return self._conn

    def request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload)
        headers = {"Content-Type": "application/json", "Connection": "keep-alive"}
        last_error: Exception | None = None
        for attempt in range(2):
            conn = self._conn if self._conn is not None else self._connect()
            try:
                conn.request(method, path, body=body, headers=headers)
                response = conn.getresponse()
                raw = response.read()
                if response.status >= 400:
                    text = raw.decode("utf-8", errors="replace")
                    raise RuntimeError(f"HTTP {response.status} for {method} {path}: {text}")
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
            except RuntimeError:
                raise
            except (http.client.HTTPException, ConnectionError, TimeoutError, OSError) as error:
                last_error = error
                self._connect()
                if attempt == 0:
                    continue
                raise
        if last_error is not None:
            raise last_error
        return {}


_thread_http = threading.local()


def _http_session(base_url: str) -> _HttpSession:
    session = getattr(_thread_http, "session", None)
    if session is None or session.base_url != base_url.rstrip("/"):
        session = _HttpSession(base_url)
        _thread_http.session = session
    return session


def _http_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _http_session(base_url).request_json(method, path, payload)


def _load_task(task_path: str, *, seed: int) -> dict[str, Any]:
    task = json.loads((TASK_DIR / task_path).read_text())
    task["seed"] = seed
    task["task_id"] = f"{task.get('task_id', 'craftax_policy_dev')}_{seed}"
    return task


def default_parallel_workers() -> int:
    cpu = os.cpu_count() or 8
    return max(4, min(32, cpu * 2))


def distribution_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "min": 0.0,
            "p25": 0.0,
            "median": 0.0,
            "mean": 0.0,
            "p75": 0.0,
            "max": 0.0,
            "stdev": 0.0,
        }
    ordered = sorted(float(value) for value in values)
    count = len(ordered)

    def quantile(probability: float) -> float:
        if count == 1:
            return ordered[0]
        index = probability * (count - 1)
        lower = int(index)
        upper = min(lower + 1, count - 1)
        weight = index - lower
        return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

    return {
        "count": count,
        "min": round(ordered[0], 4),
        "p25": round(quantile(0.25), 4),
        "median": round(statistics.median(ordered), 4),
        "mean": round(statistics.mean(ordered), 4),
        "p75": round(quantile(0.75), 4),
        "max": round(ordered[-1], 4),
        "stdev": round(statistics.pstdev(ordered), 4) if count > 1 else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Craftax code-policy sweep.")
    parser.add_argument("--policy", default=str(TASK_DIR / "policies" / "heuristic_baseline.py"))
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--include-trace", action="store_true")
    parser.add_argument("--lane", choices=["python", "rust", "rust_http"], default="python")
    parser.add_argument("--base-url", default="http://127.0.0.1:8098")
    parser.add_argument(
        "--rust-http",
        action="store_true",
        help="Use legacy Rust HTTP lane (slow; per-step POST /rollouts/{id}/step)",
    )
    parser.add_argument("--parallel", type=int, default=1, help="Concurrent rollouts (Rust HTTP lane)")
    parser.add_argument("--summary-only", action="store_true", help="Omit per-episode traces from output JSON")
    args = parser.parse_args()
    report = run_policy_sweep(
        policy_path=Path(args.policy).expanduser().resolve(),
        suite_path=Path(args.suite).expanduser().resolve(),
        output_path=Path(args.output).expanduser().resolve(),
        include_trace=bool(args.include_trace),
        lane=str(args.lane),
        base_url=str(args.base_url),
        parallel=int(args.parallel),
        summary_only=bool(args.summary_only),
    )
    printable = {
        key: report[key]
        for key in (
            "suite_id",
            "score",
            "mean_reward",
            "unique_achievement_count",
            "unique_achievements",
            "achievement_frequency",
            "failure_mode_counts",
            "elapsed_s",
        )
    }
    print(json.dumps(printable, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
