# Live seeds (container + env)

Status: normative — 2026-06-16  
Parent: [`deterministic_tasks.md`](deterministic_tasks.md), [`task_bundle_format.md`](task_bundle_format.md)

## Idea

A **seed** is a deterministic task identity (`seed` + `scenario_id` + bundled policies). Parallel eval needs **many live episodes at once**, each isolated.

Two supported deployment patterns:

### A) Env service + parallel policy rollouts (split)

```text
                    ┌─────────────────────────────┐
  seed=101 rollout  │  Env service (gold HTTP)  │
  seed=102 rollout  │  sessions[rollout_id]     │
  seed=103 rollout  │  /reset  /rollouts/{id}/step │
                    └─────────────────────────────┘
                              ▲
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   Container rollout     Container rollout     Container rollout
   (Groq vs minimax)     (Groq vs minimax)     (Groq vs minimax)
```

1. Start the **env service** once (`gold/service.py` or container image that only exposes env routes).
2. For each seed, **reset** → receive `rollout_id` (deterministic from `seed` + `scenario_id`).
3. All later env calls use that id as the path prefix: `/rollouts/{rollout_id}/step`, `/state`, `/events`.
4. Fan out **N container rollouts** in parallel; each worker owns one seed and one `rollout_id`.

The seed is not repeated on every step body — it is fixed at **reset** and encoded in `rollout_id`.

```http
POST /reset
{"scenario_id": "groq_vs_minimax_101", "seed": 101, "task_id": "groq_vs_minimax_101"}
→ rollout_id = episode_id_from_task(...)   # stable per seed+task

POST /rollouts/{rollout_id}/step
{"action": {"player": "X", "position": 4}, "observation_profile": "llm_text"}
```

Gold service keeps a **session map** `rollout_id → live engine`. Many seeds = many concurrent sessions.

**Same seed in parallel:** two workers with seed `101` get the same deterministic `rollout_id` and would collide on one session. For concurrent replays of one seed, prefix with `trace_correlation_id` when minting rollout handles (future) or use distinct `task_id` per trial.

### B) Monolithic container `/rollout` (NanoLong-style)

One HTTP call runs the full episode in-process (`spawn_env` per request). No separate env service. Parallel eval = N concurrent `POST /rollout` with different seeds.

Use when the policy loop (Groq + minimax) should stay inside the container and you do not need step-wise env access from outside.

## In-process env contract

```python
spec = SeedSpec(seed=101, agent_mark="X")
env = spawn_env(spec)   # fresh TictactoeSingleplayerEnv
```

Rules:

| Rule | Why |
|------|-----|
| One live engine per `rollout_id` / spawn | Concurrency + parity |
| `episode_id` / `rollout_id` from `task_id` + `seed` | Deterministic tasks |
| Policies use `(public, seed, ply)` only | No hidden service RNG |

## Container HTTP (policy rollout lane)

| Route | Multi-seed |
|-------|------------|
| `GET /task_info?seeds=101&seeds=102` | batch introspection |
| `POST /rollout` | one seed per body; N parallel requests |

No eval routes on containers. Clients fan out rollouts.

## Gold env service HTTP (session lane)

| Route | Role |
|-------|------|
| `POST /reset` | mint `rollout_id` for a seed |
| `POST /rollouts/{rollout_id}/step` | step one live session |
| `GET /rollouts/{rollout_id}/state` | observation |
| `GET /rollouts/{rollout_id}/events` | NEV |

`supports_many_live_seeds: true` on env service health when session map is concurrent-safe (one engine per `rollout_id`).

## Parallel eval (client)

Fan out N rollout workers (container `/rollout` or env reset + step loops). See `container/parallel_eval.py`.

## Capacity and limits

Normative pool policy: [`env_session_pool.md`](env_session_pool.md).
