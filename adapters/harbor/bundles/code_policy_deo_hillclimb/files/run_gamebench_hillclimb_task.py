from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def gamebench_task() -> str:
    return os.environ.get("GAMEBENCH_TASK", "tictactoe-singleplayer").strip()


def candidate_subdir() -> str:
    return os.environ.get("CANDIDATE_SUBDIR", "tictactoe").strip()


def gamebench_root(workspace: Path) -> Path:
    raw = os.environ.get("GAMEBENCH_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    staged = workspace / "gamebench"
    if (staged / "tasks" / gamebench_task()).is_dir():
        return staged.resolve()
    return (Path.home() / "Documents" / "GitHub" / "gamebench").resolve()


def task_dir(workspace: Path) -> Path:
    return gamebench_root(workspace) / "tasks" / gamebench_task()


def resolve_candidate_root(output_root: Path, candidate_root: Path, lane: Path) -> Path:
    resolved = candidate_root.expanduser()
    if not resolved.is_absolute():
        resolved = (output_root / resolved).resolve()
    task_candidates = resolved / candidate_subdir()
    if task_candidates.is_dir():
        return task_candidates.resolve()
    if resolved.exists():
        return resolved
    fallback = lane / "candidates" / candidate_subdir()
    if fallback.exists():
        return fallback.resolve()
    return resolved


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_hillclimb(output_root: Path, *, candidate_root: Path, lane: Path) -> dict[str, Any]:
    hillclimb = lane / "scripts" / "run_hillclimb.py"
    if not hillclimb.exists():
        raise FileNotFoundError(f"missing hillclimb runner: {hillclimb}")
    work_dir = output_root / "artifacts" / "gamebench_hillclimb"
    work_dir.mkdir(parents=True, exist_ok=True)
    suite = lane / "defaults" / "policy_sweep" / "policy_dev_v1.json"
    baseline = lane / "containers" / "codepolicy" / "heuristic_policy.py"
    command = [
        sys.executable,
        str(hillclimb),
        "--suite",
        str(suite),
        "--baseline",
        str(baseline),
        "--candidate-root",
        str(candidate_root),
        "--output",
        str(work_dir),
    ]
    extra = os.environ.get("GAMEBENCH_HILLCLIMB_EXTRA_ARGS", "").strip()
    if extra:
        command.extend(extra.split())
    env = dict(os.environ)
    env["PYTHONPATH"] = str(lane)
    subprocess.run(command, check=True, cwd=str(lane), env=env)
    return json.loads((work_dir / "leaderboard.json").read_text(encoding="utf-8"))


def materialize_workproduct(output_root: Path, leaderboard: dict[str, Any], lane: Path) -> None:
    wp = output_root / "artifacts" / "workproduct_container"
    wp.mkdir(parents=True, exist_ok=True)
    best_id = str(leaderboard.get("best_candidate_id", "baseline"))
    best = next((item for item in leaderboard.get("rankings", []) if item.get("candidate_id") == best_id), {})
    best_policy_dir = wp / "best_policy"
    best_policy_dir.mkdir(parents=True, exist_ok=True)
    src = Path(str(best.get("policy_path", "")))
    if src.exists():
        shutil.copy2(src, best_policy_dir / "heuristic_policy.py")
    baseline_score = float(leaderboard.get("baseline_score", 0.0))
    best_score = float(leaderboard.get("best_score", 0.0))
    write_json(
        wp / "eval_summary.json",
        {
            "schema_version": "gamebench.eval_summary.v1",
            "candidate_count": int(leaderboard.get("evaluated_policy_count", 0)),
            "completed_candidate_count": int(leaderboard.get("evaluated_policy_count", 0)),
            "best_candidate_id": best_id,
            "best_source_kind": "candidate" if best_id != "baseline" else "baseline",
            "best_score": best_score,
            "baseline_score": baseline_score,
            "best_score_delta": best_score - baseline_score,
            "records": leaderboard.get("rankings", []),
        },
    )


def cmd_run(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root).expanduser().resolve()
    lane = task_dir(output_root)
    candidate_root = resolve_candidate_root(output_root, Path(args.candidate_root), lane)
    leaderboard = run_hillclimb(output_root, candidate_root=candidate_root, lane=lane)
    materialize_workproduct(output_root, leaderboard, lane)
    best_score = float(leaderboard.get("best_score", 0.0))
    baseline_score = float(leaderboard.get("baseline_score", 0.0))
    family = f"gamebench.{gamebench_task().replace('-', '_')}_code_policy"
    result = {
        "schema_version": "gamebench.harbor.result.v1",
        "task_id": f"harbor/gamebench/{gamebench_task()}",
        "benchmark_family": family,
        "reward": {"primary_metric": "task_score", "value": max(best_score, 0.0)},
        "best_candidate_id": leaderboard.get("best_candidate_id"),
        "baseline_score": baseline_score,
        "best_score": best_score,
        "delta_vs_baseline": best_score - baseline_score,
    }
    write_json(output_root / "artifacts" / "gamebench_harbor_result.json", result)
    # Archival alias for older Harbor scorers/panels; not authority.
    write_json(output_root / "artifacts" / "reportbench_output.json", result)
    print(json.dumps(leaderboard, indent=2, sort_keys=True))
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root).expanduser().resolve()
    errors: list[str] = []
    summary_path = output_root / "artifacts/workproduct_container/eval_summary.json"
    if not summary_path.exists():
        errors.append("missing artifacts/workproduct_container/eval_summary.json")
    else:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if float(summary.get("best_score_delta") or 0.0) < 0.01:
            errors.append("best policy does not beat baseline by >= 0.01")
        if str(summary.get("best_source_kind") or "") != "candidate":
            errors.append("best_source_kind is not candidate")
        if int(summary.get("completed_candidate_count") or 0) < 1:
            errors.append("no completed candidates")
    candidate_glob = list((output_root / "candidates" / candidate_subdir()).glob("*/heuristic_policy.py"))
    if not candidate_glob:
        errors.append(f"no policies under candidates/{candidate_subdir()}/*/heuristic_policy.py")
    review = {"score": 0.0 if errors else 1.0, "errors": errors}
    write_json(output_root / "artifacts/verifier_review.json", review)
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GameBench code-policy hillclimb helper for Harbor workspaces.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--output-root", required=True)
    run.add_argument("--candidate-root", default="candidates")
    run.set_defaults(func=cmd_run)
    score = sub.add_parser("score")
    score.add_argument("--output-root", required=True)
    score.set_defaults(func=cmd_score)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
