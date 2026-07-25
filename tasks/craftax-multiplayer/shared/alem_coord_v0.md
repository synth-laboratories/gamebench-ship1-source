# `alem_coord_v0` profile contract

`alem_coord_v0` is an opt-in ALEM Lite extension of `craftax-multiplayer`, inspired by [ALEM (arXiv:2606.08340)](https://arxiv.org/abs/2606.08340). It is an own Python-and-Rust coordination layer over the local Coop emulators. It neither imports nor wraps `alem-env`, JAX, or its PRNG.

The default Craftax-Coop profile is unchanged. Enable the profile at reset or rollout creation with:

```json
{
  "rules_profile": "alem_coord_v0",
  "coordination": {"scenario": "sync_2", "alpha": 0.3}
}
```

`scenario` must be one of `sync_2`, `sync_all`, or `handover`; `alpha` is exactly one of `0.3`, `0.6`, or `0.9`. The v0 maps are fixed, deterministic layouts around level-0 target `[0, 4, 4]`, rather than a procedural coordination graph.

## Sites

| Pinned map | Participants | Completion rule | Role gate |
|---|---|---|---|
| `sync_2` | `agent_0`, `agent_1` | Both act (`do` or `attack`) on the same site target in one joint step. | Warrior |
| `sync_all` | all three agents | All three act on the same site target in one joint step. | Warrior |
| `handover` | `agent_2` → `agent_1` | Miner deposits iron at the site; Forager completes it within two subsequent decision windows. | Miner to open; Forager to complete |

Specialists always pass their gate. A non-specialist uses the deterministic `mix64(seed ^ timestep ^ (site_index << 16) ^ player_index) % 10000` roll and passes when it is less than `10000 - alpha_milli * 10`. The emitted `soft_role_roll` records `alpha_milli`, the roll, required role, and outcome.

## Structured messages

The sole message form is a non-free-text action object:

```json
{"kind":"say","to":"agent_1","code":"NEED_IRON","site_id":"handover_site"}
```

- `to` is `agent_0`, `agent_1`, `agent_2`, or `all`, but cannot be the sender.
- `code` is one of `NEED_IRON`, `MEET_AT`, `ATTACK_MOB`, `BUILD_HERE`.
- `site_id` is optional.
- No fields other than `kind`, `to`, `code`, and `site_id` are permitted. `say` consumes that agent's action for the simultaneous step.

## NEV and metrics

The profile emits `coord_site_spawned`, `coord_sync_success`, `coord_sync_fail`, `handover_opened`, `handover_completed`, `handover_expired`, `soft_role_roll`, and `message`, in addition to the existing Coop event stream. Each site event includes `site_id` and `site_kind`; sync failures include `reason`.

Profile state is checkpointed in optional `alem_coord` state. Episode metrics are:

```json
{
  "base_reward": 0.0,
  "coord_reward": 2.0,
  "coord_success_rate": {
    "sync_2": {"success": 1, "resolved": 1, "rate": 1.0}
  }
}
```

`base_reward` is the cumulative legacy Coop reward, while `coord_reward` is the cumulative site-only reward (2 for `sync_2` or `handover`, 3 for `sync_all`). The returned shared reward is their per-step sum. Coordination achievements (`coord_sync_2`, `coord_sync_all`, `coord_handover`, `coord_message`, `coord_soft_role`, `coord_handover_offer`) remain zero-valued in base reward so the split is not double-counted.

## Fixture and parity surface

The pinned fixtures are `alem_sync_2_success`, `alem_sync_all_success`, `alem_handover_success`, `alem_handover_expired`, and `alem_soft_role_denial`. `scripts/verify_python_rust_parity.py` runs all five through independent Python and Rust profile loops, including checkpoint restoration; `scripts/verify_gold_fixtures.py` validates the checked-in event/state artifacts.
