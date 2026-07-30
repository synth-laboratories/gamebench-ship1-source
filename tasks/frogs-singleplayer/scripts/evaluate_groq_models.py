#!/usr/bin/env python3
"""Evaluate Groq chat models on FrogsGame agent rollouts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx


TASK_DIR = Path(__file__).resolve().parents[1]
for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gold_python.agent_io import format_agent_observation, parse_action_text
from gold_python.engine import FrogsEngine
from task_resolve import resolve_task


GROQ_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
]
MODEL_PRICES_USD_PER_MTOK = {
    "openai/gpt-oss-20b": {"input": 0.075, "output": 0.30},
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
}
SYSTEM_PROMPT = (
    "You are playing FrogsGame. Think privately, then reply with exactly one JSON action such as "
    '{"kind":"place_frog","row":0,"col":1} or {"kind":"submit"}.'
)


async def call_model(
    api_key: str,
    model: str,
    prompt: str,
    *,
    max_tokens: int,
    reasoning_effort: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{GROQ_URL}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        response.raise_for_status()
        payload = response.json()
    content = payload["choices"][0]["message"].get("content", "")
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return {
        "assistant_text": str(content),
        "usage": payload.get("usage", {}),
        "request_id": payload.get("id"),
        "latency_ms": latency_ms,
    }


async def run_rollout(
    api_key: str,
    model: str,
    task: dict[str, Any],
    seed: int,
    *,
    task_path: str,
    max_steps: int,
    max_tokens: int,
    reasoning_effort: str,
) -> dict[str, Any]:
    task = json.loads(json.dumps(task))
    task["seed"] = seed
    task["task_id"] = f"{task.get('task_id', 'frogs_policy_dev')}_{seed}"
    engine = FrogsEngine()
    engine.reset(resolve_task(task, seed_override=seed))
    turns: list[dict[str, Any]] = []
    action_history: list[dict[str, Any]] = []
    invalid = 0
    repairs = 0
    errors = 0
    latencies: list[float] = []
    prompt_tokens = 0
    completion_tokens = 0
    while engine.private.step_index < max_steps and not engine.private.terminated and not engine.private.truncated:
        readout = engine.symbolic_readout()
        observation = format_agent_observation(readout)
        prompt = "\n".join(
            [
                observation["observation_text"],
                "",
                f"Prior actions: {json.dumps(action_history)}",
            ]
        )
        assistant_text = ""
        error = None
        usage: dict[str, Any] = {}
        try:
            inference = await call_model(
                api_key,
                model,
                prompt,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
            )
            assistant_text = str(inference["assistant_text"])
            usage = dict(inference.get("usage", {}))
            latencies.append(float(inference["latency_ms"]))
            prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
            completion_tokens += int(usage.get("completion_tokens", 0) or 0)
        except Exception as exc:
            errors += 1
            error = str(exc)
        parsed = parse_action_text(assistant_text, observation["valid_actions"])
        if parsed.invalid_parse:
            invalid += 1
        if parsed.repaired:
            repairs += 1
        engine.step(parsed.action)
        action_history.append({"action": parsed.action, "ply": engine.private.step_index - 1})
        turns.append(
            {
                "ply": engine.private.step_index - 1,
                "action": parsed.to_dict(),
                "assistant_text": assistant_text,
                "error": error,
                "latency_ms": latencies[-1] if error is None and latencies else None,
                "usage": usage,
                "reward_total": engine.private.total_reward,
                "grid_hash": engine.symbolic_readout()["grid_hash"],
            }
        )
    outcome = "success" if engine.private.total_reward >= 1.0 else "truncated" if engine.private.truncated else "failure"
    return {
        "model": model,
        "seed": seed,
        "task_path": task_path,
        "task_id": engine.resolved.task_id if engine.resolved else "unknown",
        "outcome": outcome,
        "steps": engine.private.step_index,
        "reward": engine.private.total_reward,
        "invalid_action_count": invalid,
        "repair_count": repairs,
        "inference_error_count": errors,
        "latency_ms_mean": statistics.mean(latencies) if latencies else None,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": estimate_cost_usd(model, prompt_tokens, completion_tokens),
        "turns": turns,
        "events": engine.nev.legacy_strings(),
    }


def summarize(model: str, rollouts: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rollouts)
    successes = sum(1 for row in rollouts if row["outcome"] == "success")
    rewards = [float(row["reward"]) for row in rollouts]
    latencies = [float(row["latency_ms_mean"]) for row in rollouts if row["latency_ms_mean"] is not None]
    return {
        "model": model,
        "n": n,
        "successes": successes,
        "success_rate": round(successes / n, 4) if n else 0.0,
        "mean_reward": round(statistics.mean(rewards), 4) if rewards else 0.0,
        "mean_steps": round(statistics.mean([int(row["steps"]) for row in rollouts]), 2) if rollouts else 0,
        "invalid_action_count": sum(int(row["invalid_action_count"]) for row in rollouts),
        "repair_count": sum(int(row["repair_count"]) for row in rollouts),
        "inference_error_count": sum(int(row["inference_error_count"]) for row in rollouts),
        "latency_ms_mean": round(statistics.mean(latencies), 2) if latencies else None,
        "prompt_tokens": sum(int(row["prompt_tokens"]) for row in rollouts),
        "completion_tokens": sum(int(row["completion_tokens"]) for row in rollouts),
        "total_cost_usd": round(sum(float(row.get("estimated_cost_usd") or 0.0) for row in rollouts), 8),
        "mean_rollout_cost_usd": round(
            sum(float(row.get("estimated_cost_usd") or 0.0) for row in rollouts) / n,
            8,
        )
        if n
        else 0.0,
    }


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    prices = MODEL_PRICES_USD_PER_MTOK.get(model)
    if prices is None:
        return None
    return round(
        (prompt_tokens / 1_000_000) * prices["input"]
        + (completion_tokens / 1_000_000) * prices["output"],
        10,
    )


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GROQ_API_KEY is required")
    models = [part.strip() for part in args.models.split(",") if part.strip()] or DEFAULT_MODELS
    seeds = [int(part.strip()) for part in args.seeds.split(",") if part.strip()]
    task_paths = [part.strip() for part in args.tasks.split(",") if part.strip()]
    all_rollouts: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for model in models:
        rollouts = []
        for task_path in task_paths:
            task = json.loads((TASK_DIR / task_path).read_text())
            for seed in seeds:
                rollouts.append(
                    await run_rollout(
                        api_key,
                        model,
                        task,
                        seed,
                        task_path=task_path,
                        max_steps=args.max_steps,
                        max_tokens=args.max_tokens,
                        reasoning_effort=args.reasoning_effort,
                    )
                )
        summaries.append(summarize(model, rollouts))
        all_rollouts.extend(rollouts)
    report = {
        "schema": "gamebench.frogs.groq_model_eval.v1",
        "tasks": task_paths,
        "seeds": seeds,
        "max_steps": args.max_steps,
        "max_tokens": args.max_tokens,
        "reasoning_effort": args.reasoning_effort or None,
        "models": models,
        "summaries": summaries,
        "rollouts": all_rollouts,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--seeds", default="1,2,3,4")
    parser.add_argument("--tasks", default="tasks/policy_dev_template.json")
    parser.add_argument("--max-steps", type=int, default=16)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--output", default=str(TASK_DIR / "reports" / "groq_gpt_oss_eval.json"))
    args = parser.parse_args()
    report = asyncio.run(main_async(args))
    print(json.dumps({"summaries": report["summaries"], "output": args.output}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
