# GameBench Craftax HTTP Contract

The Python and Rust gold lanes expose the same core routes. The local default
ports are `8097` for Python and `8098` for Rust.

- `GET /health`
- `POST /run_scenario`
- `POST /rollouts`
- `POST /rollouts/{rollout_id}/step`
- `GET /rollouts/{rollout_id}/readout`
- `GET /rollouts/{rollout_id}/event_log`
- `POST /rollouts/{rollout_id}/checkpoint`
- `POST /rollouts/{rollout_id}/restore`
- `POST /rollouts/{rollout_id}/simulate`
- `GET /rollouts/{rollout_id}/render.svg`

Checkpoint blobs use `gamebench.checkpoint.v1` and are intentionally lane-local.
They restore the resolved task, world grid, inventory, entity state, RNG state,
reward counters, and NEV cursor/events.
