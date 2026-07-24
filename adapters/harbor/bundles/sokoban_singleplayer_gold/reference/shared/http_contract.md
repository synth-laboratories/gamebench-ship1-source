# Sokoban Gold HTTP Contract

Both gold lanes expose the same local development surface.

| Route | Body | Response |
| --- | --- | --- |
| `GET /health` | none | lane id, version, env family |
| `POST /rollouts` | task JSON and optional `seed` | `rollout_id`, readout, NEV cursor |
| `POST /rollouts/{id}/step` | `{ "action": "up" }` | readout, reward, done flags, NEV cursor |
| `POST /rollouts/{id}/checkpoint` | none | base64 blob, byte count, NEV cursor |
| `POST /rollouts/{id}/restore` | `{ "blob": "..." }` | restore report and readout |
| `POST /rollouts/{id}/simulate` | `{ "blob": "...", "sequences": [["right"], ["up", "right"]] }` | batch branch results without mutating the live rollout |
| `GET /rollouts/{id}/readout` | none | symbolic readout |
| `GET /rollouts/{id}/event_log` | none | structured NEV and legacy strings |
| `GET /rollouts/{id}/render.svg` | none | SVG board image, Python lane |
| `GET /rollouts/{id}/render.png` | none | PNG board image, Python lane |

Actions are `up`, `down`, `left`, and `right`.
