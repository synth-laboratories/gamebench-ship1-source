# Overcooked V2 Multiplayer Cybernetic Example

Local infra: `exotic_cybernetics/`, `containers/exotic_cybernetics/`, `scripts/run_exotic_cybernetics*.py`

SMR lane (planned): `evals/reportbench/lanes/overcooked_v2_gamebench_cybernetic_policy_uplift_1cand/`

## Pattern

Use the model as a kitchen macro and coordination classifier.
The model should not emit raw actions. Code owns rollout execution under a 20k prompt-token budget per episode.

## Quick smoke (mock steering)

```bash
cd tasks/overcooked-v2-multiplayer
python3 scripts/run_exotic_cybernetics.py --mock
```

## Reference policies

- `pure_code_bridge` — baseline symbolic policy, 0 LLM tokens
- `sparse_governor` — sparse steering patches via proxied `SteerSession`
