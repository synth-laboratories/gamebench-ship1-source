# Overcooked V2 pure-Rust authority

`overcooked-v2-gold` is a standalone Rust implementation of the task's
authoritative symbolic multiplayer mechanics. It has no Python, JAX, or service
dependency. `OvercookedV2Env::from_task_value` consumes the task's existing
layout/rules JSON shape; `step` consumes a typed simultaneous `JointAction`.

The checkpoint schema is `gamebench.overcooked_v2.checkpoint.v2`. Canonical
compact JSON includes the resolved task, parsed layout, RNG state, agents,
counters, pot/cooking state, active recipe, button timers, rewards, terminal
state, runtime metrics, and full event trace. Restoring from that JSON is
self-contained and byte-stable when no continuation is applied.

Runnable surfaces:

- `cargo run --bin service -- 127.0.0.1:8081` starts the stdlib HTTP service.
- `cargo run --example mapo_checkpoint_replay` executes every manifest row and
  emits deterministic checkpoint/continuation receipts on stdout.

The service exposes `/health`, `/info`, `/run_scenario`, `/rollouts`, and
rollout-scoped `step`, `checkpoint`, `restore`, `simulate`, `readout`, and
`event_log` routes. Rust checkpoint `blob` values are UTF-8 JSON, also returned
as a parsed `checkpoint` object.

Only `symbolic_compact` observations are in the initial Rust authority. The
Python lane remains authoritative for `spatial_tensor`, `featurized`,
`pixel_rgb`, `jaxmarl_default`, and `jaxmarl_featurized`; requesting one of
those profiles in Rust fails at task resolution. Rule profiles are recursively
composed in Rust so `grounded_communication -> hidden_recipe_indicator` works as
declared, while explicit task overrides remain highest precedence.

Other explicit parity boundaries: stochastic spawn, random reset, and recipe
resampling use a checkpointed Rust integer PRNG rather than Python's Mersenne
Twister, so seeded random trajectories are deterministic within the Rust lane
but not bit-identical across lanes. Rust also enforces map bounds and the
declared 2–4-agent contract. Rust v2 and Python v1 checkpoints are each
self-contained but are not cross-import formats.

The MAPO example's executor profiles are typed reference behaviors for
validating environment, checkpoint, split, and scoring substrate. They are not
an interpreter for arbitrary natural-language candidate prompts.
