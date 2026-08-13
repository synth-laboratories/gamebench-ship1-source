# Super Mario Bros. research-port HTTP contract

The Rust service is local-only and has no parity surface based on HTTP UUIDs or
wall-clock time. Session IDs are transport handles and are ignored by scoring.

| Route | Body | Response |
| --- | --- | --- |
| `GET /health` | none | service lane and 32-level catalog count |
| `GET /info` | none | capabilities, observation shape, action contract |
| `POST /rollouts` or `/reset` | `{ "task": {"level_id":"1-1"}, "seed": 7 }` | rollout handle and readout |
| `POST /rollouts/{id}/step` | `{ "action": "right_jump_run" }` or input object | step, events, readout, progress, terminal |
| `POST /rollouts/{id}/checkpoint` | none | base64 JSON checkpoint and byte count |
| `POST /rollouts/{id}/restore` | `{ "blob": "..." }` | restore report and readout |
| `POST /rollouts/{id}/simulate` | `{ "blob":"...", "sequences":[["right"],["right_jump"]] }` | non-mutating branch results |
| `GET /rollouts/{id}/readout` | none | public symbolic state and route progress |
| `GET /rollouts/{id}/event_log` | none | structured semantic events and legacy names |
| `GET /rollouts/{id}/render.png` | none | original geometric RGB PNG |
| `GET /rollouts/{id}/render.rgb` | none | base64 RGB8 observation |
| `POST /run_scenario` | `{ "task": {"level_id":"1-1", "actions":[...]}}` | bulk replay result |

Allowed discrete actions are `neutral`, `left`, `right`, `down`, `jump`,
`run`, `left_jump`, `right_jump`, `left_run`, `right_run`,
`left_jump_run`, `right_jump_run`, `down_jump`, `down_left`, and `down_right`.
