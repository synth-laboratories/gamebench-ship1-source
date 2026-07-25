# Spectrum correctness (ProgramBench-style)

Status: normative — 2026-06-16  
Parent: [`deterministic_tasks.md`](deterministic_tasks.md), [`marl_env_standards.md`](marl_env_standards.md)

## Question

How correct is a candidate sim implementation — as a **spectrum**, not only pass/fail?

Lineage: [ProgramBench](https://programbench.com) reports **resolved** (100% behavioral tests), **almost** (≥95%), and extended average pass rates.

GameBench uses **NEV events** + **public state** as behavioral tests across fixed scenario seeds.

## Per-scenario signals

| Signal | Definition |
|--------|------------|
| `nev_hit_rate` | Matching legacy NEV strings at each index / `len(gold_events)` |
| `public_hit_rate` | Fraction of compared public fields matching gold terminal public dict |
| `resolved` | `nev_hit_rate == 1.0` and `public_hit_rate == 1.0` |
| `almost` | `nev_hit_rate >= 0.95` and `public_hit_rate >= 0.95` |
| `http_ok` | HTTP `/run_scenario` completed without transport errors |

NEV is the **primary** parity surface; public state is the secondary symbolic check.

## Aggregate leaderboard metrics

Report these for a model + harness (e.g. Harbor + GPT-5.4-mini):

| Metric | Meaning |
|--------|---------|
| `resolved_rate` | Fraction of scenarios fully correct |
| `almost_rate` | Fraction ≥95% on NEV + public |
| `mean_nev_hit_rate` | Average `nev_hit_rate` across scenarios |
| `mean_public_hit_rate` | Average `public_hit_rate` |
| `http_lane_mean_nev` | Same metrics on HTTP candidate lane |

**Primary headline:** `resolved_rate` (like ProgramBench resolved).  
**Secondary:** `almost_rate` while resolved is sparse.  
**Diagnostic:** per-scenario table + `mean_nev_hit_rate` curve.

## Lanes

1. **Local in-process** — import candidate `gold` package (fast dev)
2. **HTTP service** — spawn `scripts/run_service.py` and exercise `/run_scenario`
3. **Harbor** — Codex agent in Docker workspace; verifier runs HTTP lane against `workspace/candidate`

Gold reference should score **100%** on all metrics.

## Harbor verifier reward

Default Harbor `reward.txt` for spectrum tasks:

```text
reward = mean_nev_hit_rate
```

Optional gates (document per task):

- hard fail if `http_ok` is false for any scenario
- cap reward at `0.5` if `mean_public_hit_rate < 0.5`

Implementation: `tasks/tictactoe-multiplayer/scripts/spectrum_eval.py`, Harbor `harbor/tictactoe_multiplayer_gold/tests/test.sh`.
