# GameBench task bundle format (tic-tac-toe gold)

Status: normative — 2026-06-16  
Parent: [`deterministic_tasks.md`](deterministic_tasks.md)

Gold reference tasks under `tasks/tictactoe-*` share one **task bundle schema**. Lane differences are only `env_family` and step API (single action vs joint action).

## Task JSON (`gamebench.task.v1`)

Required fields:

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | string | `gamebench.task.v1` |
| `task_id` | string | Stable id; matches gold fixtures when present |
| `env_family` | string | `tictactoe-singleplayer` or `tictactoe-multiplayer` |
| `scenario_id` | string | Rollout identity (often equals `task_id`) |
| `seed` | int | RNG root for env + seeded policies |
| `max_plies` | int | Horizon cap |
| `opening_moves` | list | Scripted prefix before policy loop |
| `agent_0_policy` | object | Policy spec for X (`agent_0`) |
| `agent_1_policy` | object | Policy spec for O (`agent_1`) |

Optional: `episode_id` (otherwise derived from `task_id` + `seed`).

### Agent mapping (fixed)

| Agent id | Mark | Role |
|----------|------|------|
| `agent_0` | X | first player |
| `agent_1` | O | second player |

Canonical board + agent constants live in `tasks/tictactoe-multiplayer/gold/board.py`. Single-player gold re-exports via `tasks/tictactoe-singleplayer/gold/mp_board.py`.

### Policy spec

```json
{"kind": "registry", "policy_id": "win_block_center_v1"}
```

```json
{"kind": "monty_python", "module": "win_block_center_v1", "entry": "choose_action"}
```

Legacy aliases (`x_policy`, `o_policy`) are accepted by scenario runners during migration only — new tasks must use `agent_0_policy` / `agent_1_policy`.

### Opening moves

**Single-player** (`tictactoe-singleplayer`): list of `{"player": "X", "position": 4}`.

**Multiplayer** (`tictactoe-multiplayer`): list of joint steps:

```json
{
  "joint_action": {
    "agent_0": {"kind": "place", "position": 4},
    "agent_1": {"kind": "wait"}
  }
}
```

Legacy opening entries with `player` + `position` are converted to joint dicts by the multiplayer runner.

## Fixture scenarios (`gamebench.scenarios.v1`)

Gold fixture files under `fixtures/gold/scenarios/scenarios.json`:

```json
{
  "schema_version": "gamebench.scenarios.v1",
  "scenarios": [
    {
      "schema_version": "gamebench.scenario.v1",
      "scenario_id": "ttt_001_empty_win_vs_block",
      "seed": 101,
      "max_plies": 9,
      "opening_moves": [],
      "agent_0_policy_id": "win_block_center_v1",
      "agent_1_policy_id": "block_win_center_v1"
    }
  ]
}
```

Scenario runners expand `agent_*_policy_id` into full task objects for `run_scenario`.

## Lane-specific step API

| `env_family` | Step input |
|--------------|------------|
| `tictactoe-singleplayer` | `{"player": "X", "position": 4}` |
| `tictactoe-multiplayer` | `joint_action` dict per [`marl_env_standards.md`](marl_env_standards.md) |

Same policies and seeds produce the same board trajectory; NEV strings differ by lane (`TurnStarted` vs `JointTurn`, mark vs agent id in `MoveApplied`).
