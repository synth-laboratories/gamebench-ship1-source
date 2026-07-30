# Rogue Singleplayer Cybernetic Example

Local infra: `exotic_cybernetics/`, `containers/exotic_cybernetics/`, `scripts/run_exotic_cybernetics*.py`

SMR lane (planned): `evals/reportbench/lanes/rogue_gamebench_cybernetic_policy_uplift_1cand/`

## Pattern

Use the model as a exploration and combat-phase governor.
The model should not emit raw actions. Code owns rollout execution under a 20k prompt-token budget per episode.

## Quick smoke (mock steering)

```bash
cd tasks/rogue-singleplayer
python3 scripts/run_exotic_cybernetics.py --mock
```

## Reference policies

- `pure_code_bridge` — baseline symbolic policy, 0 LLM tokens
- `sparse_governor` — sparse steering patches via proxied `SteerSession`
