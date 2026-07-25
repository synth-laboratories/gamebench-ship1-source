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

The Lite scope excludes deposit respawn, free-text diplomacy, a leaderboard
harness, and all private-engine/runtime dependencies.

The normative board, action, observation, NEV, and checkpoint contract is in
[`shared/fog_duel_lite_v0.md`](shared/fog_duel_lite_v0.md).
