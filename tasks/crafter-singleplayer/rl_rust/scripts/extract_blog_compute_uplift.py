#!/usr/bin/env python3
"""Extract crafter-rl-compute-uplift blog chart JSON from crafter-rl run directories.

Usage (multi-seed: repeat a method to aggregate N seed runs into one row with
across-seed mean + CI):
  python3 scripts/extract_blog_compute_uplift.py \\
    --output growth/.../chart_data/crafter_rl_compute_uplift.json \\
    ppo=reports/rl_rust/blog_ppo_20step_heldout_4x32_s1 \\
    ppo=reports/rl_rust/blog_ppo_20step_heldout_4x32_s2 \\
    ppo=reports/rl_rust/blog_ppo_20step_heldout_4x32_s3 \\
    cispo=reports/rl_rust/blog_cispo_20step_heldout_4x32_s1 \\
    cispo=reports/rl_rust/blog_cispo_20step_heldout_4x32_s2

Optional GELO row (optimizer-side cost via optimizer_cost_extract.py):
  gelo_rlvr_opsd=optimizers-beta/.out/crafter_rust_runs/<run_id>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_relative(path: Path) -> str:
    """Repo-root-relative path string (no machine-local /Users prefix), so the
    evidence JSON passes the blog provenance gate and is reproducible anywhere."""
    resolved = path.resolve()
    try:
        toplevel = subprocess.run(
            ["git", "-C", str(resolved.parent), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return str(resolved.relative_to(toplevel))
    except Exception:
        try:
            return str(resolved.relative_to(Path.cwd()))
        except ValueError:
            return path.name

# Tinker gpt-oss-20b list pricing (USD per token) — backend model_pricing parity
INPUT_USD_PER_TOKEN = 0.075 / 1_000_000
OUTPUT_USD_PER_TOKEN = 0.30 / 1_000_000
PRICING_TABLE_VERSION = "tinker_gpt-oss-20b_2026-06-28"

METHOD_META: dict[str, dict[str, str]] = {
    "ppo": {
        "stack_depth": "trainer_only",
        "primary_metric": "mean_achievement_reward",
        "reward_mode": "standard",
    },
    "cispo": {
        "stack_depth": "trainer_only",
        "primary_metric": "goal_success_rate",
        "reward_mode": "standard",
    },
    "ddpo": {
        "stack_depth": "trainer_only",
        "primary_metric": "goal_success_rate",
        "reward_mode": "standard",
    },
    "gelo_rlvr_opsd": {
        "stack_depth": "archive+2_experts+opsd",
        "primary_metric": "theme_goal_success_and_retention_mean_reward",
        "reward_mode": "goal_binary",
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _canonical_source_ref(row: dict[str, Any]) -> str:
    payload = {k: v for k, v in row.items() if k != "source_ref"}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _token_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return input_tokens * INPUT_USD_PER_TOKEN + output_tokens * OUTPUT_USD_PER_TOKEN


def _sum_tokens_from_report(report: dict[str, Any]) -> tuple[int, int]:
    inp = out = 0
    meta = report.get("metadata") or {}
    for update in meta.get("updates") or []:
        inp += int(update.get("train_input_tokens") or 0)
        out += int(update.get("train_output_tokens") or 0)
    for ev in meta.get("evals") or []:
        inp += int(ev.get("eval_input_tokens") or 0)
        out += int(ev.get("eval_output_tokens") or 0)
    return inp, out


def _sum_rollouts(report: dict[str, Any], updates: list[dict[str, Any]]) -> int:
    train = int(report.get("rollout_count") or 0)
    meta = report.get("metadata") or {}
    eval_rollouts = sum(int(e.get("rollout_count") or 0) for e in meta.get("evals") or [])
    if train == 0 and updates:
        train = sum(int(u.get("rollout_count") or 0) for u in updates)
    return train + eval_rollouts


def _pick_evals(report: dict[str, Any], evals: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if evals:
        bootstrap = next((e for e in evals if e.get("eval_label") == "bootstrap"), evals[0])
        final = next((e for e in reversed(evals) if e.get("eval_label") == "final"), evals[-1])
        return bootstrap, final
    meta_evals = (report.get("metadata") or {}).get("evals") or []
    if not meta_evals:
        return None, None
    bootstrap = next((e for e in meta_evals if e.get("eval_label") == "bootstrap"), meta_evals[0])
    final = next((e for e in reversed(meta_evals) if e.get("eval_label") == "final"), meta_evals[-1])
    return bootstrap, final


def _metric_value(eval_row: dict[str, Any] | None, primary_metric: str) -> float | None:
    if not eval_row:
        return None
    if primary_metric == "goal_success_rate":
        return float(eval_row.get("goal_success_rate")) if eval_row.get("goal_success_rate") is not None else None
    return float(eval_row.get("mean_reward")) if eval_row.get("mean_reward") is not None else None


def _ci_band(eval_row: dict[str, Any] | None, primary_metric: str) -> tuple[float | None, float | None]:
    if not eval_row:
        return None, None
    key = "goal_success_rate_ci95" if primary_metric == "goal_success_rate" else "mean_reward_ci95"
    band = eval_row.get(key) or {}
    low = band.get("low")
    high = band.get("high")
    return (float(low) if low is not None else None, float(high) if high is not None else None)


def _instability_series(updates: list[dict[str, Any]], evals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for ev in evals:
        label = ev.get("eval_label") or ev.get("checkpoint_version")
        points.append(
            {
                "x": ev.get("checkpoint_epoch", len(points)),
                "label": label,
                "mean_reward": ev.get("mean_reward"),
                "goal_success_rate": ev.get("goal_success_rate"),
            }
        )
    for upd in updates:
        points.append(
            {
                "x": upd.get("update_index"),
                "label": f"update_{upd.get('update_index')}",
                "mean_reward": upd.get("mean_reward"),
                "goal_success_rate": upd.get("goal_success_rate"),
            }
        )
    return points


def extract_crafter_rl_row(
    method: str,
    run_dir: Path,
    *,
    run_id: str | None = None,
    accepted: bool = True,
    limitations: str = "",
) -> dict[str, Any]:
    report_path = run_dir / "report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"missing report.json in {run_dir}")

    report = _read_json(report_path)
    evals = _read_jsonl(run_dir / "evals.jsonl")
    updates = _read_jsonl(run_dir / "updates.jsonl")
    config_path = run_dir / "config.json"

    meta_info = METHOD_META.get(method, METHOD_META["cispo"])
    primary_metric = meta_info["primary_metric"]
    bootstrap_ev, final_ev = _pick_evals(report, evals)
    bootstrap_val = _metric_value(bootstrap_ev, primary_metric)
    final_val = _metric_value(final_ev, primary_metric)
    delta = None
    if bootstrap_val is not None and final_val is not None:
        delta = final_val - bootstrap_val

    ci_low, ci_high = _ci_band(final_ev, primary_metric)
    eval_n = int(final_ev.get("rollout_count") or 0) if final_ev else None
    rollouts_total = _sum_rollouts(report, updates)
    inp, out = _sum_tokens_from_report(report)
    cost_usd = _token_cost_usd(inp, out)

    delta_per_1k = None
    delta_per_dollar = None
    if delta is not None and rollouts_total > 0:
        delta_per_1k = delta / (rollouts_total / 1000)
    if delta is not None and cost_usd > 0:
        delta_per_dollar = delta / cost_usd

    resolved_run_id = run_id or run_dir.name
    artifact_refs = [str(p.relative_to(run_dir)) for p in [report_path, run_dir / "evals.jsonl", run_dir / "updates.jsonl"] if p.exists()]

    row: dict[str, Any] = {
        "row_id": f"{method}.{resolved_run_id}",
        "method": method,
        "stack_depth": meta_info["stack_depth"],
        "run_id": resolved_run_id,
        "primary_metric": primary_metric,
        "reward_mode": meta_info["reward_mode"],
        "bootstrap_value": bootstrap_val,
        "final_value": final_val,
        "delta": delta,
        "ci_95_low": ci_low,
        "ci_95_high": ci_high,
        "eval_n": eval_n,
        "heldout_label": "frozen_4x32",
        "train_updates": int(report.get("train_steps") or len(updates) or 0),
        "rollouts_total": rollouts_total,
        "wall_clock_seconds": (int(report.get("elapsed_ms") or 0)) / 1000.0,
        "cost_usd_total": round(cost_usd, 6),
        "cost_input_tokens": inp,
        "cost_output_tokens": out,
        "delta_per_1k_rollouts": round(delta_per_1k, 6) if delta_per_1k is not None else None,
        "delta_per_dollar": round(delta_per_dollar, 6) if delta_per_dollar is not None else None,
        "accepted": accepted,
        "config_ref": _repo_relative(config_path) if config_path.exists() else None,
        "artifact_refs": artifact_refs,
        "limitations": limitations,
        "missing_public_packet": False,
    }
    row["source_ref"] = _canonical_source_ref(row)
    return row


# Two-sided 95% t-multipliers by degrees of freedom (n-1), for small-N seed CIs.
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
        7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}


def _t_ci(values: list[float | None]) -> tuple[float | None, float | None, float | None, float, int]:
    """(mean, ci_low, ci_high, std, n) for a small sample using the t-distribution.
    n<2 returns no interval (std=0)."""
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    if n == 0:
        return None, None, None, 0.0, 0
    mean = sum(vals) / n
    if n == 1:
        return mean, None, None, 0.0, 1
    var = sum((v - mean) ** 2 for v in vals) / (n - 1)
    std = var ** 0.5
    sem = std / (n ** 0.5)
    t = _T95.get(n - 1, 1.96)
    return mean, mean - t * sem, mean + t * sem, std, n


def _mean(values: list[float | None]) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def aggregate_seed_rows(method: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse N per-seed rows for one method into a single comparison row.

    CI on delta comes from ACROSS-seed spread when N>1 (the multi-seed CI the
    blog reports); for N==1 it falls back to the within-run bootstrap CI so the
    field is never silently empty. Per-seed detail is retained under `seed_runs`.
    """
    meta = METHOD_META.get(method, METHOD_META["cispo"])
    seed_run_ids = [r["run_id"] for r in rows]
    n_seeds = len(rows)

    delta_mean, delta_lo, delta_hi, delta_std, _ = _t_ci([r.get("delta") for r in rows])
    final_mean, final_lo, final_hi, _, _ = _t_ci([r.get("final_value") for r in rows])
    cost_mean, _, _, cost_std, _ = _t_ci([r.get("cost_usd_total") for r in rows])
    rollouts_mean = _mean([r.get("rollouts_total") for r in rows])

    if n_seeds == 1:
        ci_source = "within_run_bootstrap"
        delta_lo, delta_hi = rows[0].get("ci_95_low"), rows[0].get("ci_95_high")
    else:
        ci_source = "across_seed"

    eval_ns = {r.get("eval_n") for r in rows if r.get("eval_n")}
    eval_n = min(eval_ns) if eval_ns else None
    limitations = rows[0].get("limitations", "")
    if len(eval_ns) > 1:
        limitations = (limitations + " | seed runs had mismatched eval_n; reported min.").strip(" |")

    delta_per_dollar = (delta_mean / cost_mean) if (delta_mean is not None and cost_mean) else None
    delta_per_1k = (delta_mean / (rollouts_mean / 1000)) if (delta_mean is not None and rollouts_mean) else None

    seedset_hash = hashlib.sha256("|".join(sorted(seed_run_ids)).encode()).hexdigest()[:12]
    agg = {
        "row_id": f"{method}.seedset_{seedset_hash}",
        "method": method,
        "stack_depth": meta["stack_depth"],
        "primary_metric": meta["primary_metric"],
        "reward_mode": meta["reward_mode"],
        "heldout_label": "frozen_4x32",
        "eval_n": eval_n,
        "n_seeds": n_seeds,
        "seed_run_ids": seed_run_ids,
        "ci_source": ci_source,
        "bootstrap_value": _mean([r.get("bootstrap_value") for r in rows]),
        "final_value": final_mean,
        "final_value_ci_95_low": final_lo,
        "final_value_ci_95_high": final_hi,
        "delta": delta_mean,
        "delta_std": round(delta_std, 6),
        "ci_95_low": delta_lo,
        "ci_95_high": delta_hi,
        "cost_usd_total": round(cost_mean, 6) if cost_mean is not None else None,
        "cost_usd_total_std": round(cost_std, 6),
        "cost_input_tokens": int(_mean([r.get("cost_input_tokens") for r in rows]) or 0),
        "cost_output_tokens": int(_mean([r.get("cost_output_tokens") for r in rows]) or 0),
        "rollouts_total": int(rollouts_mean) if rollouts_mean is not None else None,
        "delta_per_1k_rollouts": round(delta_per_1k, 6) if delta_per_1k is not None else None,
        "delta_per_dollar": round(delta_per_dollar, 6) if delta_per_dollar is not None else None,
        "train_updates": rows[0].get("train_updates"),
        "config_ref": rows[0].get("config_ref"),
        "accepted": all(r.get("accepted", True) for r in rows),
        "limitations": limitations,
        "seed_runs": [
            {k: r.get(k) for k in ("run_id", "delta", "final_value", "cost_usd_total",
                                   "ci_95_low", "ci_95_high", "config_ref", "artifact_refs")}
            for r in rows
        ],
        "missing_public_packet": False,
    }
    agg["source_ref"] = _canonical_source_ref(agg)
    return agg


