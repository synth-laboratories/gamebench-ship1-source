"""Harbor verifier: score code-policy hillclimb candidates in /workspace."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def write_result(path: Path, reward_path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    reward_path.write_text(f"{payload.get('harbor_reward', 0.0)}\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=os.environ.get("GAMEBENCH_WORKSPACE_ROOT", "/workspace"))
    parser.add_argument("--task-dir", default=os.environ.get("GAMEBENCH_TASK_DIR", ""))
    parser.add_argument("--output", default=os.environ.get("HARBOR_RESULT_JSON", "/logs/verifier/result.json"))
    parser.add_argument("--reward", default=os.environ.get("HARBOR_REWARD_PATH", "/logs/verifier/reward.txt"))
    parser.add_argument("--pass-delta", type=float, default=0.01)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    task_dir = Path(args.task_dir).resolve() if args.task_dir else workspace / "gamebench" / "tasks" / os.environ.get("GAMEBENCH_TASK", "")
    output_json = Path(args.output)
    reward_path = Path(args.reward)
    hillclimb = task_dir / "scripts" / "run_hillclimb.py"
    suite = os.environ.get("GAMEBENCH_POLICY_SUITE", str(task_dir / "defaults" / "policy_sweep" / "policy_dev_v1.json"))
    baseline = os.environ.get(
        "GAMEBENCH_POLICY_BASELINE",
        str(task_dir / "containers" / "codepolicy" / "heuristic_policy.py"),
    )
    task_id = os.environ.get("GAMEBENCH_TASK", "")
    candidate_root = workspace / "candidates" / os.environ.get(
        "CANDIDATE_SUBDIR",
        task_id.removesuffix("-singleplayer").removesuffix("-multiplayer"),
    )
    work_dir = workspace / ".harbor_hillclimb"

    if not hillclimb.exists():
        write_result(
            output_json,
            reward_path,
            {"error": f"missing hillclimb runner: {hillclimb}", "harbor_reward": 0.0},
        )
        return 1

    cmd = [
        sys.executable,
        str(hillclimb),
        "--suite",
        suite,
        "--baseline",
        baseline,
        "--candidate-root",
        str(candidate_root),
        "--output",
        str(work_dir),
    ]
    extra = os.environ.get("GAMEBENCH_HILLCLIMB_EXTRA_ARGS", "").strip()
    if extra:
        cmd.extend(extra.split())
    env = dict(os.environ)
    env["PYTHONPATH"] = str(task_dir)
    subprocess.run(cmd, check=True, cwd=str(task_dir), env=env)

    leaderboard = json.loads((work_dir / "leaderboard.json").read_text(encoding="utf-8"))
    baseline_score = float(leaderboard.get("baseline_score", 0.0))
    best_score = float(leaderboard.get("best_score", 0.0))
    delta = best_score - baseline_score
    passed = delta >= float(args.pass_delta) and str(leaderboard.get("best_candidate_id")) != "baseline"
    reward = best_score if passed else 0.0
    rankings = leaderboard.get("rankings") or []
    baseline_row = next(
        (r for r in rankings if isinstance(r, dict) and r.get("candidate_id") == "baseline"),
        None,
    )
    scout_rows = [
        r
        for r in rankings
        if isinstance(r, dict) and r.get("mean_scout_score") is not None
    ]
    payload = {
        "benchmark_family": "gamebench.code_policy_deo_hillclimb",
        "score_metric": leaderboard.get("score_metric"),
        "baseline_score": baseline_score,
        "best_score": best_score,
        "best_candidate_id": leaderboard.get("best_candidate_id"),
        "delta_vs_baseline": delta,
        "passed": passed,
        "harbor_reward": reward,
        "leaderboard_path": str(work_dir / "leaderboard.json"),
        "evaluated_policy_count": leaderboard.get("evaluated_policy_count"),
    }
    if scout_rows:
        by_scout = max(scout_rows, key=lambda r: float(r.get("mean_scout_score") or 0.0))
        if isinstance(baseline_row, dict) and baseline_row.get("mean_scout_score") is not None:
            baseline_scout = float(baseline_row["mean_scout_score"])
        else:
            baseline_scout = 0.0
        best_scout = float(by_scout.get("mean_scout_score") or 0.0)
        payload["baseline_mean_scout_score"] = baseline_scout
        payload["best_mean_scout_score"] = best_scout
        payload["delta_mean_scout_score"] = best_scout - baseline_scout
        payload["best_scout_candidate_id"] = by_scout.get("candidate_id")
    write_result(output_json, reward_path, payload)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
