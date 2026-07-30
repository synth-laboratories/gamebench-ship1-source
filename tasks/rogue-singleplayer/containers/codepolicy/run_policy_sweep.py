#!/usr/bin/env python3
"""Run Rogue code-policy scenario sweeps."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[2]
if str(TASK_ROOT) not in sys.path:
    sys.path.insert(0, str(TASK_ROOT))
if str(TASK_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(TASK_ROOT / "scripts"))

from containers.codepolicy.rollout_code_policy import task_root
from run_policy_sweep import run_policy_sweep


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--policy-path", default="")
    parser.add_argument("--suite", default=str(TASK_ROOT / "defaults" / "policy_sweep" / "policy_dev_v2.json"))
    parser.add_argument("--include-trace", action="store_true")
    args = parser.parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    policy_path = Path(args.policy_path).expanduser().resolve() if args.policy_path else task_root() / "containers" / "codepolicy" / "heuristic_policy.py"
    report = run_policy_sweep(
        policy_path=policy_path,
        suite_path=Path(args.suite).expanduser().resolve(),
        output_path=output_dir / "summary.json",
        include_trace=bool(args.include_trace),
    )
    print(json.dumps({key: report[key] for key in ("suite_id", "score_metric", "score", "success_rate", "mean_reward", "mean_scout_score", "mean_synth_shaped_reward", "elapsed_s")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
