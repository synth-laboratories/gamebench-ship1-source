# DungeonGrid Multiplayer

DungeonGrid is a deterministic, turn-based party environment with matching Rust and pure-Python engines. Scenarios may use any non-empty `hero_roles` list; the MAPO coordination dataset instantiates four agents with `barbarian`, `wizard`, `rogue`, and `cleric` roles.

## Observation and communication settings

The optional top-level `observation` object controls the agent information boundary:

```json
{
  "observation": {
    "mode": "local",
    "visibility_radius": 3,
    "communication_enabled": true
  }
}
```

- `mode: "global"` preserves the original full-state observation and is the default for scenarios that omit the object.
- `mode: "local"` exposes only entities and terrain within Manhattan `visibility_radius`. Unseen map cells render as `?`, unrevealed traps are omitted, and `StepResult.info` follows the same local boundary instead of leaking verifier state.
- `communication_enabled` controls whether `message` is legal. Direct messages target an agent id; `party` broadcasts to every other hero. Delivered messages persist in each recipient's `inbox` and in checkpoints.

`rich_state()` remains an authoritative verifier/admin surface. Policies should consume `observation` and must not receive `rich_state()` out of band.

The MAPO dataset in `defaults/mapo_coordination/dataset_v1.json` turns on four-agent local visibility and communication. Its matched `event_triggered_channel_masked` arm executes the same inbox-conditioned policy while dropping message delivery, separating communication effects from a different action policy.
