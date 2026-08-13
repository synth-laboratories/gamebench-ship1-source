#!/usr/bin/env python3
"""Rank code-policy candidates on the NOTES.md hillclimb envs, then eval top-K × N.

For each env in the NOTES "code policy ✓" block (craftax / sokoban / rogue /
overcooked / minihack / dungeongrid), this script:

1. Discovers existing code-policy candidates (Harbor refs, task candidates,
   baselines, Dock packages when present, optional policy_puzzles).
2. Ranks them on a short suite and keeps the top ``--top`` (default 10).
3. Re-runs each selected policy on a synthesized ``--episodes``-long suite
   (default 100) against the local python/rust gold rewrite.
4. Writes a markdown stats table + JSON under ``--output``.

Many envs ship fewer than 10 distinct policies; the script evaluates all unique
candidates (by sha256) up to ``--top``.

Examples:
  ./scripts/run_codepolicy_top10_x100.py --dry-run
  ./scripts/run_codepolicy_top10_x100.py --envs sokoban-singleplayer --episodes 20 --top 3
  ./scripts/run_codepolicy_top10_x100.py --output /tmp/gb-codepolicy-panel
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVALS_ROOT = Path.home() / "Documents" / "GitHub" / "evals"

# NOTES.md code-policy ✓ subset (incl. emerald port lane).
ENVS = (
    "craftax-singleplayer",
    "craftax-multiplayer",
    "sokoban-singleplayer",
    "rogue-singleplayer",
    "overcooked-v2-multiplayer",
    "minihack-singleplayer",
    "dungeongrid-singleplayer",
    "dungeongrid-multiplayer",
    "pokemon-emerald-littleroot-singleplayer",
)

DOCK_CANDIDATE_GLOBS = {
    "craftax-singleplayer": "core/dock/tasks/gamebench/craftax-code_policy_opt/candidates/**/heuristic_policy.py",
    "craftax-multiplayer": "core/dock/tasks/gamebench/craftax_coop-code_policy_opt/candidates/**/heuristic_policy.py",
    "sokoban-singleplayer": "core/dock/tasks/gamebench/sokoban-code_policy_opt/candidates/**/heuristic_policy.py",
    "rogue-singleplayer": "core/dock/tasks/gamebench/rogue-code_policy_opt/candidates/**/heuristic_policy.py",
    "overcooked-v2-multiplayer": "core/dock/tasks/gamebench/overcooked_v2-code_policy_opt/candidates/**/heuristic_policy.py",
    "minihack-singleplayer": "core/dock/tasks/gamebench/minihack-code_policy_opt/candidates/**/heuristic_policy.py",
    "dungeongrid-singleplayer": "core/dock/tasks/gamebench/dungeongrid_singleplayer-code_policy_opt/candidates/**/heuristic_policy.py",
    "dungeongrid-multiplayer": "core/dock/tasks/gamebench/dungeongrid-code_policy_opt/candidates/**/heuristic_policy.py",
}


@dataclass(frozen=True)
class Policy:
    env: str
    candidate_id: str
    path: Path
    sha256: str


@dataclass
class SweepResult:
    env: str
    candidate_id: str
    policy_path: str
    ok: bool
    score: float | None = None
    mean_reward: float | None = None
    success_rate: float | None = None
    n_episodes: int | None = None
    elapsed_s: float | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _task_dir(env: str) -> Path:
    return REPO_ROOT / "tasks" / env


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return str(v)


def _candidate_id_from_path(path: Path, env: str) -> str:
    parts = path.resolve().parts
    if "references" in parts:
        return "harbor_reference"
    if path.name == "heuristic_baseline.py":
        return "heuristic_baseline"
    if path.parent.name == "codepolicy":
        return "container_baseline"
    # .../candidates/<id>/heuristic_policy.py or .../craftax/<id>/...
    parent = path.parent.name
    if parent in {"candidates", env, "sokoban", "rogue", "craftax", "craftax_coop", "minihack", "overcooked_v2"}:
        return path.parent.parent.name
    return parent


def discover_policies(
    env: str,
    *,
    evals_root: Path | None,
    include_puzzles: bool,
) -> list[Policy]:
    task = _task_dir(env)
    roots: list[Path] = [
        REPO_ROOT
        / "adapters"
        / "harbor"
        / "bundles"
        / "code_policy_deo_hillclimb"
        / "solution"
        / "references"
        / env
        / "heuristic_policy.py",
        task / "policies" / "heuristic_baseline.py",
        task / "containers" / "codepolicy" / "heuristic_policy.py",
    ]
    for pattern in (
        "candidates/**/heuristic_policy.py",
        "examples/code_policy_deo/candidates/**/heuristic_policy.py",
    ):
        roots.extend(sorted(task.glob(pattern)))
    if include_puzzles:
        roots.extend(sorted(task.glob("policy_puzzles/**/heuristic_policy.py")))
    if evals_root is not None:
        glob_pat = DOCK_CANDIDATE_GLOBS.get(env)
        if glob_pat:
            roots.extend(sorted((evals_root).glob(glob_pat)))

    seen: dict[str, Policy] = {}
    for path in roots:
        if not path.is_file():
            continue
        digest = _sha256(path)
        if digest in seen:
            continue
        seen[digest] = Policy(
            env=env,
            candidate_id=_candidate_id_from_path(path, env),
            path=path.resolve(),
            sha256=digest,
        )
    # Stable order: prefer named candidates before baselines, then path.
    policies = list(seen.values())
    policies.sort(
        key=lambda p: (
            0 if p.candidate_id not in {"heuristic_baseline", "container_baseline", "harbor_reference"} else 1,
            p.candidate_id,
            str(p.path),
        )
    )
    # Disambiguate duplicate candidate_ids after dedupe-by-hash.
    used: dict[str, int] = {}
    unique: list[Policy] = []
    for policy in policies:
        n = used.get(policy.candidate_id, 0)
        used[policy.candidate_id] = n + 1
        cid = policy.candidate_id if n == 0 else f"{policy.candidate_id}_{n + 1}"
        unique.append(Policy(env=policy.env, candidate_id=cid, path=policy.path, sha256=policy.sha256))
    return unique


def _base_suite_path(env: str, prefer_smoke: bool) -> Path:
    task = _task_dir(env)
    smoke = task / "defaults" / "policy_sweep" / "policy_smoke_v1.json"
    batch100 = task / "defaults" / "policy_sweep" / "policy_batch_v100.json"
    dev = task / "defaults" / "policy_sweep" / "policy_dev_v1.json"
    if prefer_smoke and smoke.is_file():
        return smoke
    if not prefer_smoke and env == "craftax-singleplayer" and batch100.is_file():
        return batch100
    if env == "rogue-singleplayer":
        v2 = task / "defaults" / "policy_sweep" / "policy_dev_v2.json"
        if v2.is_file() and not prefer_smoke:
            return v2
    if dev.is_file():
        return dev
    if smoke.is_file():
        return smoke
    raise FileNotFoundError(f"no policy_sweep suite for {env}")


def expand_suite(base: dict[str, Any], *, env: str, n_episodes: int, suite_id: str) -> dict[str, Any]:
    """Clone a suite template into an N-episode evaluation suite."""
    suite = json.loads(json.dumps(base))
    suite["suite_id"] = suite_id

    if "seeds" in suite and isinstance(suite["seeds"], list):
        suite["seeds"] = list(range(101, 101 + n_episodes))
        suite.pop("holdout_seeds", None)
        suite.pop("tasks", None)
        return suite

    if "tasks" in suite and isinstance(suite["tasks"], list) and suite["tasks"]:
        # Rogue v2-style: expand task list by cycling templates with new seeds.
        templates = suite["tasks"]
        expanded = []
        for i in range(n_episodes):
            item = json.loads(json.dumps(templates[i % len(templates)]))
            if isinstance(item, dict):
                item["seed"] = 101 + i
                item["task_id"] = f"{item.get('task_id', item.get('scenario_id', 'task'))}_{i:03d}"
            expanded.append(item)
        suite["tasks"] = expanded
        return suite

    if "episodes" in suite and isinstance(suite["episodes"], list) and suite["episodes"]:
        # Craftax-coop: keep full kind×alpha coverage, then tile with new seeds.
        templates = suite["episodes"]
        expanded = []
        i = 0
        while len(expanded) < n_episodes:
            item = json.loads(json.dumps(templates[i % len(templates)]))
            item["seed"] = int(item.get("seed", 101)) + 1000 * (i // len(templates)) + (i % 97)
            item["scenario_id"] = f"{item.get('scenario_id', item.get('scenario', 'ep'))}_{len(expanded):03d}"
            expanded.append(item)
            i += 1
        suite["episodes"] = expanded[:n_episodes]
        return suite

    if "scenarios" in suite and isinstance(suite["scenarios"], list) and suite["scenarios"]:
        templates = suite["scenarios"]
        expanded = []
        for i in range(n_episodes):
            item = json.loads(json.dumps(templates[i % len(templates)]))
            item["seed"] = int(item.get("seed", 1)) + 1000 * (i // len(templates)) + i
            base_id = str(item.get("scenario_id") or item.get("profile") or item.get("source") or "scenario")
            item["scenario_id"] = f"{Path(base_id).stem}_{i:03d}"
            expanded.append(item)
        suite["scenarios"] = expanded
        return suite

    raise ValueError(f"{env}: suite has no seeds/tasks/episodes/scenarios to expand")


def _extract_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    n = (
        summary.get("n_seeds")
        or summary.get("n_scenarios")
        or summary.get("episode_count")
        or summary.get("n_episodes")
        or len(summary.get("episode_summaries") or summary.get("episodes") or summary.get("seeds") or [])
        or None
    )
    success = summary.get("success_rate")
    if success is None and summary.get("mean_coord_success_rate") is not None:
        success = summary.get("mean_coord_success_rate")
    return {
        "score": summary.get("score"),
        "mean_reward": summary.get("mean_reward")
        if summary.get("mean_reward") is not None
        else summary.get("mean_coord_reward"),
        "success_rate": success,
        "n_episodes": n,
        "elapsed_s": summary.get("elapsed_s"),
    }


def _load_sweep_fn(task_dir: Path) -> Callable[..., dict[str, Any]]:
    sweep_path = task_dir / "scripts" / "run_policy_sweep.py"
    mod_name = f"gb_sweep_{task_dir.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, sweep_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {sweep_path}")
    module = importlib.util.module_from_spec(spec)
    # Ensure task-local imports resolve the same way CLI runs do.
    sys.path.insert(0, str(task_dir / "scripts"))
    for p in (task_dir, task_dir / "gold_python", task_dir / "shared", task_dir / "gold"):
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec.loader.exec_module(module)
    fn = getattr(module, "run_policy_sweep", None)
    if not callable(fn):
        raise RuntimeError(f"{sweep_path} has no run_policy_sweep()")
    return fn


def run_one_policy(
    env: str,
    policy: Policy,
    suite_path: Path,
    output_path: Path,
    *,
    episode_timeout_s: float,
) -> SweepResult:
    task = _task_dir(env)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    env_vars = os.environ.copy()
    env_vars["GAMEBENCH_ROOT"] = str(REPO_ROOT)
    # Harbor craftax reference imports policies.* from the task tree.
    py_path = os.pathsep.join(
        [
            str(task),
            str(task / "policies"),
            str(task / "gold_python"),
            str(task / "shared"),
            env_vars.get("PYTHONPATH", ""),
        ]
    )
    env_vars["PYTHONPATH"] = py_path

    # craftax-multiplayer sweep is library-only.
    if env == "craftax-multiplayer":
        try:
            sweep = _load_sweep_fn(task)
            t0 = time.time()
            summary = sweep(
                policy_path=policy.path,
                suite_path=suite_path,
                output_path=output_path,
                include_trace=False,
            )
            metrics = _extract_metrics(summary if isinstance(summary, dict) else _read_json(output_path))
            if metrics["elapsed_s"] is None:
                metrics["elapsed_s"] = time.time() - t0
            return SweepResult(
                env=env,
                candidate_id=policy.candidate_id,
                policy_path=str(policy.path),
                ok=True,
                raw=summary if isinstance(summary, dict) else _read_json(output_path),
                **metrics,
            )
        except Exception as exc:  # noqa: BLE001 - surface per-policy failures in the table
            _write_json(
                output_path,
                {"status": "error", "error": f"{type(exc).__name__}: {exc}", "env": env, "policy": str(policy.path)},
            )
            return SweepResult(
                env=env,
                candidate_id=policy.candidate_id,
                policy_path=str(policy.path),
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )

    cmd = [
        sys.executable,
        str(task / "scripts" / "run_policy_sweep.py"),
        "--policy",
        str(policy.path),
        "--suite",
        str(suite_path),
        "--output",
        str(output_path),
    ]
    if env == "craftax-singleplayer":
        cmd.extend(["--lane", "python", "--summary-only"])
    elif env == "sokoban-singleplayer":
        cmd.extend(["--engine-lane", "python", "--workers", "1"])
    elif env == "rogue-singleplayer":
        cmd.extend(["--lane", "python", "--episode-timeout-seconds", str(episode_timeout_s)])
    elif env == "pokemon-emerald-littleroot-singleplayer":
        pass  # rust gold HTTP; sweep auto-starts emerald_gold

    t0 = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(task),
        env=env_vars,
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - t0
    if output_path.is_file():
        try:
            summary = _read_json(output_path)
        except json.JSONDecodeError:
            summary = {"status": "error", "error": "invalid summary json", "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
    else:
        summary = {
            "status": "error",
            "error": f"missing summary (exit={proc.returncode})",
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
        _write_json(output_path, summary)

    if summary.get("status") == "error" or summary.get("schema", "").endswith("failure.v1"):
        err = summary.get("failure") or summary.get("error") or proc.stderr.strip() or f"exit {proc.returncode}"
        return SweepResult(
            env=env,
            candidate_id=policy.candidate_id,
            policy_path=str(policy.path),
            ok=False,
            elapsed_s=elapsed,
            error=str(err)[:500],
            raw=summary,
        )

    metrics = _extract_metrics(summary)
    if metrics["elapsed_s"] is None:
        metrics["elapsed_s"] = elapsed
    return SweepResult(
        env=env,
        candidate_id=policy.candidate_id,
        policy_path=str(policy.path),
        ok=True,
        raw=summary,
        **metrics,
    )


def render_markdown_table(rows: list[SweepResult], *, title: str) -> str:
    lines = [
        f"## {title}",
        "",
        "| env | policy | ok | n | score | mean_reward | success_rate | elapsed_s |",
        "|-----|--------|:--:|--:|------:|------------:|-------------:|----------:|",
    ]
    for row in rows:
        lines.append(
            "| {env} | {policy} | {ok} | {n} | {score} | {reward} | {success} | {elapsed} |".format(
                env=row.env,
                policy=row.candidate_id,
                ok="✓" if row.ok else "✗",
                n=row.n_episodes if row.n_episodes is not None else "—",
                score=_fmt(row.score),
                reward=_fmt(row.mean_reward),
                success=_fmt(row.success_rate),
                elapsed=_fmt(row.elapsed_s, 2),
            )
        )
    if not rows:
        lines.append("| — | — | — | — | — | — | — | — |")
    lines.append("")
    return "\n".join(lines)


def render_env_summary(rows: list[SweepResult], *, episodes: int) -> str:
    """One row per env: best policy on the N× eval."""
    by_env: dict[str, list[SweepResult]] = {}
    for row in rows:
        by_env.setdefault(row.env, []).append(row)
    lines = [
        f"## Per-env best ({episodes}× eval)",
        "",
        "| env | policies_evaled | best_policy | best_score | best_success | mean_score_all |",
        "|-----|----------------:|-------------|-----------:|-------------:|---------------:|",
    ]
    for env in ENVS:
        env_rows = [r for r in by_env.get(env, []) if r.ok and r.score is not None]
        if not env_rows:
            lines.append(f"| {env} | 0 | — | — | — | — |")
            continue
        best = max(env_rows, key=lambda r: float(r.score or -math.inf))
        mean_score = statistics.fmean(float(r.score) for r in env_rows if r.score is not None)
        lines.append(
            f"| {env} | {len(env_rows)} | {best.candidate_id} | {_fmt(best.score)} | {_fmt(best.success_rate)} | {_fmt(mean_score)} |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--envs", nargs="+", choices=ENVS, default=list(ENVS), help="Subset of NOTES envs")
    parser.add_argument("--top", type=int, default=10, help="Max policies per env after ranking (default 10)")
    parser.add_argument("--episodes", type=int, default=100, help="Episodes per selected policy (default 100)")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/gb-codepolicy-top10-x100"),
        help="Directory for suites, per-policy summaries, stats.md, results.json",
    )
    parser.add_argument("--evals-root", type=Path, default=DEFAULT_EVALS_ROOT, help="Path to evals repo for Dock candidates")
    parser.add_argument("--no-dock", action="store_true", help="Skip Dock candidate discovery")
    parser.add_argument("--include-puzzles", action="store_true", help="Include policy_puzzles/hidden heuristics")
    parser.add_argument("--skip-rank", action="store_true", help="Skip short ranking; take first --top by discovery order")
    parser.add_argument("--dry-run", action="store_true", help="List discovered policies and exit")
    parser.add_argument("--episode-timeout-seconds", type=float, default=30.0, help="Rogue per-episode timeout")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    evals_root = None if args.no_dock else Path(args.evals_root).expanduser().resolve()
    if evals_root is not None and not evals_root.is_dir():
        print(f"warning: evals root missing ({evals_root}); continuing without Dock candidates", file=sys.stderr)
        evals_root = None

    discovery: dict[str, list[Policy]] = {}
    for env in args.envs:
        discovery[env] = discover_policies(env, evals_root=evals_root, include_puzzles=args.include_puzzles)

    if args.dry_run:
        for env in args.envs:
            print(f"\n{env} ({len(discovery[env])} unique policies)")
            for policy in discovery[env]:
                print(f"  - {policy.candidate_id}: {policy.path}")
        return 0

    rank_rows: list[SweepResult] = []
    selected: dict[str, list[Policy]] = {}
    for env in args.envs:
        policies = discovery[env]
        if not policies:
            print(f"[{env}] no policies found", file=sys.stderr)
            selected[env] = []
            continue
        if args.skip_rank or len(policies) <= args.top:
            selected[env] = policies[: args.top]
            print(f"[{env}] selecting {len(selected[env])}/{len(policies)} policies (no rank needed)")
            continue

        rank_suite_src = _base_suite_path(env, prefer_smoke=True)
        rank_suite = expand_suite(
            _read_json(rank_suite_src),
            env=env,
            n_episodes=min(10, args.episodes),
            suite_id=f"{env}_rank_smoke",
        )
        # craftax-mp rank suite must still cover kind×alpha — use unexpanded base if tiny.
        if env == "craftax-multiplayer":
            rank_suite = _read_json(rank_suite_src)
            rank_suite["suite_id"] = f"{env}_rank_smoke"
        rank_suite_path = output / env / "_rank_suite.json"
        _write_json(rank_suite_path, rank_suite)

        scored: list[tuple[float, Policy, SweepResult]] = []
        for policy in policies:
            out = output / env / "rank" / policy.candidate_id / "summary.json"
            print(f"[{env}] rank {policy.candidate_id} …", flush=True)
            result = run_one_policy(env, policy, rank_suite_path, out, episode_timeout_s=args.episode_timeout_seconds)
            rank_rows.append(result)
            score = float(result.score) if result.ok and result.score is not None else float("-inf")
            scored.append((score, policy, result))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected[env] = [policy for _, policy, _ in scored[: args.top]]
        print(f"[{env}] top {len(selected[env])}: {[p.candidate_id for p in selected[env]]}", flush=True)

    eval_rows: list[SweepResult] = []
    env_timings: list[dict[str, Any]] = []
    for env in args.envs:
        policies = selected.get(env, [])
        if not policies:
            env_timings.append(
                {
                    "env": env,
                    "wall_s": 0.0,
                    "policy_elapsed_s": 0.0,
                    "policies": 0,
                    "ok": 0,
                    "fail": 0,
                }
            )
            continue
        base_path = _base_suite_path(env, prefer_smoke=False)
        if env == "craftax-singleplayer" and args.episodes == 100:
            # Prefer the checked-in 100-seed batch suite.
            batch = _task_dir(env) / "defaults" / "policy_sweep" / "policy_batch_v100.json"
            eval_suite = _read_json(batch if batch.is_file() else base_path)
            if not batch.is_file():
                eval_suite = expand_suite(eval_suite, env=env, n_episodes=args.episodes, suite_id=f"{env}_x{args.episodes}")
            else:
                eval_suite["suite_id"] = batch.stem
        else:
            eval_suite = expand_suite(
                _read_json(base_path),
                env=env,
                n_episodes=args.episodes,
                suite_id=f"{env}_x{args.episodes}",
            )
        suite_path = output / env / f"suite_x{args.episodes}.json"
        _write_json(suite_path, eval_suite)

        env_t0 = time.time()
        env_ok = 0
        env_fail = 0
        policy_elapsed = 0.0
        for policy in policies:
            out = output / env / "eval" / policy.candidate_id / "summary.json"
            print(f"[{env}] eval×{args.episodes} {policy.candidate_id} …", flush=True)
            result = run_one_policy(env, policy, suite_path, out, episode_timeout_s=args.episode_timeout_seconds)
            eval_rows.append(result)
            if result.ok:
                env_ok += 1
            else:
                env_fail += 1
            if result.elapsed_s is not None:
                policy_elapsed += float(result.elapsed_s)
            status = "ok" if result.ok else f"FAIL {result.error}"
            print(
                f"  -> score={_fmt(result.score)} success={_fmt(result.success_rate)} "
                f"reward={_fmt(result.mean_reward)} ({status})",
                flush=True,
            )
        wall_s = time.time() - env_t0
        env_timings.append(
            {
                "env": env,
                "wall_s": wall_s,
                "policy_elapsed_s": policy_elapsed,
                "policies": len(policies),
                "ok": env_ok,
                "fail": env_fail,
            }
        )
        print(f"[{env}] wall_time={wall_s:.2f}s policies={len(policies)} ok={env_ok} fail={env_fail}", flush=True)

    table = render_markdown_table(eval_rows, title=f"Code-policy top-{args.top} × {args.episodes}")
    summary = render_env_summary(eval_rows, episodes=args.episodes)
    timing_lines = [
        "## Per-env wall time",
        "",
        "| env | wall_s | policies | ok | fail | sum_policy_elapsed_s |",
        "|-----|-------:|---------:|---:|-----:|---------------------:|",
    ]
    for item in env_timings:
        timing_lines.append(
            f"| {item['env']} | {_fmt(item['wall_s'], 2)} | {item['policies']} | "
            f"{item['ok']} | {item['fail']} | {_fmt(item['policy_elapsed_s'], 2)} |"
        )
    timing_lines.append("")
    total_wall = sum(float(item["wall_s"]) for item in env_timings)
    timing_lines.append(f"Total eval wall time: **{_fmt(total_wall, 2)}s** ({total_wall / 60.0:.2f} min)")
    timing_lines.append("")
    timing_md = "\n".join(timing_lines)

    md = "\n".join(
        [
            "# GameBench code-policy top-K × N",
            "",
            f"- repo: `{REPO_ROOT}`",
            f"- envs: {', '.join(args.envs)}",
            f"- top: {args.top}",
            f"- episodes: {args.episodes}",
            f"- lane: local python gold rewrite (rust not required)",
            "",
            timing_md,
            summary,
            table,
        ]
    )
    if rank_rows:
        md += "\n" + render_markdown_table(rank_rows, title="Ranking pass")

    (output / "stats.md").write_text(md + "\n")
    _write_json(
        output / "results.json",
        {
            "schema": "gamebench.codepolicy_topk_xN.v1",
            "repo_root": str(REPO_ROOT),
            "envs": list(args.envs),
            "top": args.top,
            "episodes": args.episodes,
            "env_timings": env_timings,
            "total_eval_wall_s": total_wall,
            "discovery": {
                env: [
                    {"candidate_id": p.candidate_id, "path": str(p.path), "sha256": p.sha256}
                    for p in discovery[env]
                ]
                for env in args.envs
            },
            "selected": {
                env: [p.candidate_id for p in selected.get(env, [])] for env in args.envs
            },
            "eval": [row.__dict__ | {"raw": None} for row in eval_rows],
            "rank": [row.__dict__ | {"raw": None} for row in rank_rows],
        },
    )
    print("\n" + md)
    print(f"\nwrote {output / 'stats.md'}")
    print(f"wrote {output / 'results.json'}")
    failures = [r for r in eval_rows if not r.ok]
    return 1 if failures and len(failures) == len(eval_rows) else 0


if __name__ == "__main__":
    # Avoid leaving a stale cwd-dependent import cache when reusing one process.
    try:
        raise SystemExit(main())
    finally:
        pass
