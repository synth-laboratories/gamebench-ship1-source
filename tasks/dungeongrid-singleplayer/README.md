# DungeonGrid Singleplayer

One-controller DungeonGrid code-policy task. The policy exclusively controls a
single hero (`barbarian` or `wizard`, per scenario) through the active-agent
action API.

## Scoring

Episode score is an **unbounded composite**:

```
gold*2 + achievements*1.5 + armor*1 + spells*2 + engine_reward + step_bonus*0.05
  - invalid_actions*5
```

Terms:
- **gold** — `coin_cache` collected from chests
- **achievements** — unlocked achievement count
- **armor** — remaining HP + carried/equipped armor value
- **spells** — successful spell casts
- **engine_reward** — raw environment shaped reward
- **step_bonus** — unused action budget (efficiency)

## Train / heldout

- **Train (10 dungeons):** `defaults/policy_sweep/policy_dev_v1.json` — use these
  while developing candidates.
- **Heldout (10 unseen):** `defaults/policy_sweep/policy_heldout_v1.json` —
  hillclimb’s primary leaderboard score is the heldout mean composite.

```bash
PYTHONPATH=.:gold_python:scripts python3 scripts/run_hillclimb.py \
  --output /tmp/dungeongrid-singleplayer
```
