# Craftax canonical policy — do not lose these settings

**Date:** 2026-08-13
**Why this file exists:** the settings below produced every good Craftax result
we have. They live in scratch files and shell history, and two different ReAct
implementations now exist that do **not** agree. If collection, evaluation and
training do not all run this exact policy, the numbers are not comparable and an
uplift measurement is meaningless.

## The canonical policy

This is the config behind the 2000-step run that scored **18.80 with 19
achievements**, and the `both` arm that averaged **12.90**.

```json
{
  "use_lm": true,
  "provider": "openrouter",
  "model": "openai/gpt-5.6-luna",
  "reasoning_effort": "medium",
  "max_tokens": 1024,
  "max_llm_turns": 400,
  "min_actions_per_call": 4,
  "max_actions_per_call": 8,

  "react_mode": "conversation",
  "observation_mode": "both",

  "context_token_budget": 16000,
  "compact_at": 0.7,
  "keep_recent_messages": 8,
  "keep_recent_frames": 2,

  "capture": "required"
}
```

Environment, equally load-bearing:

```json
{"seed": N, "config": {"max_steps": 2000, "world": {"use_default": "craftax_default"}}}
```

`craftax_default` is 48×48, 9 levels, vanilla densities. Assert
`summary.world.is_reference_world == true` on every result. Anything else is not
a Craftax number — see `WORLD_DEFAULTS_FINDING_2026-08-13.md`.

### Why each knob matters

| knob | why |
|---|---|
| `react_mode: conversation` | Append-only transcript: `system → user → assistant(tool_calls) → tool(result) → …`. The old `stateless` mode rebuilt a fresh prompt each turn and carried only a 16-action tail window, dropping 152 of 168 actions with no summary. |
| `observation_mode: both` | Text alone and image alone both score ~7.1–7.4. Together: **12.90**, and it is the only configuration that ever reached the dungeon (`enter_dungeon`, `open_chest`, `find_bow`, `collect_sapphire`, `defeat_orc_mage`). |
| `compact_at` / `context_token_budget` | Compaction fires on **real `usage.prompt_tokens`**, not an estimate or a turn count. Summary is model-written; system message and opening task always survive. |
| `keep_recent_frames: 2` | Frames re-send every turn until compaction. Unbounded, one seed hit **1,066,008 tokens** and blew the client timeout — and the resulting failures killed deep survivors preferentially, biasing the sample. |
| `max_llm_turns: 400` | The clamp was 128, which at 7.56 steps/turn ceilinged any rollout near 968 steps. Raised to 1024. |

## Two ReAct implementations disagree — the open risk

There are now **two** harnesses, and they are not the same policy:

| | `craftax_gold.rs` (ours) | `platform/react.py` (Containers) |
|---|---|---|
| transcript | append-only | append-only |
| **images** | **yes** (`observation_mode: both`) | **NO — text only** |
| compaction trigger | token budget × `compact_at` | `compact_every` turn count (default 16) |
| compaction retains | `keep_recent_messages: 8`, `keep_recent_frames: 2` | `compact_keep_turns = 2` |
| default model | — (explicit) | `meta/muse-spark-1.1` |
| max_tokens | 1024 (cap 4096) | 768 (cap 2048) |

**Consequence:** SFT checkpoint evaluation runs through the Containers platform,
so a checkpoint would be evaluated **text-only with different compaction** while
the teacher data was collected **with images**. That is the same class of defect
as the three-divergent-prompts bug (`image_input.md`): train on one
representation, measure on another, read the mismatch as "no uplift".

**This must be resolved before any uplift claim.** Either teach
`platform/react.py` the image path and token-based compaction, or route
checkpoint evaluation through the Rust loop. Do not compare across them.

## Where the code is

