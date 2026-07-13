# GameBench MARL prompt optimization Rust adapter

This standalone binary exposes public `synth_gepa`'s
`gepa_optimizer_contract.v1` over the committed Craftax Multiplayer,
DungeonGrid, and Overcooked V2 Rust authorities. It has no model or Python
dependency: candidate strings are interpreted by a strict bounded semantic
layer and executed as real Rust-engine continuations from deterministic MAPO
checkpoints.

## Run

```bash
cargo run -- --environment craftax --port 8788
cargo run -- --environment dungeongrid --port 8789
cargo run -- --environment overcooked --port 8790
```

The required routes are `GET /health`, `GET /metadata`, `GET /task_info`,
`GET /program`, `GET /taskset`, `POST /taskset/tasks`, and `POST /rollout`.
`GET /info` aliases `/metadata` for generic container tooling.

The catalogs are generated only from the committed v1 MAPO datasets. Internal
dataset partitions remain disjoint:

| Environment | Train | Selection | Heldout | Total |
| --- | ---: | ---: | ---: | ---: |
| Craftax Multiplayer | 256 | 96 | 160 | 512 |
| DungeonGrid | 168 | 48 | 72 | 288 |
| Overcooked V2 | 48 | 24 | 24 | 96 |

Craftax rows are `64/24/40` disjoint seeds crossed with four frozen probes.
DungeonGrid rows are `7/2/3` disjoint base scenarios crossed with four map
transforms, two role orders, and three frozen probes.
Overcooked uses the committed three templates per internal split and expands
each template with `16/8/8` deterministic seed replicas. This yields exactly
`48/24/24` rows while preserving split-disjoint layout families and seeds.

Public GEPA has only train and heldout taskset surfaces. The adapter therefore
maps both internal train and internal selection IDs through requested
`split="train"`, while retaining `selection` in the task ID and returning
`dataset_split="selection"`. Internal heldout IDs require
`split="heldout"`. `/taskset` consequently advertises only:

| Environment | Public train | Public heldout |
| --- | ---: | ---: |
| Craftax Multiplayer | 352 | 160 |
| DungeonGrid | 216 | 72 |
| Overcooked V2 | 72 | 24 |

`/taskset` exposes public counts only. `/taskset/tasks` resolves every requested
ID inside the supplied public split and returns a generic error for a
cross-split ID. It never returns labels or checkpoint contents. Every returned
row includes a `roles` string array for exact role arms. Example train IDs are:

```text
craftax_coordination_v1:train:1001:iron_handoff
dungeongrid_coordination_v1:train:blackwater_bell_breach:identity:original:pre_breach
overcooked_v2_coordination_v1:train:train_hidden_1101:r01:hidden_recipe_reveal
```

## Mutable program and semantic directives

All three environments return the identical three-field string program:

- `shared_instruction`
- `communication_policy`
- `role_prompts`

Only exact `KEY=VALUE` directives separated by semicolons or newlines are
recognized. Unknown, vague, malformed, misplaced, or out-of-range text leaves
that semantic at seed behavior.

```text
shared_instruction:
  PRIORITY=SAFETY|DELIVERY|EXTRACTION

communication_policy:
  SPEAK=ALWAYS|EVENT_TRIGGERED|SILENT
  MAX_CHARS=8..240
  REQUEST=ACTION_ONLY|REQUEST_THEN_ACT|REQUEST_ONLY
  HANDOFF=DIRECT|REQUIRED|NONE
  FOLLOWER_REPLY=ACK|ON_REQUEST|SILENT

role_prompts:
  ROLE_ASSIGNMENT=FLEXIBLE|SPECIALISTS|DUPLICATED
  ROLE[<role>]=FLEXIBLE|SPECIALIST|DUPLICATED|SILENT
```

For Craftax, the load-bearing priority is `DELIVERY`; for DungeonGrid it is
`EXTRACTION`; for Overcooked it is `DELIVERY`. A compact specialist candidate
can pair that priority with `SPEAK=EVENT_TRIGGERED`,
`REQUEST=REQUEST_THEN_ACT`, `HANDOFF=REQUIRED`, `FOLLOWER_REPLY=SILENT`, and
`ROLE_ASSIGNMENT=SPECIALISTS`.

Craftax rows expose `warrior`, `forager`, and `miner`; DungeonGrid rows expose
the committed party roles. Overcooked roles are probe- and agent-count-specific:
hidden-recipe rows expose `cook` and `ingredient_0`, three-chef assignment rows
expose `ingredient_0`, `ingredient_1`, and `cook`, four-chef assignment rows
also expose `delivery`, and handoff rows expose `cook` and `delivery`.

## Requests and matched diagnostics

Every rollout must explicitly supply `metadata.evaluation_arm`, including the
primary arm. Accepted ids are:

- `primary`
- `channel_masked`
- `role_permuted`
- `role_ablation::<role>`

`channel_masked` executes and records the same send or grounded-signal
actions/events, then drops only delivery to the dependent choice. Overcooked
uses real recipe-button, pot-state, and counter-handoff actions/events; it does
not claim free-text engine messaging, and reports zero message characters.
`role_permuted` changes only specialist assignment. A role ablation replaces
only the named row-valid role's parsed role prompt with
`metadata.ablation_baseline`; aliases
`parent_candidate`, `seed_candidate`, `parent_behavior`, and `seed_behavior`
are accepted. The baseline may be a `role_prompts` string or a candidate object.

Missing/unknown arms, missing roles, missing ablation baselines, and conflicting
`metadata.ablate_role` values return HTTP 400. Every non-primary success carries
`intervention_applied=true`, the checkpoint digest, and its typed arm receipt in
top-level `intervention_evidence`, `summary.intervention`, and
`trace.intervention`.

Fetch and roll out one Craftax train row:

```bash
curl -sS -X POST http://127.0.0.1:8788/taskset/tasks -H 'content-type: application/json' -d '{"split":"train","task_ids":["craftax_coordination_v1:train:1001:iron_handoff"],"filters":{}}'
curl -sS -X POST http://127.0.0.1:8788/rollout -H 'content-type: application/json' -d '{"task":{"task_id":"craftax_coordination_v1:train:1001:iron_handoff","split":"train"},"candidate":{"shared_instruction":"PRIORITY=DELIVERY","communication_policy":"SPEAK=EVENT_TRIGGERED; MAX_CHARS=64; REQUEST=REQUEST_THEN_ACT; HANDOFF=REQUIRED; FOLLOWER_REPLY=SILENT","role_prompts":"ROLE_ASSIGNMENT=SPECIALISTS"},"metadata":{"evaluation_arm":"primary"}}'
```

The response includes numeric `reward_info.outcome_reward`, all requested
coordination metrics, generated versus applied actions, raw authority events,
per-agent contribution signals, parser diagnostics, and initial/final state
digests. IMAC should consume primary-arm metrics only; non-primary arms are
matched diagnostic evidence for COMA, IC3Net, and RODE.

## Current boundary

This is a controlled prompt-to-protocol experiment, not a natural-language or
model-backed policy. The executor intentionally recognizes only the documented
directives and the frozen MAPO continuation families. Unknown text retains seed
behavior rather than selecting an oracle continuation.
