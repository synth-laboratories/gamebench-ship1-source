# Craftax-Coop multiplayer

This is a distinct, self-contained GameBench multiplayer task based on the semantics of Multi-Agent Craftax (arXiv:2511.04904) and the authors' `MA-Craftax` reference. It has no runtime dependency on JAX, Flax, JaxMARL, or `craftax-singleplayer`.

The default game uses three simultaneous agents (`agent_0` Warrior, `agent_1` Forager, `agent_2` Miner), nine deterministic 48×48 levels, shared rewards and achievements, common world/resources/combat, requests and directed giving, and boss/death/timestep endings. Observations are per-agent symbolic JSON with an 11×11 ASCII view and a shared teammate dashboard.

Actions are objects such as `{"kind":"left"}`, `{"kind":"request_iron"}`, or `{"kind":"give_iron_to_agent_2"}`. All joint steps must name every agent. Requests remain active for 10 turns and can receive repeated gifts. Version-2 checkpoints serialize all authoritative state; structured and legacy NEV are both retained.

## Role semantics

- Warrior deals double base combat damage, crafts advanced swords/arrows, uses bows, and enchants weapons.
- Forager has triple food/drink capacity, gathers saplings, gains food from passive mobs, and casts the team-heal spell.
- Miner crafts pickaxes and torches and alone places stone bridges; both Miner and Warrior can cast the learned fireball spell.

## Parity and author-reference boundaries

Python and Rust are independent runtime authorities with the same deterministic map generator, world/player state, simultaneous conflict rules, role abilities, requests/trades, collection and crafting, mobs and projectiles, plants/chests/potions/books/enchantments, attributes, traversal, boss progression, rewards, checkpoints, observations, NEV, and terminal conditions. `scripts/verify_python_rust_parity.py` compares canonical cooperative, combat, collection, expiry, plant/time, boss, death, timestep, and checkpoint scenarios.

This is a pure-language semantic port, not a byte-for-byte execution of the authors' JAX program. Consequently JAX PRNG bitstreams are not reproduced. The two runtimes instead share a specified integer mixer, room/smooth-biome generator, and deterministic spawn selection. Dungeon topology, biome/resource constraints, local light maps, simultaneous shared-target resolution, mob classes, elemental damage, projectile capacities, plants, floor gates, and boss rounds are preserved semantically, but a seed does not produce the same individual tiles or random draws as JAX. The GameBench task provides symbolic JSON/ASCII rather than the author repository's pixel asset renderer. These are representation and PRNG boundaries; none falls back to `craftax-singleplayer` or removes a cooperative action/dynamic.

Python and Rust emit the same canonical structured and legacy NEV records for parity traces. The parity verifier compares the full logs for reset, joint actions, requests, movement, and resource collection, in addition to semantic scenario projections and cross-language checkpoint restoration. The fixture bundle pins broader canonical Python event/state artifacts, while HTTP action-tape replay proves both services consume the same policy trace.

## Usage

`python scripts/run_policy.py --seed 101 --steps 100`

`python scripts/run_service.py --port 8080`

`cargo run --manifest-path gold_rust/Cargo.toml --example smoke`

Checkpoint-based MAPO coordination dataset and Rust reference evaluation:

`cargo run --release --manifest-path gold_rust/Cargo.toml --example mapo_coordination_eval`

The evaluator uses disjoint train/selection/heldout seed ranges and frozen iron handoff, food rescue, miner crafting, and expiring-request probes. Candidate prompts live in `defaults/mapo_coordination/candidates_v1.json`; every continuation records grounded request/give actions and state evidence under `reports/mapo_coordination_rust_eval.json`. The bundled executor profiles are reference behaviors, not a replacement for model-backed execution of arbitrary natural-language candidates.

`cargo run --manifest-path gold_rust/Cargo.toml --bin service -- 127.0.0.1:8081`

`python scripts/verify_python_rust_parity.py`

Canonical multiplayer fixture verification (five deterministic task bundles with
structured NEV, legacy NEV, projected observations/state, request expiry,
resource giving, checkpoint restore, and timestep termination):

`python scripts/verify_gold_fixtures.py`

Regenerate those checked-in artifacts after an intentional runtime contract
change with `python scripts/generate_gold_fixtures.py`.

Shared HTTP policy runner (works against either service):

`python scripts/run_http_policy.py --base-url http://127.0.0.1:8080 --runtime python --seed 404 --steps 300 --output reports/http_e2e/python_seed404.json`

Code-policy HTTP rollout, capturing one deterministic joint-action tape:

`python3 containers/codepolicy/rollout_code_policy.py --base-url http://127.0.0.1:8080 --runtime python --policy policies/heuristic_baseline.py --seed 101 --steps 100 --capture-actions reports/codepolicy/heuristic_seed101.actions.json --output reports/codepolicy/heuristic_seed101.python.json`

Replay those exact actions against the Rust HTTP service:

`python3 containers/codepolicy/rollout_code_policy.py --base-url http://127.0.0.1:8081 --runtime rust --seed 101 --steps 100 --replay-actions reports/codepolicy/heuristic_seed101.actions.json --output reports/codepolicy/heuristic_seed101.rust.json`

Three-agent Gemini 3.1 Flash Lite ReAct HTTP rollout (requires `GEMINI_API_KEY`), followed by a no-cost Rust replay:

`python3 containers/react/run_react_policy.py --base-url http://127.0.0.1:8080 --runtime python --model gemini-3.1-flash-lite --seed 101 --steps 30 --capture-actions reports/react/gemini_3_1_flash_lite_seed101.actions.json --output reports/react/gemini_3_1_flash_lite_seed101.python.json`

`python3 containers/react/run_react_policy.py --base-url http://127.0.0.1:8081 --runtime rust --seed 101 --steps 30 --replay-actions reports/react/gemini_3_1_flash_lite_seed101.actions.json --output reports/react/gemini_3_1_flash_lite_seed101.rust.json`

Both runners emit the same report schema with per-step joint actions, rewards, events, dones, and per-agent/team dashboard snapshots. Action tapes are runtime-neutral and validate the seed and complete agent set before replay.
