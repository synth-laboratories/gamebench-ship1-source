# MiniHack Gold HTTP Contract

Both gold lanes expose the same local development surface.

| Route | Body | Response |
| --- | --- | --- |
| `GET /health` | none | lane id, env family, session count |
| `POST /run_scenario` | `{ "task": { ... task JSON with optional actions ... } }` | legacy NEV strings, terminal state, readout |
| `POST /rollouts` | task JSON and optional `seed` | `rollout_id`, readout, NEV cursor |
| `POST /rollouts/{id}/step` | `{ "action": { "kind": "move", "direction": "east" } }` or direction string | readout, reward, done flags |
| `POST /rollouts/{id}/checkpoint` | none | base64 blob, byte count, NEV cursor |
| `POST /rollouts/{id}/restore` | `{ "blob": "..." }` | restore report and readout |
| `POST /rollouts/{id}/simulate` | `{ "blob": "...", "sequences": [[{"kind":"move","direction":"south"}]] }` | batch branch results |
| `GET /rollouts/{id}/readout` | none | symbolic readout |
| `GET /rollouts/{id}/event_log` | none | structured NEV and legacy strings |

Actions are MiniHack symbolic dicts: `move` (8-way), `wait`, `pickup`, `attack`.