def _load_null_scaffold(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    payload = _read_json(path)
    rows = payload.get("honest_null_rows") or []
    for row in rows:
        row.setdefault("missing_public_packet", True)
    return rows


def parse_labeled_dir(token: str) -> tuple[str, Path, str | None]:
    if "=" not in token:
        raise argparse.ArgumentTypeError(f"expected method=path[@run_id], got {token!r}")
    method, rest = token.split("=", 1)
    method = method.strip()
    run_id: str | None = None
    if "@" in rest:
        path, run_id = rest.rsplit("@", 1)
        path = path.strip()
        run_id = run_id.strip() or None
    else:
        path = rest.strip()
    if not method or not path:
        raise argparse.ArgumentTypeError(f"invalid spec: {token!r}")
    return method, Path(path), run_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "-o", required=True, type=Path)
    parser.add_argument("--slug", default="crafter-rl-compute-uplift")
    parser.add_argument("--producer-commit", default=None)
    parser.add_argument(
        "--null-scaffold",
        type=Path,
        default=None,
        help="JSON file with honest_null_rows to merge (Jstack anchors until artifact-backed)",
    )
    parser.add_argument(
        "runs",
        nargs="+",
        type=parse_labeled_dir,
        help="method=path/to/run_dir or method=path/to/run_dir@run_id",
    )
    args = parser.parse_args(argv)

    # Group runs by method so N seed-runs collapse into one aggregated row.
    per_seed_by_method: dict[str, list[dict[str, Any]]] = {}
    method_order: list[str] = []
    instability_by_method: dict[str, list[dict[str, Any]]] = {}
    pareto_seed_points: list[dict[str, Any]] = []

    for method, run_dir, explicit_run_id in args.runs:
        run_dir = run_dir.resolve()
        seed_row = extract_crafter_rl_row(
            method,
            run_dir,
            run_id=explicit_run_id,
            limitations="Heldout mean achievement regressed vs bootstrap on n=128"
            if method == "ppo"
            else "",
        )
        per_seed_by_method.setdefault(method, []).append(seed_row)
        if method not in method_order:
            method_order.append(method)
        # Instability series from the first seed run per method (representative).
        if method not in instability_by_method:
            evals = _read_jsonl(run_dir / "evals.jsonl")
            updates = _read_jsonl(run_dir / "updates.jsonl")
            instability_by_method[method] = _instability_series(updates, evals)
        if seed_row.get("delta") is not None and seed_row.get("cost_usd_total"):
            pareto_seed_points.append({
                "method": method,
                "run_id": seed_row["run_id"],
                "x_cost_usd": seed_row["cost_usd_total"],
                "y_delta": seed_row["delta"],
                "seed": True,
            })

    comparison_rows = [aggregate_seed_rows(m, per_seed_by_method[m]) for m in method_order]

    # Aggregated frontier (one point per method); pareto_seed_points carries the spread.
    pareto_points = [
        {
            "method": r["method"],
            "n_seeds": r["n_seeds"],
            "x_cost_usd": r["cost_usd_total"],
            "y_delta": r["delta"],
            "y_ci_95_low": r["ci_95_low"],
            "y_ci_95_high": r["ci_95_high"],
            "accepted": r["accepted"],
        }
        for r in comparison_rows
        if r.get("delta") is not None and r.get("cost_usd_total")
    ]

    honest_null_rows = _load_null_scaffold(args.null_scaffold)
    has_incomplete = any(r.get("missing_public_packet") for r in comparison_rows)
    if honest_null_rows:
        has_incomplete = True

    packet = {
        "schema_version": "crafter_rl_compute_uplift_evidence_packet.v1",
        "slug": args.slug,
        "status": "generated_partial" if has_incomplete else "generated",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer_commit": args.producer_commit,
        "pricing_table_version": PRICING_TABLE_VERSION,
        "heldout_seed_manifest": {
            "eval_seeds": [581, 582, 583, 584],
            "eval_samples_per_seed": 32,
            "eval_n": 128,
        },
        "comparison_rows": comparison_rows,
        "honest_null_rows": honest_null_rows,
        "pareto_points": pareto_points,
        "pareto_seed_points": pareto_seed_points,
        "instability_window": instability_by_method,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(packet, handle, indent=2, sort_keys=True)
        handle.write("\n")

    seed_summary = ", ".join(f"{r['method']}:{r['n_seeds']}seed" for r in comparison_rows)
    print(f"wrote {args.output} ({len(comparison_rows)} method rows — {seed_summary}; status={packet['status']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())