# Super Mario Bros. single-player research port

This task is a Rust-native, deterministic research environment for the 32
World 1-1 through World 8-4 evaluation identifiers used by the Odysseus-style
visual-control protocol. It is an original platformer with capability coverage
informed by that evaluation family; it is not an emulator and does not claim
pixel, map, timing, physics, enemy, route, or content parity with Nintendo.

## What is implemented

`gold_rust` contains the authoritative fixed-point engine and exposes:

- 32 independently authored course blueprints with unique geometry signatures,
  themes, route checkpoints, hazards, and capability tags;
- 60 Hz integer/fixed-point movement, acceleration, braking, jumping, landing,
  horizontal and vertical collision, gaps, lava/water behavior, and camera
  tracking;
- scheduled walkers, shells, flyers, fish, and spikes; stomps, damage,
  invincibility, power states, deaths, lives, and terminal reasons;
- question, breakable, solid, and used blocks; coins, mushrooms, flowers,
  stars, pipes/transitions, moving platforms, and route-aware progress;
- deterministic RGB8 observations built from geometric primitives and original
  colors, with no checked-in or generated proprietary visual assets;
- complete serializable snapshots, JSON checkpoint/restore, semantic events,
  replayable action tapes, bounded timers, score/reward semantics, and an
  explicit 15-action discrete space compatible with VLM rollouts.

Run the engine and all Rust tests with:

```sh
cargo test --manifest-path gold_rust/Cargo.toml
```

Run the HTTP adapter locally with:

```sh
cargo run --release --manifest-path gold_rust/Cargo.toml --bin super_mario_bros_service -- --port 8099
```

The repository-convention wrapper is also available at
`scripts/run_service.py` and accepts `--host` and `--port`.

The adapter implements `/health`, `/info`, `/rollouts`, `/reset`,
`/rollouts/{id}/step`, `/checkpoint`, `/restore`, `/simulate`, `/readout`,
`/event_log`, `/render.png`, and `/render.rgb`. It accepts either a discrete
action name such as `right_jump_run` or an input object. The in-process API is
`Env::reset`, `Env::step`/`Env::step_action`, `Env::snapshot`,
`Env::restore`, `Env::checkpoint_bytes`, `Env::from_checkpoint_bytes`,
`Env::drain_events`, and `Env::render_rgb`.

## Course authorship and scoring

Each level has an explicit authored blueprint in `gold_rust/src/lib.rs` and is
materialized into its own floor gaps, ledges, block bank, collectible bank,
enemy schedule, moving-platform plan, pipe destinations, hazard profile, and
route checkpoints. The `authoring_variant_*` capability tag and
`LevelSpec::fingerprint` are internal integrity checks for this research-safe
content, not hashes of ROM material.

Progress is reported in thousandths, along with the furthest tile, current
route checkpoint, route count, and progress axis. Reward is shaped by progress,
coins, power-ups, stomps, damage, death, and completion. Completion, death, and
timeout are distinct terminal reasons and steps after termination are no-ops.

## Provenance boundary

The canonical local ROM path for optional, uncommitted behavioral-oracle work
is `roms/Super Mario Bros. (Japan, USA).nes`. `roms/` is gitignored. The ROM
must never be read by the checked-in crate or adapter and must never be copied,
embedded, hashed as content, converted into fixtures, or used to generate
tracked frames, maps, sprites, audio, music, level data, or other extracted
assets. No oracle tooling is required to build, test, or run this task.

The distributable observation layer intentionally uses flat colors and simple
geometric figures. Any research report using this task must describe it as an
original capability-oriented platformer and must not make unsupported claims
of Nintendo-content parity.
