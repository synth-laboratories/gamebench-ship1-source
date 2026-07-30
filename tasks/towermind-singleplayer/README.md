# TowerMind semantic tower defense

`towermind-singleplayer` is an own, deterministic Python + Rust tower-defense
emulator inspired by [TowerMind (arXiv:2601.05899)](https://arxiv.org/abs/2601.05899).
The published Unity environment is a semantic reference only: this task does
not import Unity, ML-Agents, JAX, a ROM, or any upstream runtime. It preserves
the paper-shaped decisions instead—spatial building, pickup-only gold, distinct
Archer/Magician/Knight towers, hero and knight micro, fog-disabled friendlies,
leak loss, and reliable rejection of hallucinated actions.

## v0 contract

- L1 and L2 are deterministic playable discrete maps; L3–L5 are named,
  inspectable progression stubs. They document the intended five-level ladder
  without claiming unsupported content is implemented.
- Gold comes only from spawned coins collected by a hero or knight. Enemy kills
  intentionally grant zero gold.
- Archer is single-target, Magician deals local AoE, and Knight Tower summons a
  controllable knight. The hero and knights move one Manhattan cell or attack
  adjacent enemies.
- A friendly that is in a fog cell is hidden from the symbolic observation and
  cannot execute micro; a tower in fog is hidden and cannot fire.
- Every invalid action emits structured `illegal_action` NEV with
  `hallucination: true`, applies no requested state change, and consumes the
  discrete decision tick. Each enemy leak applies exactly `-1.0`; an episode
  ends at base HP zero or when all waves clear.
- Observations return both a structured object and canonical textual JSON.
  Checkpoints are portable `json-v1` snapshots and are exercised from Python to
  Rust by the local parity command.

Actions are JSON objects such as:

```json
{"kind":"build","tower":"archer","target":"gate_archer"}
{"kind":"collect","actor":"hero","target":[1,2]}
{"kind":"move","actor":"knight_0","target":[5,2]}
{"kind":"attack","actor":"hero","target":"enemy_0"}
{"kind":"wait"}
```

## Layout

- `gold_python/` and `gold_rust/` are independent authorities.
- `defaults/levels/` contains L1/L2 gameplay maps and L3–L5 progression stubs.
- `defaults/scenarios/` contains five deterministic action tapes: gold/build,
  fog + knight micro, illegal-action reliability, base destruction by leaks,
  and L3 stub discovery.
- `fixtures/gold/` pins scenario inputs, structured NEV, final state/observation,
  and checkpoint artifacts.
- `policies/heuristic_baseline.py` is a small deterministic placement/pickup
  baseline suitable for a local code-policy smoke run.
- `defaults/policy_sweep/policy_dev_v1.json` is the fixed L1/L2 code-policy
  DEO suite. Its score combines leak-derived reward, base-pressure survival,
  waves-cleared rate, and illegal-action reliability. The Harbor baseline is
  deliberately a legal pickup-only policy; the checked-in candidate demonstrates
  public-observation tower placement and hero/knight micro without a seed or
  fixture lookup.

## Local commands

```bash
cd tasks/towermind-singleplayer
python3 scripts/verify_python_rust_parity.py
python3 scripts/verify_gold_fixtures.py
python3 scripts/run_policy.py --level L1 --steps 40
python3 scripts/run_service.py --port 8094
```

## Code-policy DEO

The generic Harbor `code_policy_deo_hillclimb` bundle resolves this task through
`adapters/eval_registry.toml`: it uses
`defaults/policy_sweep/policy_dev_v1.json`, the importable baseline at
`containers/codepolicy/heuristic_policy.py`, and candidates under the
`towermind` namespace. A candidate exports `act(observation) -> action`, where
the observation is the public structured/textual TowerMind state.

Run the checked-in end-to-end example (it creates artifacts only in the supplied
directory, or in a new temporary directory when `--output` is omitted):

```bash
cd tasks/towermind-singleplayer
python3 scripts/run_code_policy_deo_example.py --output /tmp/towermind-deo
```

It evaluates the pickup-first baseline and
`examples/code_policy_deo/candidates/towermind/fog_aware_tower_micro_v1`, then
fails unless the best non-baseline policy improves the canonical leaderboard by
at least `0.01`. To run the same task-local runner with another candidate root:

```bash
python3 scripts/run_hillclimb.py \
  --suite defaults/policy_sweep/policy_dev_v1.json \
  --baseline containers/codepolicy/heuristic_policy.py \
  --candidate-root /path/to/candidates \
  --output /tmp/towermind-hillclimb
```

After an intentional semantics change, regenerate the checked-in fixtures with
`python3 scripts/generate_gold_fixtures.py` and rerun both verifiers. The task
is headless and CPU-only.
