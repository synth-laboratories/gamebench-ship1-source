# MARL env standards (GameBench)

Status: normative — 2026-06-16  
Lineage: JaxMARL / OvercookedV2 (NanoCoop), PettingZoo conventions

## Agent identity

- Fixed string agent ids: `agent_0`, `agent_1`, … (`agent_{i}` zero-based)
- Stable across reset, checkpoint, NEV, HTTP, and task bundles
- Task bundle maps roles to ids (e.g. TTT: `agent_0` = X, `agent_1` = O)

## Step contract (joint action)

Every env step accepts a **joint action dict**, even when only one agent moves:

```json
{
  "agent_0": {"kind": "place", "position": 4},
  "agent_1": {"kind": "wait"}
}
```

Overcooked/JaxMARL simultaneous example:

```python
env.step_env(key, state, {"agent_0": primitive0, "agent_1": primitive1})
```

Turn-based games (tic-tac-toe multiplayer) use the same joint dict; non-acting agents send `{"kind": "wait"}`.

## Step return shape

```python
observations: dict[str, dict]   # per agent_id
rewards: dict[str, float]       # per agent_id
dones: dict[str, bool]          # per agent_id + "__all__"
info: dict[str, Any]
```

## Observations

Per-agent observations keyed by agent id. Each obs should include:

- `agent_id`
- `agent_index` (0-based int)
- `legal_agent_ids` or action mask for that agent
- `last_joint_event` (optional, NanoCoop pattern)

## NEV log

Multi-agent steps append joint-aware events:

- `GameStarted(<task_id>)`
- `JointTurn(agent_0)` / `JointTurn(agent_1)` — whose move is active (turn-based)
- `MoveApplied(agent_0,4)` — player tag is agent id or mark
- `GameEnded(agent_0,win)` or `GameEnded(draw,draw)`

Gold comparisons use the same legacy string NEV as single-agent lanes.

## Task bundle

Use [`task_bundle_format.md`](task_bundle_format.md) — `agent_0_policy` / `agent_1_policy`, shared across gold tasks. `env_family` selects step API only.

```json
{
  "schema_version": "gamebench.task.v1",
  "task_id": "ttt_mp_001",
  "env_family": "tictactoe-multiplayer",
  "seed": 101,
  "agent_0_policy": {"kind": "registry", "policy_id": "win_block_center_v1"},
  "agent_1_policy": {"kind": "registry", "policy_id": "block_win_center_v1"}
}
```

All randomness from task `seed` + policy `(seed, ply)` — see [`deterministic_tasks.md`](deterministic_tasks.md).

## HTTP service

Same container routes as single-player, plus:

- `POST /step` body: `{"joint_action": {...}, "observation_profile": "llm_text"}`
- `GET /agents` → `["agent_0", "agent_1"]`
- `env_family` in `/health` distinguishes `tictactoe-multiplayer` vs `tictactoe-singleplayer`
