#!/usr/bin/env python3
"""Run rogue-singleplayer exotic-cybernetics policy sweep (proxied 20k input-token budget)."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_DIR.parents[1]
for path in reversed((REPO_ROOT, TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared", TASK_DIR / "scripts")):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("GAMEBENCH_CYBERNETICS_ENV_LABEL", "Rogue symbolic policy")

from containers.exotic_cybernetics.rollout_exotic_cybernetics import rollout_exotic_cybernetics_episode
from exotic_cybernetics.config import BENCHMARK_FAMILY, ENV_FAMILY, INPUT_TOKEN_BUDGET, MAX_POLICY_COST_USD
from exotic_cybernetics.inference_proxy import proxy_base_url, start_inference_proxy, stop_inference_proxy


def load_suite(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def failure_modes_for_result(result: dict[str, Any]) -> list[str]:
    details = result["reward_info"]["details"]
    modes: list[str] = []
    cyber = details.get("cybernetics") or result.get("cybernetics") or {}
    if not cyber.get("budget_compliant", True):
        modes.append("token_budget_violation")
    if cyber.get("budget_exhausted"):
        modes.append("token_budget_exhausted")
    if cyber.get("cost_budget_exhausted"):
        modes.append("cost_budget_exhausted")
    return modes or ["progress"]


def distribution_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    n = len(ordered)

    def pct(p: float) -> float:
        idx = min(n - 1, max(0, int(p * (n - 1))))
        return round(ordered[idx], 4)

    return {
        "min": round(ordered[0], 4),
        "p25": pct(0.25),
        "median": pct(0.5),
        "mean": round(statistics.mean(ordered), 4),
        "p75": pct(0.75),
        "max": round(ordered[-1], 4),
        "stdev": round(statistics.pstdev(ordered), 4) if n > 1 else 0.0,
    }


def wait_for_proxy(base_url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"inference proxy not healthy at {base_url}")


def run_sweep(
    *,
    policy_path: Path,
    suite_path: Path,
    output_path: Path,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    suite = load_suite(suite_path)
    seeds = [int(seed) for seed in suite.get("seeds", [])]
    max_steps = int(max_steps_override if max_steps_override is not None else suite.get('max_steps', 80))
    started = time.time()
    results: list[dict[str, Any]] = []
    token_counts: list[float] = []
    llm_calls: list[float] = []
    cost_values: list[float] = []
    episode_seconds: list[float] = []

    task_path = str(suite.get("task_template", "tasks/policy_dev_template.json"))
    for seed in seeds:
        ep_started = time.perf_counter()
        episode = rollout_exotic_cybernetics_episode(
            policy_path=policy_path,
            seed=seed,
            task_path=task_path,
            max_steps=max_steps,
        )
        episode_seconds.append(time.perf_counter() - ep_started)
        results.append(episode)
        cyber = episode.get("cybernetics") or {}
        token_counts.append(float(cyber.get("prompt_tokens_consumed", 0)))
        llm_calls.append(float(cyber.get("llm_calls", 0)))
        cost_values.append(float(cyber.get("estimated_cost_usd", 0.0)))


    rewards = [float(item["reward_info"]["outcome_reward"]) for item in results]
    failure_counts = Counter(mode for item in results for mode in failure_modes_for_result(item))
    report = {
        "schema": "gamebench.rogue.exotic_cybernetics_sweep.v1",
        "benchmark_family": BENCHMARK_FAMILY,
        "env_family": ENV_FAMILY,
        "suite_id": str(suite.get("suite_id", "rogue_exotic_cybernetics")),
        "policy_path": str(policy_path),
        "max_steps": max_steps,
        "input_token_budget": INPUT_TOKEN_BUDGET,
        "max_policy_cost_usd": MAX_POLICY_COST_USD,
        "n_seeds": len(results),
        "score": round(statistics.mean(rewards), 4) if rewards else 0.0,
        "mean_reward": round(statistics.mean(rewards), 4) if rewards else 0.0,
        "reward_distribution": distribution_stats(rewards),
        "prompt_tokens_distribution": distribution_stats(token_counts),
        "llm_calls_distribution": distribution_stats(llm_calls),
        "policy_cost_distribution": distribution_stats(cost_values),
        "episode_seconds_distribution": distribution_stats(episode_seconds),
        "total_wall_s": round(sum(episode_seconds), 3),
        "mean_episode_s": round(statistics.mean(episode_seconds), 4) if episode_seconds else 0.0,
        "failure_mode_counts": dict(sorted(failure_counts.items())),
        "episodes": results,
        "elapsed_s": round(time.time() - started, 3),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="rogue-singleplayer exotic cybernetics sweep.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "exotic_cybernetics" / "eval_dev_v10.json"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--mock", action="store_true", help="Use deterministic mock steering")
    args = parser.parse_args()

    if args.mock:
        os.environ["GAMEBENCH_CYBERNETICS_MOCK"] = "1"

    base = proxy_base_url()
    os.environ["GAMEBENCH_INFERENCE_PROXY_URL"] = base
    start_inference_proxy()
    wait_for_proxy(base)
    try:
        report = run_sweep(
            policy_path=Path(args.policy).expanduser().resolve(),
            suite_path=Path(args.suite).expanduser().resolve(),
            output_path=Path(args.output).expanduser().resolve(),
            max_steps_override=args.max_steps,
        )
        print(json.dumps({k: report[k] for k in ("score", "mean_reward", "prompt_tokens_distribution", "llm_calls_distribution", "failure_mode_counts")}, indent=2))
    finally:
        stop_inference_proxy()


if __name__ == "__main__":
    main()
