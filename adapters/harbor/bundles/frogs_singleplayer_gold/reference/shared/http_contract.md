# FrogsGame HTTP Contract

The Python and Rust gold lanes expose the same routes as the Sokoban/Crafter dual-lane tasks:

- `GET /health`
- `POST /run_scenario`
- `POST /rollouts`
- `POST /rollouts/{id}/step`
- `POST /rollouts/{id}/checkpoint`
- `POST /rollouts/{id}/restore`
- `POST /rollouts/{id}/simulate`
- `GET /rollouts/{id}/readout`
- `GET /rollouts/{id}/event_log`

Actions are JSON objects:

- `{"kind": "place_frog", "row": 0, "col": 1}`
- `{"kind": "remove_frog", "row": 0, "col": 1}`
- `{"kind": "submit"}`
- `{"kind": "reset"}`

Rewards are programmatic and binary: `1.0` only when `submit` receives a complete valid placement, otherwise `0.0`.
