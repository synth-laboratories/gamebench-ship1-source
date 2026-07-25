# Fog Duel Lite multiplayer

`fogwar-duel-multiplayer` is an own-language GameBench emulator inspired
by [Age of LLM (arXiv:2606.24391)](https://arxiv.org/abs/2606.24391). The paper's
private engine is a semantic reference only: this task will own its Python and
Rust loops, checkpoints, and structured NEV. It deliberately targets symbolic
decision pressure, not private-engine, renderer, or pixel parity.

## Rules digest

Two agents contest a 13×7 map. A mountain barrier in column 6 has one or two
passages in each pinned layout; `agent_0` starts at `(1,3)` and `agent_1` at
`(11,3)`. Each full round contains one ordered half-turn for each player. Round
order is always `agent_0` then `agent_1`. This is not a joint-step task.

An actor submits at most three ordered structured actions: `produce`, `move`,
`attack`, `build`, `launch`, or `wait`. Units are Tank, Fighter, SAM, and Drone.
The combat triangle and Tank-only building damage preserve the paper's core
decision pressure. Bases, credit mines, uranium mines, and silos are buildings.
Credits buy units/buildings; uranium comes only from uranium mines and is secret
from the opponent. Deposits are finite in Lite, but do not respawn mid-game.

Fog hides enemy units outside friendly detection. Seen enemy buildings remain as
last-seen records until the engine knows they were destroyed; the enemy base must
have been scouted before a launch is legal. At the end of a full round, one valid
launch wins by nuclear victory; two valid launches cause mutual destruction.
Tank damage reducing a base to zero HP is an immediate military win.

Structured diplomacy is outside the three-action budget: `ceasefire`, `peace`,
and `ultimatum` may be proposed or answered through typed fields. Free-text
messages are intentionally excluded. Every malformed or illegal action is
discarded individually, spends only its own action slot, and emits
`illegal_action`; this is the reliability signal rather than a silent fallback.

## Gold layout and verification

Independent authorities live in `gold_python/` and `gold_rust/`; neither wraps
or imports the private engine. The three deterministic scenario files are
`fogwar_military_win_v0` (Tank victory), `fogwar_nuclear_win_v0` (one queued
launch after both fixed-order half-turns), and `fogwar_illegal_reliability_v0`
(a rejected stale unit reference). Fixtures include the canonical state, NEV,
and action-boundary checkpoint restoration records.

Run the task-local checks from this directory:

```bash
python3 scripts/verify_gold_fixtures.py
python3 scripts/verify_python_rust_parity.py
```

The parity gate compares complete structured NEV envelopes/payloads and the
authoritative state for every scenario, then restores the nonterminal illegal
reliability checkpoint in Rust and replays the remaining half-turn.

The JSON-lines Python service accepts `reset`, `step`, `observe`, `state`,
`checkpoint`, and `restore` requests on stdin and emits one JSON response per
line:

```bash
python3 scripts/run_service.py
python3 scripts/run_policy.py --scenario fogwar_nuclear_win_v0
```

## Code-policy DEO example

The fixed `policy_dev_v1` suite runs `agent_0` against the fixed
`passive_wait_v1` `agent_1` request stream while preserving engine-owned
alternation (`agent_0`, then `agent_1`) and private observations. It has one
scenario each for a visible Tank military win, a valid launch that resolves
only after `agent_1` completes the round, and an empty opening that measures
illegal-action reliability. Its score is the mean of
`0.80 * (agent_0 terminal reward / 3.0) + 0.20 * legal-action reliability`;
reliability is `1 - illegal policy actions / submitted policy actions`.

The Harbor-compatible baseline is
`containers/codepolicy/heuristic_policy.py`. The checked-in stronger, pure
observation-only candidate is
`examples/code_policy_deo/candidates/fogwar_duel/tactical_observation_v1/heuristic_policy.py`.
It uses neither scenario identity nor hidden state: it launches only when the
observation proves the prerequisites, attacks only a currently visible base in
Tank range, and otherwise waits.

Run the full generic Harbor DEO bundle through the task-local wrapper from the
repository root. It stages the checked-in candidate under the supplied external
output root, invokes the generic bundle's `run` and `score` commands, and
asserts a candidate best-score delta of at least `0.01`:

```bash
python3 tasks/fogwar-duel-multiplayer/scripts/run_deo_example.py \
  --output-root /tmp/fogwar-deo-example
```

The generic run phase writes the canonical `leaderboard.json` under
`/tmp/fogwar-deo-example/artifacts/gamebench_hillclimb/`; the second writes the
Harbor verifier result under the same supplied output root. The task-local
runner can also be called directly with the same external output requirement:

```bash
python3 tasks/fogwar-duel-multiplayer/scripts/run_hillclimb.py \
  --suite tasks/fogwar-duel-multiplayer/defaults/policy_sweep/policy_dev_v1.json \
  --baseline tasks/fogwar-duel-multiplayer/containers/codepolicy/heuristic_policy.py \
  --candidate-root tasks/fogwar-duel-multiplayer/examples/code_policy_deo/candidates \
  --output /tmp/fogwar-deo-hillclimb
```

The Lite scope excludes deposit respawn, free-text diplomacy, and all
private-engine/runtime dependencies.

The normative board, action, observation, NEV, and checkpoint contract is in
[`shared/fog_duel_lite_v0.md`](shared/fog_duel_lite_v0.md).
