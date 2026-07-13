# Overcooked v2 multiplayer (GameBench)

Symbolic **multi-agent simultaneous MARL** kitchen gold with **full JaxMARL OvercookedV2-scope** features.

## Layout

- `gold_python/` — joint-step engine, NEV, checkpoints, observations, pixel render, FastAPI service
- `shared/` — ASCII layout parser, ingredient model, task resolver
- `fixtures/gold/` — **29** scripted scenarios + NEV eventlogs
- `defaults/layouts/` — **30** ASCII layouts (21 JaxMARL catalog + 9 task-specific); see `index.json`
- `scripts/` — verify, spectrum eval, hillclimb, HTTP service
- `policies/` — greedy cooperative heuristic baseline + `kitchen_nav.py` shared MARL logic
- `containers/codepolicy/` — in-process `choose_joint_actions` rollout

## Engine features (full scope)

| Feature | Status |
|---------|--------|
| Multi-ingredient recipes (`ing_0`, `ing_1`, …) | Yes |
| Ingredient piles `O`, `T`, digits `0–9` | Yes |
| Grounded communication buttons (`L` + interact) | Yes |
| Passive recipe indicators (`R`) | Yes |
| Partial observability (`view_radius`) | Yes |
| Stochastic spawn | Yes |
| 3+ agents | Yes |
| Counters, plated soup, recipe pool / ZSC resample | Yes |
| Observation profiles | `symbolic_compact`, `spatial_tensor`, `featurized`, `pixel_rgb` (aliases `jaxmarl_default`, `jaxmarl_featurized`) |
| `URGENCY_CUTOFF` tensor layer | Yes (`urgency_cutoff` task override; default 40) |
| `random_reset` (agents, pots, counters) | Yes (`defaults/rules/random_reset.json`) |
| OvercookedAI exact featurized vector | Yes (48 self + 44 per other agent + dist + position; no JAX) |
| Shaped rewards (optional rules flag) | Yes |
| Manual cook start (`start_cooking_interaction`) | Yes |
| Ingredient permutations in obs | Yes |

## Rules profiles (`defaults/rules/`)

| Profile | Features |
|---------|----------|
| `cooperative_full_obs` | Full map + visible recipe |
| `partial_obs_v1` | Masked ASCII per agent |
| `hidden_recipe_indicator` | Recipe hidden until `R` visible |
| `stochastic_spawn` | Random walkable spawn |
| `zsc_coop` | Partial obs + hidden recipe + stochastic + recipe pool |
| `grounded_communication` | Hidden recipe + `L` button activation |
| `featurized_obs` | `featurized` observation profile (OvercookedAI vector layout) |
| `pixel_obs` | `pixel_rgb` observation profile |
| `random_reset` | Random agent positions/inventories, pot state, counter items on reset |

## Layout library

Regenerate catalog layouts from `shared/layout_catalog.py`:

```bash
cd tasks/overcooked-v2-multiplayer
PYTHONPATH=.:gold_python:shared python3 scripts/generate_layout_library.py
```

Catalog layouts are written to `defaults/layouts/` as ASCII JSON. Custom task layouts (`demo_tiny`, `three_chefs`, etc.) coexist with the 21 ported JaxMARL maps.

## Quick verify

```bash
cd tasks/overcooked-v2-multiplayer
python3 scripts/build_scenarios.py
python3 scripts/generate_eventlogs.py
python3 scripts/verify_gold_nev.py
python3 scripts/verify_restore_equivalence.py
PYTHONPATH=.:gold_python:shared python3 scripts/spectrum_eval.py --lane local --reference-local
```

## HTTP observation profiles

Rollout request accepts `observation_profile` or task `readouts.profile`:

- `symbolic_compact` — masked ASCII + JSON (default)
- `spatial_tensor` — layered map tensor including urgency layer when `steps_remaining < urgency_cutoff` (`jaxmarl_default` alias)
- `featurized` — OvercookedAI fixed-length `observations[agent].features` (`jaxmarl_featurized` alias)
- `pixel_rgb` — tile RGB `observations[agent].pixel_rgb`
