# GameBench — Super Mario Bros. single-player research environment

Implement or stage a Rust-native, research-safe platformer under
`/workspace/candidate/gold_rust` and expose the documented HTTP service. The
reference source is supplied only as the local Harbor gold solution; the
contract and provenance rules are the normative surface for candidate work.

The environment must cover all 32 stable evaluation identifiers `1-1` through
`8-4`, with independent authored course definitions and meaningful capability
coverage. It must remain deterministic for a fixed `(level_id, seed, action
tape)` and must not require a ROM, extracted maps, copyrighted sprites, audio,
captured frames, or network access.

The verifier exercises fixed-point movement, collision and pits, scheduled
entities, stomps and damage, blocks and power states, moving platforms,
water/castle-style hazards, pipes and route progress, RGB observations,
snapshots/restores, semantic events, timers, terminal reasons, and the full
HTTP rollout/checkpoint/simulate surface.

Use only the original geometric RGB observation. Do not make Nintendo parity
claims: the task is a capability-oriented research port, not an emulator.
