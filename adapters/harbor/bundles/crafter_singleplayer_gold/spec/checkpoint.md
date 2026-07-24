# Checkpoint blob

Status: v0 — 2026-06-16  
See: [`canonical_sim_target.txt`](../canonical_sim_target.txt)

## Minimal blob (default)

```json
{
  "schema_version": "gamebench.checkpoint.v1",
  "env_family": "tictactoe-singleplayer",
  "episode_id": "...",
  "step_index": 3,
  "nev_cursor": 7,
  "config_hash": "sha256:...",
  "sim": { ... engine-specific public+private fields ... }
}
```

Tic-Tac-Toe `sim` holds: `board`, `turn`, `winner`, `scenario_id`, `seed`, `ply`.

Render cache is **not** included in minimal profile.

## Budgets (v0 draft)

| Metric | Tic-Tac-Toe target | GameBench general |
|--------|-------------------|-------------------|
| Blob size | ≤ 4 KB | ≤ 64 KB typical |
| Save p50 | ≤ 1 ms | ≤ 5 ms |
| Restore p50 | ≤ 1 ms | ≤ 10 ms |
| Restore p99 | ≤ 5 ms | ≤ 50 ms |

Run: `python scripts/bench_checkpoint.py`

## RestoreReport

```json
{
  "bytes": 512,
  "wall_ms": 0.12,
  "nev_events_restored": 7,
  "render_cache_hit": false
}
```

## synth-containers mapping

- `POST /rollouts/{rollout_id}/checkpoints` → save minimal blob
- `GET /checkpoints/{checkpoint_id}/export` → blob bytes
- `POST /checkpoints/import` → restore into new or same rollout
