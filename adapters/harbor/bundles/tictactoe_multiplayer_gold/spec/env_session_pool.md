# Env session pool (live rollouts)

Status: normative — 2026-06-16  
Parent: [`live_seeds.md`](live_seeds.md), [`deterministic_tasks.md`](deterministic_tasks.md)

## Problem

Parallel eval (e.g. 100 Groq agents vs minimax on 100 unique seeds) needs the **env service** to hold many **live** engines at once. Each session owns:

- public + private sim state
- full NEV log (grows with plies)
- optional in-memory checkpoints

That memory is **bounded per instance** — you cannot host 1M concurrent tic-tac-toe episodes in one process without sharding.

## Model

```text
Eval client                    Env service
──────────                     ───────────
task_id=ttt_101, seed=101  →   POST /reset  → sessions[rollout_id]
task_id=ttt_102, seed=102  →   POST /reset  → sessions[rollout_id]
   … 98 more in parallel …
Groq worker for 101        →   POST /rollouts/{id}/step
```

- **One live engine per `rollout_id`** (`rollout_id` = deterministic `episode_id` from `task_id` + `seed`).
- **Unique `task_id` per seed** in a batch eval → unique `rollout_id` → no collision.
- Pool enforces **max concurrent live sessions**, **idle TTL**, and **release when terminal**.

## Lifecycle

| Phase | HTTP | Pool behavior |
|-------|------|----------------|
| Admit | `POST /reset` | Create engine; evict terminated + idle if needed; **429** if still full |
| Active | `POST /rollouts/{id}/step` | Touch session; mark `terminated` when episode ends |
| Release | terminal step or `DELETE /rollouts/{id}` | Drop engine + NEV from memory |
| Stale | idle past TTL | Evicted on next admit or `POST /pool/evict_idle` |

Default: **`auto_release_on_terminal=true`** — finished games free a slot immediately so a 100-wide eval does not leave 100 dead sessions until TTL.

## Capacity planning (tic-tac-toe multiplayer)

Observed gold budgets (see eval reports):

| Component | Typical | Hard max |
|-----------|---------|----------|
| Checkpoint blob | ~5 KB | 64 KB |
| NEV + Python overhead | ~10–20 KB | — |
| **Planning estimate per session** | **32 KB** | **64 KB** |

| Concurrent sessions | Est. RAM (32 KB/session) | Notes |
|---------------------|--------------------------|-------|
| 100 | ~3 MB | Comfortable default eval |
| 256 | ~8 MB | Default `max_active_sessions` |
| 10,000 | ~320 MB | Needs higher limit + monitoring |
| 1,000,000 | ~32 GB | **Not one process** — shard env services |

Limits are **env-family specific**. Sokoban / long-horizon games need higher `estimated_bytes_per_session` and lower `max_active_sessions`.

## Configuration (env vars)

| Variable | Default | Meaning |
|----------|---------|---------|
| `GAMEBENCH_ENV_MAX_SESSIONS` | `256` | Max live sessions |
| `GAMEBENCH_ENV_IDLE_TTL_SEC` | `600` | Drop untouched sessions after N seconds |
| `GAMEBENCH_ENV_AUTO_RELEASE_TERMINAL` | `1` | Free slot when episode terminates |
| `GAMEBENCH_ENV_BYTES_PER_SESSION` | `32768` | Planning estimate for `/pool` stats |

## HTTP surface

| Route | Role |
|-------|------|
| `GET /health` | `pool` stats + `supports_many_live_seeds` |
| `GET /pool` | Full pool stats |
| `POST /pool/evict_idle` | Operator sweep (returns evicted count) |
| `DELETE /rollouts/{rollout_id}` | Explicit close |

**429** on `POST /reset` when pool is full:

```json
{
  "detail": "env session pool full",
  "pool": { "active_sessions": 256, "max_active_sessions": 256, ... }
}
```

Clients should retry with backoff or reduce parallelism.

## Client pattern (100 parallel Groq eval)

1. Mint 100 tasks: distinct `task_id` + `seed` each.
2. `POST /reset` for all 100 (async fan-out, respect 429).
3. Each Groq worker loops `step` on its `rollout_id` until `terminated`.
4. Slots auto-release; optional `DELETE` if worker aborts mid-episode.

Alternative: monolithic container `POST /rollout` (no session pool) when you do not need step-wise env HTTP.

Implementation: [`runtime/session_pool.py`](../runtime/session_pool.py), wired in gold `service.py`.
