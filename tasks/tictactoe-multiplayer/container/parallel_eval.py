#!/usr/bin/env python3
"""Parallel eval — N async POST /rollout (70b agent_0 vs 8b agent_1)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx

CONTAINER_ROOT = Path(__file__).resolve().parent
TASK_ROOT = CONTAINER_ROOT.parent
if str(TASK_ROOT) not in sys.path:
    sys.path.insert(0, str(TASK_ROOT))

from gold.board import AGENT_IDS

DEFAULT_AGENT_0_MODEL = "llama-3.3-70b-versatile"
DEFAULT_AGENT_1_MODEL = "llama-3.1-8b-instant"


def _default_seeds(count: int, start: int) -> list[int]:
    return list(range(start, start + count))


async def rollout_one(
    client: httpx.AsyncClient,
    base_url: str,
    seed: int,
    policy_config: dict[str, Any],
) -> dict[str, Any]:
    body = {
        "trace_correlation_id": f"parallel-mp-{seed}-{uuid.uuid4().hex[:8]}",
        "trial_id": f"ttt-mp-{seed}",
        "env": {
            "seed": seed,
            "config": {"scenario_id": f"groq_70b_vs_8b_{seed}"},
        },
        "policy": {"config": policy_config},
    }
    response = await client.post(f"{base_url.rstrip('/')}/rollout", json=body)
    response.raise_for_status()
    return response.json()


def summarize_parallel_results(
    results: list[dict[str, Any]],
    agent_0_model: str,
    agent_1_model: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    agent_0_wins = agent_1_wins = draws = unfinished = 0
    total_llm_calls = 0
    total_errors = 0

    for result in results:
        details = result.get("reward_info", {}).get("details", {})
        winner = str(details.get("winner", "unfinished"))
        if winner == AGENT_IDS[0]:
            agent_0_wins += 1
            outcome = "agent_0_win"
        elif winner == AGENT_IDS[1]:
            agent_1_wins += 1
            outcome = "agent_1_win"
        elif winner == "draw":
            draws += 1
            outcome = "draw"
        else:
            unfinished += 1
            outcome = "unfinished"

        llm_calls = int(details.get("llm_call_count", 0))
        errors = int(details.get("inference_error_count", 0))
        total_llm_calls += llm_calls
        total_errors += errors
        rows.append(
            {
                "seed": details.get("seed"),
                "outcome": outcome,
                "winner": winner,
                "agent_0_reward": details.get("agent_0_reward"),
                "agent_1_reward": details.get("agent_1_reward"),
                "llm_call_count": llm_calls,
                "inference_error_count": errors,
            }
        )

    n = len(results)
    return {
        "schema_version": "gamebench.parallel_rollout_eval.v1",
        "env_family": "tictactoe-multiplayer",
        "agent_0_model": agent_0_model,
        "agent_1_model": agent_1_model,
        "n_seeds": n,
        "summary": {
            "agent_0_wins": agent_0_wins,
            "agent_1_wins": agent_1_wins,
            "draws": draws,
            "unfinished": unfinished,
            "agent_0_win_rate": round(agent_0_wins / n, 4) if n else 0.0,
            "agent_1_win_rate": round(agent_1_wins / n, 4) if n else 0.0,
            "draw_rate": round(draws / n, 4) if n else 0.0,
            "total_llm_calls": total_llm_calls,
            "total_inference_errors": total_errors,
        },
        "rows": rows,
        "rollouts": results,
    }


def format_table(report: dict[str, Any]) -> str:
    lines = [
        f"agent_0={report['agent_0_model']} vs agent_1={report['agent_1_model']} n={report['n_seeds']}",
        (
            f"summary: agent_0_wins={report['summary']['agent_0_wins']} "
            f"agent_1_wins={report['summary']['agent_1_wins']} "
            f"draws={report['summary']['draws']} "
            f"agent_0_win_rate={report['summary']['agent_0_win_rate']} "
            f"agent_1_win_rate={report['summary']['agent_1_win_rate']}"
        ),
        "",
        "seed | outcome       | winner   | a0_r | a1_r | llm | err",
        "-----|---------------|----------|------|------|-----|----",
    ]
    for row in report["rows"]:
        lines.append(
            f"{row['seed']:>4} | {row['outcome']:<13} | {str(row['winner']):<8} | "
            f"{row['agent_0_reward']:>4} | {row['agent_1_reward']:>4} | "
            f"{row['llm_call_count']:>3} | {row['inference_error_count']:>3}"
        )
    return "\n".join(lines)


async def run_parallel(
    base_url: str,
    seeds: list[int],
    policy_config: dict[str, Any],
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=300.0) as client:
        health = await client.get(f"{base_url.rstrip('/')}/health")
        health.raise_for_status()
        results = await asyncio.gather(
            *[rollout_one(client, base_url, seed, policy_config) for seed in seeds]
        )
    agent_0_model = str(
        policy_config.get("agent_0", {}).get("model", DEFAULT_AGENT_0_MODEL)
    )
    agent_1_model = str(
        policy_config.get("agent_1", {}).get("model", DEFAULT_AGENT_1_MODEL)
    )
    return summarize_parallel_results(list(results), agent_0_model, agent_1_model)


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    policy_config: dict[str, Any] = {
        "agent_0": {
            "model": args.agent_0_model,
            "temperature": args.temperature,
        },
        "agent_1": {
            "model": args.agent_1_model,
            "temperature": args.temperature,
        },
    }
    seeds = _default_seeds(args.count, args.seed_start)
    return await run_parallel(args.base_url, seeds, policy_config)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parallel multiplayer Groq eval")
    parser.add_argument("--base-url", default=os.environ.get("CONTAINER_URL", "http://127.0.0.1:8093"))
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=201)
    parser.add_argument(
        "--agent-0-model",
        default=os.environ.get("GROQ_AGENT_0_MODEL", DEFAULT_AGENT_0_MODEL),
    )
    parser.add_argument(
        "--agent-1-model",
        default=os.environ.get("GROQ_AGENT_1_MODEL", DEFAULT_AGENT_1_MODEL),
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    report = asyncio.run(main_async(args))

    output_path = args.output
    if not output_path:
        reports_dir = CONTAINER_ROOT / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(reports_dir / "parallel_eval_70b_vs_8b.json")

    Path(output_path).write_text(json.dumps(report, indent=2) + "\n")
    print(format_table(report))
    print(f"\nwritten: {output_path}")


if __name__ == "__main__":
    main()
