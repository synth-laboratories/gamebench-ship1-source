# HTTP protocol — Tic-Tac-Toe multiplayer gold

## Health

```json
{"ok": true, "engine": "tictactoe-multiplayer-gold", "env_family": "tictactoe-multiplayer"}
```

## Agents

`GET /agents` → `{"agents": ["agent_0", "agent_1"]}`

## Step (joint action)

`POST /rollouts/{rollout_id}/step`

```json
{
  "joint_action": {
    "agent_0": {"kind": "place", "position": 4},
    "agent_1": {"kind": "wait"}
  },
  "observation_profile": "llm_text"
}
```

Response includes `observations` (per agent), `rewards`, `dones` (with `__all__`), and `info.last_joint_event`.

See [`spec/marl_env_standards.md`](../../../spec/marl_env_standards.md).