| what | where |
|---|---|
| ReAct loop, capture, image observations | `gamebench-craftax-sft` @ `josh/craftax-trace-sft` → `tasks/craftax-singleplayer/gold_rust/src/bin/craftax_gold.rs` |
| Observation renderer (FOV + HUD) | same worktree → `gold_rust/src/sprites.rs::render_observation_frame` |
| Eval driver (refuses biased samples) | same worktree → `tasks/craftax-singleplayer/scripts/run_craftax_eval.py` |
| Curation + dataset | `optimizers-beta-craftax-sft` @ `josh/craftax-trace-sft` → `scripts/lib/craftax_curation.py` |
| Canonical prompt builder | same → `scripts/lib/craftax_prompt.py` |
| Tinker backend + pause/resume | same → `crates/synth_sft/src/tinker.rs` |
| Containers platform + Craftax runtime | `containers` → `src/synth_containers/platform/{app,react}.py`, `runtimes/craftax.py` |
| Local Trace V5 capture | `containers` → `synth-trace serve` |

Both `josh/craftax-trace-sft` branches are pushed. Work in the **worktrees**, not
the shared checkouts — three separate agents committed over us there today.

## How to run it

### 1. Trace collector

```bash
python -m synth_containers.tracing.cli serve \
  --output .out/traces --host 127.0.0.1 --port 8400 \
  --capture-disk-budget-bytes 2000000000 \
  --capture-disk-reserve-bytes 200000000 \
  --budget-policy evict_oldest_sealed
# health: curl :8400/healthz
```

### 2. Craftax gold service

```bash
cd gamebench-craftax-sft/tasks/craftax-singleplayer
cargo build --release --manifest-path gold_rust/Cargo.toml --bin craftax_gold
OPENROUTER_API_KEY=... SYNTH_TRACE_CONTROL_URL=http://127.0.0.1:8400 \
  ./gold_rust/target/release/craftax_gold --host 127.0.0.1 --port 8600
```

### 3. A rollout on the canonical policy

`POST http://127.0.0.1:8600/rollout` with the JSON at the top of this file.
Check the response: `summary.world.is_reference_world`,
`summary.trace.trace_v5_digest`, `summary.context.mode == "conversation"`.
Inspect what the agent sees: `GET /rollouts/{id}/observation.png`.

### 4. A comparison

```bash
python3 scripts/run_craftax_eval.py --base-url http://127.0.0.1:8600 \
  --seeds 30 --max-steps 2000 \
  --arm both:'{"observation_mode":"both"}' \
  --arm text:'{"observation_mode":"text"}'
```

It exits non-zero rather than report a biased sample, and prints survival count
and achievement union ahead of the mean. **Three runs of an identical config gave
means of 9.61 / 9.51 / 7.09** — under ~5 points is unresolved at n=10.

### 5. Hosted SFT (phases A–E proven)

```bash
cd optimizers-beta-craftax-sft
cargo build -p optimizers-beta
TINKER_API_KEY=... OPTIMIZERS_BETA_SERVICE_TOKEN=local-dev-token \
  SYNTH_SFT_PYTHON=/path/to/venv/bin/python \
  ./target/debug/optimizers-beta serve --bind 127.0.0.1:8700 --workspace-root .out/ws

curl -X POST :8700/v1/runs -H 'Authorization: Bearer local-dev-token' \
  -H 'content-type: application/json' \
  -d '{"algorithm":"sft","config_toml":"<SftConfig TOML>"}'
```

Footguns, all of which cost time today:

- the route is `/v1/runs`, not `/runs`
- the field is `algorithm`, **not** `algorithm_id` — a wrong name silently
  defaults to GEPA and fails with a confusing TOML error
- `base_model` must be in `sft_tinker_base_models.toml` or it is refused
- `SYNTH_SFT_PYTHON` needs `tinker` **and** `jinja2` (the latter is required by
  `apply_chat_template` and is not a declared dependency)

## Status

**Proven on real data:** conversational ReAct with images, Trace V5 capture
(completed and interrupted), curation → dataset with provenance, and hosted
Tinker LoRA training to completion on Nemotron 3.5 Lightning.

**Blocked:** checkpoint evaluation (phase F) and the paired heldout comparison
(phase G) — the Containers platform harness is text-only, per the divergence
table above.
