# Crafter Gold HTTP Contract

Status: v0 implementation contract.

The Python and Rust lanes expose the same logical session surface. Checkpoint
bytes are lane-local, but resolved task JSON, NEV legacy strings, symbolic
readouts, and terminal achievement summaries are comparable across lanes. Both
lanes expose the core reset/step/state/events/checkpoint/restore/scenario,
checkpoint simulation, and SVG render surface.

## Session identity

- `rollout_id` is the live HTTP session handle. Each `POST /rollouts` (or batch
  item) allocates a new opaque id (UUID). Many concurrent rollouts may share the
  same `seed`; clients must route steps/state/checkpoints through the returned
  `rollout_id`.
- `episode_id` lives in rollout `private` state. It is deterministic from
  `task_id`, `seed`, and `config_hash` and is used for replay proofs and
  cross-lane comparability. It is not the session map key.

## Routes

- `GET /health` returns `{ "ok": true, "env_family": "crafter-singleplayer", "pool": ... }`.
- `GET /info` returns capabilities and pool stats.
- `GET /pool` and `POST /pool/evict_idle` expose live-session state; the Python
  lane enforces configured bounds and idle eviction.
- `POST /run_scenario` and `POST /rollout` accept `{ "task": ... }` and return
  scripted scenario events, NEV, state, and readout.
- `POST /reset` and `POST /rollouts` accept `{ "task": ..., "seed": ... }` and
  create a live rollout session.
- `POST /rollouts/batch` accepts `{ "items": [{ "task": ..., "seed": ... }] }`
  or `{ "tasks": [...], "seeds": [...] }`, creates multiple live rollouts, and
  returns per-rollout payloads plus pool stats.
- `POST /step` accepts `{ "rollout_id": "...", "action": "move_right" }`.
- `POST /rollouts/{rollout_id}/step` accepts `{ "action": "move_right" }`.
- `GET /state/{rollout_id}` and `GET /rollouts/{rollout_id}/state` return the
  latest public/private state, symbolic readout, NEV tail, and NEV cursor.
- `GET /rollouts/{rollout_id}/readout` returns only the symbolic readout.
- `GET /rollouts/{rollout_id}/events` returns full NEV records plus legacy strings.
- `DELETE /rollouts/{rollout_id}` releases a live session.
- `POST /checkpoint/{rollout_id}` and `POST /rollouts/{rollout_id}/checkpoint`
  export a lane-local checkpoint blob inline for compatibility.
- `POST /rollouts/{rollout_id}/checkpoints` stores a checkpoint and returns a
  checkpoint id plus size/cursor metadata.
- `GET /rollouts/{rollout_id}/checkpoints` lists stored checkpoint metadata for
  that rollout: checkpoint id, save order, blob size, step index, NEV cursor,
  config hash, source (`manual` or `cadence`), auto flag, and export URL.
  Rollouts with `checkpoint_every_n_steps > 0` automatically store a cadence
  checkpoint after steps divisible by that interval.
- `GET /checkpoints/{checkpoint_id}/export` exports a stored checkpoint blob.
- `POST /checkpoints/import` and `POST /restore` restore a checkpoint into a new
  rollout.
- `POST /rollouts/{rollout_id}/restore` restores a checkpoint into an existing
  rollout. The service rejects the request with `409 Conflict` when the
  checkpoint `config_hash` does not match the target rollout `config_hash`.
- `POST /rollouts/{rollout_id}/simulate` evaluates action sequences from a
  checkpoint without mutating the live rollout. The checkpoint must match the
  target rollout `config_hash`.
- `GET /rollouts/{rollout_id}/render.svg` returns an SVG render of the current
  local symbolic view.
- `GET /rollouts/{rollout_id}/render.png` returns a current PNG frame. When
  `shared/assets/crafter/*.png` sprites are present (or
  `GAMEBENCH_CRAFTER_ASSETS_DIR` points at them), PNG/GIF frames use the
  original Crafter 16×16 pixel art; otherwise lanes fall back to symbolic RGB
  tiles.
- `GET /rollouts/{rollout_id}/frames/manifest` returns captured PNG frame
  metadata for visual/streaming rollouts.
- `GET /rollouts/{rollout_id}/frames/{step}.png` returns a captured PNG frame
  for a rollout step, or the current frame when requested on the current step.
- `GET /rollouts/{rollout_id}/replay.gif?through_step=N` returns a compact GIF
  assembled from captured rollout frames. GIF assembly uses ffmpeg
  palettegen/paletteuse. Rust automatic frame capture during reset/step requires
  replay mode (`GAMEBENCH_CRAFTER_REPLAY_ENABLED=1` or `--replay`) plus task gates:
  `readouts.visual`, `stream.enabled`, or `stream.persist_frames`. On-demand
  GIF/PNG fetch captures the current frame even when those gates are off.

Every reset writes `task_resolved` as the first NEV event with the fully expanded
world, rules, readout, stream, and reward config plus `config_hash`.

## Rollout limits and progress

`GET /state/{rollout_id}` and `GET /rollouts/{rollout_id}/state` return env
state plus optional rollout budgets and live counters when an agent-hosted
client wires them through.

- `limits` — configured caps (`max_llm_calls`, `max_steps`, `max_tokens`,
  `max_wall_clock_seconds`, …) set at `POST /rollouts` creation
- `progress` — live counters:
  - `env_steps` — env step count from the gold engine
  - `llm_calls_completed`, `llm_call_in_flight`
  - `prompt_tokens`, `completion_tokens`, `total_tokens`
  - `wall_clock_seconds`

`POST /rollouts/{rollout_id}/progress` merges agent-side counters during a
live rollout. The GRPO trainer pushes after each LLM call and env step, and
polls `GET /rollouts/{rollout_id}/state` ~750ms while rollouts are active.
Watch dashboards consume `RolloutProgress` o11y events sourced from those polls.

Containers that do not run an LLM agent omit `limits`/`progress` or leave them
empty. Monitors should treat absence as env-only and fall back to trainer o11y.
