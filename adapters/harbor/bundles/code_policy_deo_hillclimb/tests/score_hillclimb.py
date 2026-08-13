"""Harbor verifier: score code-policy hillclimb candidates in /workspace."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Match code_policy_deo_hillclimb task.toml [verifier] timeout_sec when unset.
_DEFAULT_HILLCLIMB_TIMEOUT_SEC = 900.0


def write_result(path: Path, reward_path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    reward_path.write_text(f"{payload.get('harbor_reward', 0.0)}\n", encoding="utf-8")


def _resolve_hillclimb_timeout_sec() -> float:
    for key in ("GAMEBENCH_HILLCLIMB_TIMEOUT_SEC", "HARBOR_VERIFIER_TIMEOUT_SEC"):
        raw = os.environ.get(key, "").strip()
        if not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if value > 0:
            return value
    return _DEFAULT_HILLCLIMB_TIMEOUT_SEC


def _terminate_process_group(proc: subprocess.Popen[Any], *, grace_seconds: float = 5.0) -> None:
    pid = getattr(proc, "pid", None)
    if os.name == "posix" and isinstance(pid, int) and pid > 0:
        try:
            os.killpg(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            try:
                os.killpg(pid, 0)
            except (ProcessLookupError, PermissionError, OSError):
                break
            time.sleep(0.05)
        else:
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=grace_seconds)
            except subprocess.TimeoutExpired:
                pass


def _run_hillclimb(
    cmd: list[str],
    *,
    cwd: str,
    env: dict[str, str],
    timeout_sec: float,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_group(proc)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            _terminate_process_group(proc, grace_seconds=1.0)
            stdout, stderr = proc.communicate(timeout=5)
    result = subprocess.CompletedProcess(
        args=cmd,
        returncode=-9 if timed_out else int(proc.returncode if proc.returncode is not None else 1),
        stdout=stdout or "",
        stderr=stderr or "",
    )
    if timed_out:
        result.stderr = (
            (result.stderr or "")
            + f"\n[timeout] hillclimb exceeded {timeout_sec:.0f}s and was terminated\n"
        )
    return result


def _payload_from_leaderboard(
    leaderboard: dict[str, Any],
    *,
    leaderboard_path: Path,
    pass_delta: float,
) -> dict[str, Any]:
    baseline_score = float(leaderboard.get("baseline_score", 0.0))
    best_score = float(leaderboard.get("best_score", 0.0))
    delta = best_score - baseline_score
    passed = delta >= float(pass_delta) and str(leaderboard.get("best_candidate_id")) != "baseline"
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
    payload: dict[str, Any] = {
        "benchmark_family": "gamebench.code_policy_deo_hillclimb",
        "score_metric": leaderboard.get("score_metric"),
        "baseline_score": baseline_score,
        "best_score": best_score,
        "best_candidate_id": leaderboard.get("best_candidate_id"),
        "delta_vs_baseline": delta,
        "passed": passed,
        "harbor_reward": reward,
        "leaderboard_path": str(leaderboard_path),
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
    heldout_rows = [
        r
        for r in rankings
        if isinstance(r, dict) and r.get("mean_heldout_score") is not None
    ]
    if heldout_rows:
        payload["heldout_suite_id"] = leaderboard.get("heldout_suite_id")
        payload["train_n_scenarios"] = leaderboard.get("train_n_scenarios")
        payload["heldout_n_scenarios"] = leaderboard.get("heldout_n_scenarios")
        if isinstance(baseline_row, dict) and baseline_row.get("mean_heldout_score") is not None:
            payload["baseline_mean_heldout_score"] = float(baseline_row["mean_heldout_score"])
        payload["best_mean_heldout_score"] = float(best_score)
        if isinstance(baseline_row, dict) and baseline_row.get("mean_train_score") is not None:
            payload["baseline_mean_train_score"] = float(baseline_row["mean_train_score"])
        best_train = next(
            (r for r in rankings if isinstance(r, dict) and r.get("candidate_id") == leaderboard.get("best_candidate_id")),
            None,
        )
        if isinstance(best_train, dict) and best_train.get("mean_train_score") is not None:
            payload["best_mean_train_score"] = float(best_train["mean_train_score"])
    return payload


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
    timeout_sec = _resolve_hillclimb_timeout_sec()

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
    # Task root only. Putting gold_python/shared on PYTHONPATH can shadow
    # namespace packages (e.g. overcooked `core.nev`) depending on import order.
    env["PYTHONPATH"] = str(task_dir)

    try:
        completed = _run_hillclimb(cmd, cwd=str(task_dir), env=env, timeout_sec=timeout_sec)
    except OSError as exc:
        write_result(
            output_json,
            reward_path,
            {
                "error": f"hillclimb launch failed: {type(exc).__name__}: {exc}",
                "harbor_reward": 0.0,
            },
        )
        return 1

    leaderboard_path = work_dir / "leaderboard.json"
    if completed.returncode != 0 or not leaderboard_path.exists():
        # Always emit reward.txt so matrix lanes don't report
        # gamebench_harbor_reward_missing on infra/isolation failures.
        stderr_tail = (completed.stderr or "")[-1500:]
        stdout_tail = (completed.stdout or "")[-800:]
        timed_out = completed.returncode == -9 or "[timeout]" in (completed.stderr or "")
        write_result(
            output_json,
            reward_path,
            {
                "error": "hillclimb_timeout" if timed_out else "hillclimb_failed",
                "returncode": completed.returncode,
                "timeout_sec": timeout_sec if timed_out else None,
                "stderr_tail": stderr_tail,
                "stdout_tail": stdout_tail,
                "harbor_reward": 0.0,
            },
        )
        return 1

    leaderboard = json.loads(leaderboard_path.read_text(encoding="utf-8"))
    payload = _payload_from_leaderboard(
        leaderboard,
        leaderboard_path=leaderboard_path,
        pass_delta=float(args.pass_delta),
    )
    write_result(output_json, reward_path, payload)
    return 0 if payload.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
