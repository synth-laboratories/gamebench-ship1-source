#!/usr/bin/env python3
"""Run deterministic Sokoban code-policy sweeps (python in-process or rust HTTP gold)."""

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Protocol


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gold_python.agent_io import format_agent_observation, parse_action_text
from gold_python.engine import SokobanEngine
from http_rollout import HttpRolloutEngine
from scoring import composite_policy_score, milestone_frequency_from_episodes
from task_resolve import load_task_path, resolve_task


PolicyFn = Callable[..., dict[str, Any]]
DEFAULT_PYTHON_PORT = 8092
DEFAULT_RUST_PORT = 8093


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
    spec = importlib.util.spec_from_file_location(f"sokoban_policy_{path.parent.name}_{path.stem}", path)
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
    engine = SokobanEngine()
    task = task_for_suite_seed(load_suite(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"), 101)
    engine.reset(resolve_task(task))
    readout = engine.symbolic_readout()
    response = fn(
        observation_text=format_agent_observation(readout)["observation_text"],
        session={},
        valid_actions=engine.valid_actions(),
        engine=engine.clone_for_sim(),
        readout=readout,
        seed=101,
        ply=0,
    )
    if not isinstance(response, dict) or "actions" not in response:
        raise ValueError(f"policy choose_actions must return a dict with actions: {path}")


def load_suite(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def task_for_suite_seed(suite: dict[str, Any], seed: int) -> dict[str, Any]:
    task = load_task_path(TASK_DIR / str(suite["task_template"]))
    task["seed"] = seed
    task.setdefault("map", {})
    task["map"]["use_default"] = suite.get("map_default", task["map"].get("use_default", "curriculum_easy"))
    task["map"]["seed"] = seed
    task["rules"] = {
        "base": suite.get("rules_default", "sparse_sokoban"),
        "overrides": {"max_steps": int(suite.get("max_steps", 120)), "errors": {"mode": "silent"}},
    }
    task["task_id"] = f"{task.get('task_id', 'sokoban_policy_dev')}_{seed}"
    return task


def failure_modes_for_episode(*, solved: bool, achievements: set[str], truncated: bool) -> list[str]:
    modes: list[str] = []
    if solved:
        return modes
    if truncated:
        modes.append("truncated")
    if "first_push" not in achievements:
        modes.append("no_push")
    elif "first_box_on_target" not in achievements:
        modes.append("no_box_on_target")
    elif not solved:
        modes.append("unsolved")
    return modes


def make_engine(*, engine_lane: str, base_url: str | None, task: dict[str, Any], seed: int) -> EngineLike:
    if engine_lane == "python":
        engine = SokobanEngine()
        engine.reset(resolve_task(task, seed_override=seed))
        return engine
    if not base_url:
        raise ValueError("base_url required for rust engine lane")
    client = HttpRolloutEngine(base_url)
    client.reset(task, seed=seed)
    return client


def run_episode(
    *,
    policy_path: Path,
    seed: int,
    suite: dict[str, Any],
    engine_lane: str,
    base_url: str | None,
    include_trace: bool = False,
    policy_fn: PolicyFn | None = None,
    use_sim_engine: bool = False,
) -> dict[str, Any]:
    if policy_fn is None:
        policy_fn = getattr(load_policy_module(policy_path), "choose_actions")
    task = task_for_suite_seed(suite, seed)
    engine = make_engine(engine_lane=engine_lane, base_url=base_url, task=task, seed=seed)
    max_steps = int(suite.get("max_steps", 120))
    session: dict[str, Any] = {}
    invalid_actions = 0
    ply = 0
    while not engine.private.terminated and not engine.private.truncated and ply < max_steps:
        readout = engine.symbolic_readout()
        sim_engine = engine.clone_for_sim() if use_sim_engine else None
        response = policy_fn(
            observation_text=format_agent_observation(readout)["observation_text"],
            session=session,
            valid_actions=engine.valid_actions(),
            engine=sim_engine,
            readout=readout,
            seed=seed,
            ply=ply,
        )
        if not isinstance(response, dict):
            raise ValueError(f"policy returned non-dict response for seed {seed}")
        session = dict(response.get("session") or session)
        raw_action = str((response.get("actions") or [""])[0])
        parsed = parse_action_text(raw_action, engine.valid_actions())
        if parsed.invalid_parse:
            invalid_actions += 1
        engine.step(parsed.action)
        ply += 1
    achievements = set(engine.private.achievements)
    solved = bool(engine.private.terminated)
    failure_modes = failure_modes_for_episode(
        solved=solved,
        achievements=achievements,
        truncated=bool(engine.private.truncated),
    )
    result: dict[str, Any] = {
        "schema": "gamebench.sokoban.policy_episode.v1",
        "seed": seed,
        "task_id": engine.private.task_id,
        "puzzle_id": engine.private.puzzle_id,
        "engine_lane": engine_lane,
        "steps": engine.private.step_index,
        "terminated": engine.private.terminated,
        "truncated": engine.private.truncated,
        "solved": solved,
        "reward": engine.private.total_reward,
        "achievements": sorted(achievements),
        "failure_modes": failure_modes,
        "invalid_action_count": invalid_actions,
        "final_readout": engine.symbolic_readout(),
    }
    if include_trace and isinstance(engine, SokobanEngine):
        result["nev"] = engine.nev.export()
        result["legacy_events"] = engine.nev.legacy_strings()
    return result


def wait_for_health(base_url: str, timeout_s: float = 45.0) -> None:
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


def spawn_service(engine_lane: str, port: int) -> subprocess.Popen[Any]:
    env = dict(os.environ)
    command = [
        sys.executable,
        str(TASK_DIR / "scripts" / "run_service.py"),
        "--lane",
        engine_lane,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_for_health(f"http://127.0.0.1:{port}")
    return proc


def run_policy_sweep(
    *,
    policy_path: Path,
    suite_path: Path,
    output_path: Path,
    engine_lane: str = "python",
    service_url: str | None = None,
    workers: int = 1,
    include_trace: bool = False,
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
        port = int(os.environ.get("GAMEBENCH_SOKOBAN_RUST_PORT", DEFAULT_RUST_PORT))
        proc = spawn_service("rust", port)
        base_url = f"http://127.0.0.1:{port}"

    try:
        results: list[dict[str, Any]] = []
        if workers <= 1:
            results = [
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
        else:
            with ThreadPoolExecutor(max_workers=min(workers, max(1, len(seeds)))) as pool:
                futures = [
                    pool.submit(
                        run_episode,
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
                for future in as_completed(futures):
                    results.append(future.result())
            results.sort(key=lambda item: int(item["seed"]))

        milestone_sets = [set(result["achievements"]) for result in results]
        frequency = milestone_frequency_from_episodes(milestone_sets)
        score = composite_policy_score(results)
        rewards = [float(result["reward"]) for result in results]
        failure_mode_counts: dict[str, int] = {}
        for result in results:
            for mode in result["failure_modes"]:
                failure_mode_counts[mode] = failure_mode_counts.get(mode, 0) + 1
        report = {
            "schema": "gamebench.sokoban.policy_sweep.v1",
            "suite_id": suite["suite_id"],
            "policy_path": str(policy_path),
            "policy_sha256": policy_sha256(policy_path),
            "engine_lane": engine_lane,
            "service_url": base_url or "(python_in_process)",
            "seeds": seeds,
            "episode_count": len(results),
            "score": score,
            "success_rate": round(sum(1 for item in results if item["solved"]) / len(results), 4) if results else 0.0,
            "milestone_frequency": frequency,
            "failure_mode_counts": dict(sorted(failure_mode_counts.items())),
            "mean_reward": statistics.mean(rewards) if rewards else 0.0,
            "elapsed_s": round(time.time() - started, 3),
            "episodes": results,
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
    parser = argparse.ArgumentParser(description="Run one Sokoban policy over a fixed seed suite.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "policy_sweep" / "policy_dev_v1.json"))
    parser.add_argument("--engine-lane", choices=["python", "rust"], default="python")
    parser.add_argument("--service-url", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", required=True)
    parser.add_argument("--include-trace", action="store_true")
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
    )
    if args.copy_policy_to:
        dest = Path(args.copy_policy_to).expanduser().resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(policy_path, dest)
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("suite_id", "policy_path", "engine_lane", "score", "success_rate", "mean_reward", "elapsed_s")
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
