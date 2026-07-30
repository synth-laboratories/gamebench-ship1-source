#!/usr/bin/env python3
"""Run deterministic Crafter code-policy sweeps (rust HTTP gold by default)."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Protocol


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from http_rollout import HttpRolloutEngine
from scoring import achievement_frequency_from_sets, achievement_success_score
from task_resolve import load_task_path, resolve_task

try:
    from observations import termination_from_state
except ImportError:
    from gold_python.observations import termination_from_state


PolicyFn = Callable[..., dict[str, Any]]
DEFAULT_RUST_PORT = 8095


def _python_engine_cls() -> type[Any]:
    from engine import CrafterEngine

    return CrafterEngine


class EngineLike(Protocol):
    def symbolic_readout(self) -> dict[str, Any]: ...
    def valid_actions(self) -> list[str]: ...
    def step(self, action: str) -> None: ...
    def clone_for_sim(self) -> Any: ...
    @property
    def private(self) -> Any: ...


def policy_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_policy_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"crafter_policy_{path.parent.name}_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot import policy: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compile_check_policy(path: Path) -> None:
    module = load_policy_module(path)
    fn = getattr(module, "choose_actions", None)
    if not callable(fn):
        raise ValueError(f"policy has no choose_actions: {path}")
    response = fn(
        observation_text="step=0\nvalid_actions=['noop']",
        session={},
        valid_actions=["noop"],
        min_action_batch_size=1,
        target_action_batch_size=1,
        max_action_batch_size=1,
        readout={"observation": {}, "front_tile": {}, "valid_actions": ["noop"]},
    )
    if not isinstance(response, dict) or "actions" not in response:
        raise ValueError(f"policy choose_actions must return a dict with actions: {path}")


def load_suite(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def task_for_suite_seed(suite: dict[str, Any], seed: int) -> dict[str, Any]:
    template_path = TASK_DIR / str(suite["task_template"])
    task = load_task_path(template_path)
    task.setdefault("world", {})
    task["world"]["use_default"] = suite.get("world_default", task["world"].get("use_default", "policy_dev_small"))
    task["world"]["seed"] = seed
    task["world"]["max_steps"] = int(suite.get("max_steps", task["world"].get("max_steps", 120)))
    task["rules"] = {"base": suite.get("rules_default", "no_homeostasis")}
    task["task_id"] = f"{task.get('task_id', 'crafter_policy_dev')}_{seed}"
    task["scenario_id"] = f"{task.get('scenario_id', 'crafter_policy_dev')}_{seed}"
    return task


def failure_modes_for_achievements(achievements: set[str]) -> list[str]:
    modes: list[str] = []
    if "collect_wood" not in achievements:
        modes.append("missed_collect_wood")
    if "collect_wood" in achievements and "place_table" not in achievements:
        modes.append("stalled_before_place_table")
    if "place_table" in achievements and "make_wood_pickaxe" not in achievements:
        modes.append("stalled_before_wood_pickaxe")
    if "make_wood_pickaxe" in achievements and "collect_stone" not in achievements:
        modes.append("stalled_before_stone")
    if "collect_stone" in achievements and "make_stone_pickaxe" not in achievements:
        modes.append("stalled_before_stone_pickaxe")
    return modes


def merge_int_counts(target: dict[str, int], source: dict[str, Any]) -> None:
    for key, value in source.items():
        target[str(key)] = target.get(str(key), 0) + int(value)


def merge_float_counts(target: dict[str, float], source: dict[str, Any]) -> None:
    for key, value in source.items():
        target[str(key)] = target.get(str(key), 0.0) + float(value)


def make_engine(*, engine_lane: str, base_url: str | None, task: dict[str, Any], seed: int) -> EngineLike:
    if engine_lane == "python":
        CrafterEngine = _python_engine_cls()
        engine = CrafterEngine()
        engine.reset(resolve_task(task))
        return engine
    if not base_url:
        raise ValueError("base_url required for rust engine lane")
    client = HttpRolloutEngine(base_url)
    client.reset(task, seed=seed)
    return client


def wait_for_health(base_url: str, timeout_s: float = 120.0) -> None:
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=2) as response:
                payload = json.loads(response.read())
                if payload.get("ok"):
                    return
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(0.2)
    raise RuntimeError(f"service not healthy: {base_url}")


def pick_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def spawn_service(engine_lane: str, port: int | None = None) -> tuple[subprocess.Popen[Any], str]:
    if engine_lane != "rust":
        raise ValueError(f"spawn_service only supports rust lane, got {engine_lane!r}")
    bind_port = port or pick_free_port()
    base_url = f"http://127.0.0.1:{bind_port}"
    proc = subprocess.Popen(
        [
            "cargo",
            "run",
            "--release",
            "--quiet",
            "--manifest-path",
            str(TASK_DIR / "gold_rust" / "Cargo.toml"),
            "--bin",
            "crafter_gold",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(bind_port),
        ],
        cwd=str(TASK_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_for_health(base_url, timeout_s=180.0)
    return proc, base_url


def run_episode(
    *,
    policy_path: Path,
    seed: int,
    suite: dict[str, Any],
    engine_lane: str,
    base_url: str | None,
    include_trace: bool = False,
    record_state_action_trace: bool = False,
    policy_fn: PolicyFn | None = None,
    use_sim_engine: bool = False,
) -> dict[str, Any]:
    if policy_fn is None:
        policy_fn = getattr(load_policy_module(policy_path), "choose_actions")
    task = task_for_suite_seed(suite, seed)
    engine = make_engine(engine_lane=engine_lane, base_url=base_url, task=task, seed=seed)
    max_steps = int(suite.get("max_steps", 120))
    session: dict[str, Any] = {}
    action_history: list[str] = []
    state_action_trace: list[dict[str, Any]] = []
    if record_state_action_trace:
        from policy_puzzle_trace import state_action_transition
    while (
        not engine.private.terminated
        and not engine.private.truncated
        and engine.private.step_index < max_steps
    ):
        readout = engine.symbolic_readout()
        sim_engine = engine.clone_for_sim() if use_sim_engine else None
        response = policy_fn(
            observation_text=readout.get("observation_text", ""),
            session=session,
            action_history=action_history,
            action_history_names=action_history,
            valid_actions=engine.valid_actions(),
            min_action_batch_size=1,
            target_action_batch_size=5,
            max_action_batch_size=8,
            engine=sim_engine,
            readout=readout,
        )
        if not isinstance(response, dict):
            raise ValueError(f"policy returned non-dict response for seed {seed}")
        session = dict(response.get("session") or session)
        actions = list(response.get("actions") or ["noop"])
        if not actions:
            actions = ["noop"]
        for action in actions:
            if engine.private.terminated or engine.private.truncated:
                break
            if record_state_action_trace:
                state_action_trace.append(state_action_transition(readout=readout, action=str(action)))
            engine.step(str(action))
            action_history.append(str(action))
    unlocked = set(engine.private.achievements)
    failure_modes = failure_modes_for_achievements(unlocked)
    if engine.private.done_reason == "death":
        failure_modes.append("player_death")
    final_readout = engine.symbolic_readout()
    if engine_lane == "python":
        from observations import summarize_events

        event_summary = summarize_events(engine.nev.export())
    else:
        event_summary = dict(final_readout.get("event_summary") or {})
        event_summary.setdefault("event_kind_counts", {})
        event_summary.setdefault("transition_counts", {})
        event_summary.setdefault("action_counts", {})
        event_summary.setdefault("reward_source_totals", {})
        event_summary.setdefault("reward_component_totals", {})
    result: dict[str, Any] = {
        "schema": "gamebench.crafter.policy_episode.v1",
        "seed": seed,
        "task_id": engine.private.task_id,
        "config_hash": engine.private.config_hash,
        "engine_lane": engine_lane,
        "steps": engine.private.step_index,
        "terminated": engine.private.terminated,
        "truncated": engine.private.truncated,
        "done_reason": engine.private.done_reason,
        "reward": engine.private.total_reward,
        "achievements": sorted(unlocked),
        "achievement_count": len(unlocked),
        "failure_modes": failure_modes,
        "event_summary": event_summary,
        "event_kind_counts": event_summary.get("event_kind_counts", {}),
        "transition_counts": event_summary.get("transition_counts", {}),
        "action_counts": event_summary.get("action_counts", {}),
        "reward_source_totals": event_summary.get("reward_source_totals", {}),
        "reward_component_totals": event_summary.get("reward_component_totals", {}),
        "final_readout": final_readout,
    }
    private_payload = (
        dict(final_readout.get("private") or {})
        if isinstance(final_readout.get("private"), dict)
        else engine.private.to_dict()
        if hasattr(engine.private, "to_dict")
        else {}
    )
    termination = termination_from_state(private=private_payload, event_summary=event_summary)
    if termination is not None:
        result["termination"] = termination
    if include_trace and engine_lane == "python":
        result["nev"] = engine.nev.export()
        result["legacy_events"] = engine.nev.legacy_strings()
    if record_state_action_trace:
        result["state_action_trace"] = state_action_trace
    return result


def _aggregate_episode_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    unlocked_sets = [set(result["achievements"]) for result in results]
    frequency = achievement_frequency_from_sets(unlocked_sets)
    score = achievement_success_score(frequency, len(results))
    rewards = [float(result["reward"]) for result in results]
    failure_mode_counts: dict[str, int] = {}
    event_kind_counts: dict[str, int] = {}
    transition_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    reward_source_totals: dict[str, float] = {}
    reward_component_totals: dict[str, float] = {}
    terminal_counts: dict[str, int] = {}
    for result in results:
        for mode in result["failure_modes"]:
            failure_mode_counts[mode] = failure_mode_counts.get(mode, 0) + 1
        merge_int_counts(event_kind_counts, result["event_kind_counts"])
        merge_int_counts(transition_counts, result["transition_counts"])
        merge_int_counts(action_counts, result["action_counts"])
        merge_float_counts(reward_source_totals, result["reward_source_totals"])
        merge_float_counts(reward_component_totals, result["reward_component_totals"])
        terminal = result["event_summary"].get("terminal")
        termination = result.get("termination") or {}
        reason = str(
            termination.get("reason")
            or (terminal or {}).get("reason")
            or result.get("done_reason")
            or "unfinished"
        )
        terminal_counts[reason] = terminal_counts.get(reason, 0) + 1
    return {
        "episode_count": len(results),
        "score": score,
        "achievement_frequency": frequency,
        "failure_mode_counts": dict(sorted(failure_mode_counts.items())),
        "event_kind_counts": dict(sorted(event_kind_counts.items())),
        "transition_counts": dict(sorted(transition_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "reward_source_totals": {key: float(value) for key, value in sorted(reward_source_totals.items())},
        "reward_component_totals": {key: float(value) for key, value in sorted(reward_component_totals.items())},
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "mean_reward": statistics.mean(rewards) if rewards else 0.0,
        "episodes": results,
    }


def _run_seed_batch(
    *,
    seeds: list[int],
    policy_path: Path,
    suite: dict[str, Any],
    engine_lane: str,
    base_url: str | None,
    include_trace: bool,
    policy_fn: PolicyFn | None,
    use_sim_engine: bool,
    workers: int,
    parallelism: str,
) -> list[dict[str, Any]]:
    if not seeds:
        return []
    worker_count = min(max(1, workers), max(1, len(seeds)))
    worker_count = _apply_rollout_worker_cap(worker_count)
    if worker_count <= 1:
        return [
            run_episode(
                policy_path=policy_path,
                seed=seed,
                suite=suite,
                engine_lane=engine_lane,
                base_url=base_url,
                include_trace=include_trace,
                policy_fn=policy_fn,
                use_sim_engine=use_sim_engine,
            )
            for seed in seeds
        ]
    use_process_pool = parallelism == "process" or (parallelism == "auto" and engine_lane == "python")
    executor_cls = ProcessPoolExecutor if use_process_pool else ThreadPoolExecutor
    worker_policy_fn = None if use_process_pool else policy_fn
    results: list[dict[str, Any]] = []
    with executor_cls(max_workers=worker_count) as pool:
        futures = [
            pool.submit(
                run_episode,
                policy_path=policy_path,
                seed=seed,
                suite=suite,
                engine_lane=engine_lane,
                base_url=base_url,
                include_trace=include_trace,
                policy_fn=worker_policy_fn,
                use_sim_engine=use_sim_engine,
            )
            for seed in seeds
        ]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: int(item["seed"]))
    return results


ROLLOUT_WORKER_CAP_ENV = "GAMEBENCH_ROLLOUT_MAX_WORKERS"


def _apply_rollout_worker_cap(worker_count: int) -> int:
    """Clamp rollout workers to GAMEBENCH_ROLLOUT_MAX_WORKERS if set.

    A per-env-instance ceiling on rollout parallelism. When several SMR runs share
    one host, each Crafter env instance is core-bound (the rollout fans across this
    threadpool), so the conservation law is
    (concurrent env-heavy lanes) x (workers per lane) ~= usable cores. Capping each
    instance lets the operator keep that product at or below the core budget;
    `capacity probe` recommends the value. Unset or non-positive leaves the
    CLI-chosen count unchanged.
    """
    raw = os.environ.get(ROLLOUT_WORKER_CAP_ENV)
    if not raw:
        return worker_count
    try:
        cap = int(raw)
    except ValueError:
        return worker_count
    if cap <= 0:
        return worker_count
    return min(worker_count, cap)


def run_policy_sweep(
    *,
    policy_path: Path,
    suite_path: Path,
    output_path: Path,
    engine_lane: str = "rust",
    service_url: str | None = None,
    workers: int = 1,
    include_trace: bool = False,
    parallelism: str = "auto",
    include_holdout: bool = True,
) -> dict[str, Any]:
    started = time.time()
    compile_check_policy(policy_path)
    policy_module = load_policy_module(policy_path)
    policy_fn = getattr(policy_module, "choose_actions")
    use_sim_engine = bool(getattr(policy_module, "USES_SIM_ENGINE", False))
    suite = load_suite(suite_path)
    seeds = [int(seed) for seed in suite["seeds"]]

    proc: subprocess.Popen[Any] | None = None
    base_url = service_url
    if engine_lane == "rust" and not base_url:
        port = int(os.environ.get("GAMEBENCH_CRAFTER_RUST_PORT", "0")) or None
        proc, base_url = spawn_service("rust", port=port)

    try:
        worker_count = min(max(1, workers), max(1, len(seeds)))
        results = _run_seed_batch(
            seeds=seeds,
            policy_path=policy_path,
            suite=suite,
            engine_lane=engine_lane,
            base_url=base_url,
            include_trace=include_trace,
            policy_fn=policy_fn,
            use_sim_engine=use_sim_engine,
            workers=workers,
            parallelism=parallelism,
        )
        dev_summary = _aggregate_episode_results(results)
        holdout_seeds = [int(seed) for seed in suite.get("holdout_seeds") or []]
        holdout_summary: dict[str, Any] | None = None
        if include_holdout and holdout_seeds:
            holdout_results = _run_seed_batch(
                seeds=holdout_seeds,
                policy_path=policy_path,
                suite=suite,
                engine_lane=engine_lane,
                base_url=base_url,
                include_trace=include_trace,
                policy_fn=policy_fn,
                use_sim_engine=use_sim_engine,
                workers=workers,
                parallelism=parallelism,
            )
            holdout_summary = _aggregate_episode_results(holdout_results)
        report = {
            "schema": "gamebench.crafter.policy_sweep.v1",
            "suite_id": suite["suite_id"],
            "policy_path": str(policy_path),
            "policy_sha256": policy_sha256(policy_path),
            "engine_lane": engine_lane,
            "service_url": base_url or "(python_in_process)",
            "seeds": seeds,
            "holdout_seeds": holdout_seeds,
            "episode_count": dev_summary["episode_count"],
            "parallelism": (
                "single"
                if worker_count <= 1
                else ("process" if parallelism == "process" or (parallelism == "auto" and engine_lane == "python") else "thread")
            ),
            "score": dev_summary["score"],
            "achievement_frequency": dev_summary["achievement_frequency"],
            "failure_mode_counts": dev_summary["failure_mode_counts"],
            "event_kind_counts": dev_summary["event_kind_counts"],
            "transition_counts": dev_summary["transition_counts"],
            "action_counts": dev_summary["action_counts"],
            "reward_source_totals": dev_summary["reward_source_totals"],
            "reward_component_totals": dev_summary["reward_component_totals"],
            "terminal_counts": dev_summary["terminal_counts"],
            "mean_reward": dev_summary["mean_reward"],
            "elapsed_s": round(time.time() - started, 3),
            "episodes": dev_summary["episodes"],
        }
        if holdout_summary is not None:
            report["holdout"] = {
                "seeds": holdout_seeds,
                "episode_count": holdout_summary["episode_count"],
                "score": holdout_summary["score"],
                "mean_reward": holdout_summary["mean_reward"],
                "achievement_frequency": holdout_summary["achievement_frequency"],
                "failure_mode_counts": holdout_summary["failure_mode_counts"],
                "episodes": holdout_summary["episodes"],
            }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Crafter policy over a fixed seed suite.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"))
    parser.add_argument("--engine-lane", choices=["python", "rust"], default="rust")
    parser.add_argument("--service-url", default="")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--parallelism", choices=["auto", "process", "thread"], default="auto")
    parser.add_argument("--output", required=True)
    parser.add_argument("--include-trace", action="store_true")
    parser.add_argument("--no-holdout", action="store_true", help="Skip holdout_seeds from suite JSON")
    parser.add_argument("--copy-policy-to", default="")
    args = parser.parse_args()
    policy_path = Path(args.policy).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    report = run_policy_sweep(
        policy_path=policy_path,
        suite_path=Path(args.suite).expanduser().resolve(),
        output_path=output_path,
        engine_lane=args.engine_lane,
        service_url=args.service_url or None,
        workers=max(1, int(args.workers)),
        include_trace=bool(args.include_trace),
        parallelism=args.parallelism,
        include_holdout=not bool(args.no_holdout),
    )
    if args.copy_policy_to:
        dest = Path(args.copy_policy_to).expanduser().resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(policy_path, dest)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "suite_id",
                    "policy_path",
                    "engine_lane",
                    "episode_count",
                    "score",
                    "achievement_frequency",
                    "mean_reward",
                    "holdout",
                    "elapsed_s",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
