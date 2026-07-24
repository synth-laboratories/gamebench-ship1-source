# NEV log (in-game event log)

Status: v0 — 2026-06-16  
See: [`canonical_sim_target.txt`](../canonical_sim_target.txt)

## Purpose

Append-only ordered stream of what happened **inside the sim**. Primary GameBench correctness substrate.

## EventRecord envelope (all env families)

| Field | Type | Notes |
|-------|------|-------|
| `step_index` | int | Monotonic per episode; restored with checkpoint |
| `sim_tick` | int | Same as step_index for turn-based games |
| `episode_id` | string | Stable episode handle |
| `kind` | enum | See kinds below |
| `severity` | enum | `info`, `warn`, `error` |
| `message` | string | One-line human text for TUI |
| `action` | object? | Normalized action when applicable |
| `transition` | object? | Diff summary or kind-specific payload |
| `payload` | object | Extensible per env |

### Kinds

`action_applied`, `state_transition`, `rule_violation`, `achievement`, `resource_delta`, `entity_spawn`, `entity_despawn`, `terminal`, `debug`

## Tic-Tac-Toe payload examples

```json
{
  "kind": "action_applied",
  "message": "MoveApplied(X,4)",
  "action": {"player": "X", "position": 4},
  "payload": {"player": "X", "position": 4}
}
```

```json
{
  "kind": "terminal",
  "message": "GameEnded(draw,draw)",
  "payload": {"winner": "draw", "reason": "draw"}
}
```

```json
{
  "kind": "rule_violation",
  "severity": "error",
  "message": "position already occupied",
  "payload": {"position": 4, "board_cell": "X"}
}
```

## Legacy string export

`game-engine-coding-tasks` oracle uses strings like `TurnStarted(O)`. Gold reference exports:

```python
nev.legacy_strings()  # ["GameStarted(...)", "MoveApplied(X,4)", ...]
```

Structured records are canonical; strings are derived for cross-repo parity.

## Checkpoint coupling

`nev_cursor` = `len(events)` stored in checkpoint blob. `restore()` must preserve cursor so resume does not duplicate or drop events.

## Export surfaces

- Step response: `nev_tail` (last N events)
- `GET /rollouts/{id}/events` — full JSONL-compatible list
- Golden files: `envs/<family>/gold/<scenario>.nev.json`
