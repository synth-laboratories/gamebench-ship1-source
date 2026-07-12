#!/usr/bin/env python3
"""Run rogue-singleplayer exotic-cybernetics reference evals."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_DIR.parents[1]
for path in reversed((REPO_ROOT, TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared", TASK_DIR / "scripts")):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("GAMEBENCH_CYBERNETICS_ENV_LABEL", "Rogue symbolic policy")

from exotic_cybernetics.config import BENCHMARK_FAMILY, INPUT_TOKEN_BUDGET, STEER_PROVIDER, steer_model
from exotic_cybernetics.inference_proxy import proxy_base_url, start_inference_proxy, stop_inference_proxy
from run_exotic_cybernetics_sweep import run_sweep, wait_for_proxy

REFERENCE_POLICIES = {
    "pure_code_bridge": TASK_DIR / "exotic_cybernetics" / "reference" / "pure_code_bridge" / "heuristic_policy.py",
    "sparse_governor": TASK_DIR / "exotic_cybernetics" / "reference" / "sparse_governor" / "heuristic_policy.py",
}
DEFAULT_POLICIES = ("pure_code_bridge", "sparse_governor")


def main() -> None:
    parser = argparse.ArgumentParser(description="rogue-singleplayer exotic cybernetics reference eval.")
    parser.add_argument("--suite", default=str(TASK_DIR / "defaults" / "exotic_cybernetics" / "eval_smoke_v2.json"))
    parser.add_argument("--output-root", default=str(TASK_DIR / "reports" / "exotic_cybernetics" / "latest"))
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--policies", nargs="*")
    args = parser.parse_args()

    policy_ids = list(args.policies) if args.policies else list(DEFAULT_POLICIES)
    if args.mock:
        os.environ["GAMEBENCH_CYBERNETICS_MOCK"] = "1"
    elif not (
        os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("GOOGLE_API_KEY", "").strip()
        or os.environ.get("GROQ_API_KEY", "").strip()
    ):
        print("API key missing; enabling GAMEBENCH_CYBERNETICS_MOCK=1", file=sys.stderr)
        os.environ["GAMEBENCH_CYBERNETICS_MOCK"] = "1"

    output_root = Path(args.output_root).expanduser().resolve()
    suite_path = Path(args.suite).expanduser().resolve()
    base = proxy_base_url()
    os.environ["GAMEBENCH_INFERENCE_PROXY_URL"] = base
    start_inference_proxy()
    wait_for_proxy(base)
    started = time.time()
    results: dict[str, Any] = {}
    try:
        for policy_id in policy_ids:
            policy_path = REFERENCE_POLICIES[policy_id]
            report = run_sweep(
                policy_path=policy_path,
                suite_path=suite_path,
                output_path=output_root / "policies" / policy_id / "summary.json",
            )
            results[policy_id] = {
                "score": report["score"],
                "mean_reward": report["mean_reward"],
                "prompt_tokens_distribution": report.get("prompt_tokens_distribution"),
                "llm_calls_distribution": report.get("llm_calls_distribution"),
                "failure_mode_counts": report.get("failure_mode_counts"),
            }
    finally:
        stop_inference_proxy()

    manifest = {
        "schema": "gamebench.rogue.exotic_cybernetics_report.v1",
        "benchmark_family": BENCHMARK_FAMILY,
        "model": steer_model(),
        "provider": STEER_PROVIDER,
        "input_token_budget": INPUT_TOKEN_BUDGET,
        "suite_id": json.loads(suite_path.read_text(encoding="utf-8")).get("suite_id"),
        "mock_mode": os.environ.get("GAMEBENCH_CYBERNETICS_MOCK", "") in {"1", "true", "yes"},
        "policies": results,
        "elapsed_s": round(time.time() - started, 3),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
