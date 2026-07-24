# Deterministic tasks — hard rule

Status: normative — 2026-06-16  
Parent: [`canonical_sim_target.txt`](../../canonical_sim_target.txt)

## The rule

**All randomness and time enter the sim only through the task bundle.**  
Two implementations running the same task with the same deterministic policy trace must produce **identical** NEV logs and identical comparable state. No wall clock, no ambient RNG, no server-generated IDs in the parity surface.

## Evaluation model (all env families)

```text
Task bundle (JSON + policies/maps/rules)
        │
        ├─► Local gold engine (reference lane)
        │
        └─► HTTP env service (candidate lane)
                │
                ▼
        Same scripted actions OR same policy replay inputs (seed, ply)
                │
                ▼
        Compare: NEV (primary) + public/symbolic state + optional render hash
```

Every env must be **runnable as a service** (container HTTP). The eval harness never imports candidate code; it only talks HTTP and loads tasks from disk.

## What the task bundle must fix

| Input | Required | Notes |
|-------|----------|-------|
| `task_id` | yes | Stable identity for gold files and reports |
| `seed` | yes | Single RNG root for env + seeded policies |
| `scenario_id` / world key | yes | Crafter: profile + dimensions; NetHack: dungeon seed |
| Opening script | if needed | Explicit moves before policy loop (`opening_moves`, map preset, …) |
| Policies | yes | Deterministic opponent/agent scripts bundled with task (`monty_python`, registry id + seed) |
| `max_plies` / horizon | yes | Caps non-terminal rollouts |
| `episode_id` | optional | If omitted, derived deterministically from `task_id` + `seed` |

**Forbidden as parity inputs:** `uuid4()`, `time.time()`, host PID, rollout/session IDs unless explicitly listed in the task and identical across lanes.

## What we compare (parity surface)

**Must match exactly between implementations:**

1. NEV log — legacy string sequence or structured `EventRecord` list (primary)
2. Public state at each checkpoint boundary (board, inventory, pose, …)
3. Private state **excluding** session bookkeeping (`episode_id`, HTTP rollout handles)
4. Checkpoint blob size at each step (optional perf gate; content should match if encoding is canonical)

**Do not compare:** HTTP `rollout_id`, `checkpoint_id`, wall-clock fields, episode UUIDs unless task-fixed.

## Deterministic policy contract

Policies are part of the task, not the service:

```python
def choose_action(public: dict, seed: int, ply: int) -> dict:
    ...
```

- `seed` and `ply` always come from the task replay loop, never from the service.
- Seeded tie-break (`seeded_legal_v1`) uses `hash(seed, ply, candidate)` — fully task-pinned.
- Eval harness collects actions once (gold policy runner) and may replay the same action list on both lanes.

## Service requirements

Each env HTTP service must support:

- `POST /run_scenario` — task JSON in, terminal NEV + state out (bulk replay)
- `POST /reset` + `POST /rollouts/{id}/step` — scripted action replay
- Checkpoint save/export/import — restore must preserve NEV cursor + sim state
- `GET /health` — report `env_family` for spawn verification

Candidate implementations must not read clock or OS RNG during `step` unless driven by task-held RNG state.

## Eval report (`eval_gold.py`)

Three pillars per run:

1. **Correctness** — NEV + public state parity (fixtures, local vs HTTP)
2. **Performance** — latency samples + checkpoint size budgets
3. **Code metrics** — SLOC, logical LOC, cyclomatic complexity per file (`gold/code_metrics.py`)

Optional `--candidate-src` compares gold vs candidate implementation size/complexity.


| Item | Status |
|------|--------|
| Task carries seed, policies, opening_moves | yes |
| Deterministic `episode_id` from task | yes (engine) |
| Local vs HTTP NEV + public compare | yes (`eval_gold.py`) |
| Gold fixture event logs | yes (`fixtures/gold/eventlogs/`) |
| Wall clock in NEV/state | none |

## Crafter / future envs

Task bundle adds:

- `rules_profile` / config hash
- `world_width`, `world_height`, `map_seed` or full map preset
- Monty rule snippets for scenario-specific validators
- Opponent policy modules (same Monty pattern as TTT)

Same rule: **map + rules + seed + policies = entire variability.** Two Crafter replicas must match NEV and symbolic state on the same task, not pixels-first.
