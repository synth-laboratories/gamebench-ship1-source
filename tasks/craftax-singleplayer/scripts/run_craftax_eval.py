#!/usr/bin/env python3
"""Run and compare Craftax policy arms without lying about the result.

Two failure modes this exists to prevent, both of which produced a wrong answer
before it existed (see ../image_input.md):

1. **Silently dropping failed seeds.** A rollout that errors is not a neutral
   loss. The rollouts that fail are the long ones — big transcripts, more
   requests, more chances to hit a timeout — so dropping them biases every arm
   toward early deaths, and biases it *differently* per arm depending on how
   expensive that arm's turns are. This driver retries, then refuses to print a
   comparison at all when an arm is short of seeds unless you pass
   `--allow-missing`.

2. **Reporting the mean as if it were the result.** On Craftax the mean is
   mostly a function of how many seeds survive the early game — survivors score
   ~15, deaths ~4 — and with ten seeds that is a coin flip. Three runs of an
   identical configuration gave means of 9.61 / 9.51 / 7.09. So the mean is
   printed with a bootstrap interval and is *not* the headline; survival count
   and achievement union are, because "this achievement was never reached" does
   not drift the way an average does.

Example:

    python3 scripts/run_craftax_eval.py \
        --base-url http://127.0.0.1:8300 --seeds 30 --max-steps 1000 \
        --arm text:'{"observation_mode":"text"}' \
        --arm both:'{"observation_mode":"both"}' \
        --out .out/modality
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

BASE_POLICY: dict[str, Any] = {
    "use_lm": True,
    "provider": "openrouter",
    "model": "openai/gpt-5.6-luna",
    "reasoning_effort": "medium",
    "max_tokens": 1024,
    "max_llm_turns": 150,
    "min_actions_per_call": 4,
    "max_actions_per_call": 8,
    "react_mode": "conversation",
    "context_token_budget": 16000,
    "compact_at": 0.7,
    "keep_recent_messages": 8,
}

# A rollout that ran this far engaged with the game; below it, the episode was
# decided by an early death rather than by the policy under test.
SURVIVAL_STEPS = 500


def post(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"content-type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def run_seed(
    base_url: str, arm: str, overrides: dict[str, Any], seed: int, max_steps: int,
    world: str, timeout: float, attempts: int,
) -> dict[str, Any]:
    policy = {**BASE_POLICY, **overrides}
    body = {
        "seed": seed,
        "rollout_id": f"craftax_{arm}_seed_{seed}",
        "env": {"seed": seed, "config": {"max_steps": max_steps, "world": {"use_default": world}}},
        "policy": {"config": policy},
    }
    last = ""
    for attempt in range(1, attempts + 1):
        started = time.time()
        try:
            record = post(f"{base_url}/rollout", body, timeout)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            last = f"{type(exc).__name__}: {str(exc)[:160]}"
            print(json.dumps({"arm": arm, "seed": seed, "attempt": attempt, "retrying": last}), flush=True)
            time.sleep(min(30, 2**attempt))
            continue
        summary = record.get("summary", {})
        row = {
            "arm": arm, "seed": seed, "reward": record.get("reward"),
            "env_steps": summary.get("env_steps"), "llm_turns": summary.get("policy_llm_turns"),
            "achievements": record.get("final_achievements") or [],
            "world": (summary.get("world") or {}).get("preset"),
            "is_reference_world": (summary.get("world") or {}).get("is_reference_world"),
            "context": summary.get("context"), "usage": record.get("usage"),
            "wall_s": round(time.time() - started, 1),
        }
        print(json.dumps({k: row[k] for k in ("arm", "seed", "reward", "env_steps", "llm_turns", "wall_s")}), flush=True)
        return row
    return {"arm": arm, "seed": seed, "reward": None, "error": last}


def bootstrap_ci(values: list[float], iterations: int = 5000, seed: int = 0) -> tuple[float, float] | None:
    """Percentile bootstrap. Makes no normality assumption, which matters here:
    Craftax rewards are bimodal (early deaths vs deep survivors), not bell-shaped."""
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    means = sorted(
        statistics.mean(rng.choices(values, k=len(values))) for _ in range(iterations)
    )
    return means[int(0.025 * iterations)], means[int(0.975 * iterations)]


def summarize(arm: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in rows if r.get("reward") is not None]
    rewards = [r["reward"] for r in scored]
    survivors = [r for r in scored if (r.get("env_steps") or 0) > SURVIVAL_STEPS]
    achievements = sorted({a for r in scored for a in (r.get("achievements") or [])})
    ci = bootstrap_ci(rewards) if rewards else None
    return {
        "arm": arm,
        "attempted": len(rows),
        "scored": len(scored),
        "failed_seeds": [r["seed"] for r in rows if r.get("reward") is None],
        "mean": statistics.mean(rewards) if rewards else None,
        "mean_ci95": ci,
        "median": statistics.median(rewards) if rewards else None,
        "max": max(rewards) if rewards else None,
        "survivors": len(survivors),
        "survival_rate": (len(survivors) / len(scored)) if scored else None,
        "achievement_union": achievements,
        "achievement_count": len(achievements),
        "total_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) for r in scored),
        "non_reference_world": sorted(
            {r["seed"] for r in scored if r.get("is_reference_world") is False}
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8098")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--world", default="craftax_default")
    parser.add_argument("--arm", action="append", required=True,
                        help='name:{"json":"overrides"} — repeatable')
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path(".out/craftax_eval"))
    parser.add_argument("--allow-missing", action="store_true",
                        help="report even when an arm lost seeds (biased; off by default)")
    args = parser.parse_args()

    arms: dict[str, dict[str, Any]] = {}
    for spec in args.arm:
        name, _, raw = spec.partition(":")
        arms[name] = json.loads(raw or "{}")
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))

    jobs = [(arm, overrides, seed) for arm, overrides in arms.items() for seed in seeds]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(
            lambda job: run_seed(args.base_url, job[0], job[1], job[2], args.max_steps,
                                 args.world, args.timeout, args.attempts),
            jobs,
        ))

    by_arm: dict[str, list[dict[str, Any]]] = {arm: [] for arm in arms}
    for row in results:
        by_arm[row["arm"]].append(row)
    summaries = {arm: summarize(arm, rows) for arm, rows in by_arm.items()}

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(
        json.dumps({"seeds": seeds, "arms": summaries, "rows": results}, indent=2) + "\n"
    )

    print(f"\n{'arm':>10} {'scored':>8} {'survivors':>10} {'achv':>5} {'mean':>7} {'95% CI':>16} {'median':>7}")
    for arm, s in summaries.items():
        ci = f"[{s['mean_ci95'][0]:.1f}, {s['mean_ci95'][1]:.1f}]" if s["mean_ci95"] else "—"
        mean = f"{s['mean']:.2f}" if s["mean"] is not None else "—"
        med = f"{s['median']:.2f}" if s["median"] is not None else "—"
        print(f"{arm:>10} {s['scored']:>4}/{s['attempted']:<3} {s['survivors']:>6}/{s['scored']:<3} "
              f"{s['achievement_count']:>5} {mean:>7} {ci:>16} {med:>7}")

    names = list(summaries)
    if len(names) > 1:
        base = names[0]
        print(f"\nachievements vs {base!r}:")
        base_set = set(summaries[base]["achievement_union"])
        for arm in names[1:]:
            arm_set = set(summaries[arm]["achievement_union"])
            print(f"  only in {arm:>8}: {sorted(arm_set - base_set) or '—'}")
            print(f"  only in {base:>8}: {sorted(base_set - arm_set) or '—'}")

    problems: list[str] = []
    for arm, s in summaries.items():
        if s["failed_seeds"]:
            problems.append(f"{arm}: lost seeds {s['failed_seeds']} — long rollouts fail "
                            f"preferentially, so this sample is biased toward early deaths")
        if s["non_reference_world"]:
            problems.append(f"{arm}: seeds {s['non_reference_world']} did not run the reference "
                            f"world; those scores are not Craftax results")
    if problems:
        print("\n" + "\n".join(f"WARNING  {p}" for p in problems))
        if not args.allow_missing:
            print("\nRefusing to present this as a comparison. Re-run the missing seeds, "
                  "or pass --allow-missing if you accept the bias.")
            return 1

    if len(names) > 1:
        print(f"\nNote: with {len(seeds)} seeds the mean is dominated by the survival count. "
              f"Treat a difference smaller than the CI width as unresolved, and prefer the "
              f"achievement and survivor columns.")
    print(f"\nreceipts: {args.out}/results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
