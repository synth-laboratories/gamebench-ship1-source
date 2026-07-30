# Settlers Rules Multiplayer

`settlers-multiplayer` is a four-player, alternating-turn, owned symbolic
emulator for the decision pressure studied in [Agents of Change / HexMachina
(arXiv:2506.04651)](https://arxiv.org/abs/2506.04651). It is intentionally a
rules-and-observation implementation: neither a pixel-perfect recreation nor
a wrapper around an upstream runtime.

The default game is a race to 10 victory points. A deterministic modular board
supports dice production, roads, settlements, cities, robber discards and
steals, structured trades, development cards, and longest-road/largest-army
awards. It uses a compact 24-vertex topology rather than an art or renderer
substrate. Public task naming stays brand-safe.

## Gold authorities

- `gold_python/engine.py`: Python rules authority and JSON checkpoint restore.
- `gold_rust/src/lib.rs`: independent Rust rules authority and JSON checkpoint
  restore.
- `fixtures/gold/`: deterministic state and NEV records generated only by the
  owned Python lane; parity covers the same five scenario commands in Rust.

Both lanes expose structured NEV kinds: `dice`, `produce`, `build`, `robber`,
`dev_card`, `trade_proposed`, `trade_accepted`, `trade_rejected`,
`trade_bank`, `vp`, `longest_road`, `largest_army`, `illegal_action`, and
`terminal`.

## Action API

The current player supplies exactly one structured action; turns then rotate
in normal player order. On a seven, only `move_robber` is legal until the
robber has moved. Useful commands include:

```json
{"kind":"build_road","edge":1}
{"kind":"build_settlement","vertex":2}
{"kind":"build_city","vertex":12}
{"kind":"trade_propose","to":"agent_2","give":"wood","want":"ore"}
{"kind":"trade_accept"}
{"kind":"play_dev","card":"knight","tile":3,"victim":"agent_1"}
```

The `free` road implementation detail is never public: free construction is
only invoked internally by a road-building development card.

## Deterministic scenarios and verification

The five pinned 4P scenarios cover a city VP, accepted structured trade,
robber recovery plus illegal-action reliability, the longest-road race, and
the three-knight largest-army race. They also restore a mid-episode checkpoint.

```bash
python3 tasks/settlers-multiplayer/scripts/generate_gold_fixtures.py
python3 tasks/settlers-multiplayer/scripts/verify_gold_fixtures.py
python3 tasks/settlers-multiplayer/scripts/verify_python_rust_parity.py
```

## Code-policy DEO

`defaults/policy_sweep/policy_dev_v1.json` is a fixed four-player,
alternating-turn suite. A candidate controls only `agent_0`; `agent_1` through
`agent_3` each run the owned, deterministic,
`policies/alphabeta_depth2.py` AlphaBeta-depth-2-spirit policy. This keeps the
paper baseline in the scoring seat while allowing one source-only code policy
to improve.

The importable baseline is
`containers/codepolicy/heuristic_policy.py`, which exports
`act(observation) -> action`. Harbor candidates use the identical public,
observation-only API at
`candidates/settlers/<candidate_id>/heuristic_policy.py`. The task-local
checked-in example is deliberately outside generated report directories:
`examples/code_policy_deo/candidates/settlers/vp_development_race_v1/`.
The DEO envelope also supplies `turn` and `rolled_die` before each action;
when `rolled_die == 7`, the policy must return `move_robber`. This mirrors the
public dice phase of the board game and makes invalid-action reliability a
policy property rather than a pre-roll API artifact.

For every seeded episode, the score is
`0.60 * win_outcome + 0.35 * (candidate_vp / 10) + 0.05 * action_reliability`.
`win_outcome` is one only when `agent_0` wins, and
`action_reliability = 1 - invalid_candidate_actions / candidate_decisions`.
This makes wins primary, preserves VP progress when a game hits its turn limit,
and rejects policies that gain progress via invalid action spam.

Run the local end-to-end example; it creates reports in a temporary directory,
asserts the checked-in candidate leads by at least `+0.01`, and leaves no
generated output in the checkout:

```bash
python3 tasks/settlers-multiplayer/scripts/run_code_policy_deo_example.py
```

The generic Harbor runner invokes the same contract with:

```bash
python3 tasks/settlers-multiplayer/scripts/run_hillclimb.py \
  --suite tasks/settlers-multiplayer/defaults/policy_sweep/policy_dev_v1.json \
  --baseline tasks/settlers-multiplayer/containers/codepolicy/heuristic_policy.py \
  --candidate-root tasks/settlers-multiplayer/examples/code_policy_deo/candidates \
  --output /tmp/gamebench-settlers-deo
```

`policies/alphabeta_depth2.py` remains the deterministic, action-pruned
AlphaBeta depth-2 spirit opponent. Its pruning is a CI cost descope, not a
change to the owned game rules.

```bash
python3 tasks/settlers-multiplayer/scripts/run_policy.py --episodes 3 --max-turns 80
```

For a headless transport, `scripts/run_service.py` accepts JSON-lines
`reset`, `step`, `checkpoint`, and `restore` commands on standard input.
