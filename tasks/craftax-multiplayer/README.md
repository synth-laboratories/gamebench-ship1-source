# Craftax-Coop multiplayer

This is a distinct, self-contained GameBench multiplayer task based on the semantics of Multi-Agent Craftax (arXiv:2511.04904) and the authors' `MA-Craftax` reference. It has no runtime dependency on JAX, Flax, JaxMARL, or `craftax-singleplayer`.

The default game uses three simultaneous agents (`agent_0` Warrior, `agent_1` Forager, `agent_2` Miner), nine deterministic 48×48 levels, shared rewards and achievements, common world/resources/combat, requests and directed giving, and boss/death/timestep endings. Observations are per-agent symbolic JSON with an 11×11 ASCII view and a shared teammate dashboard.

Actions are objects such as `{"kind":"left"}`, `{"kind":"request_iron"}`, or `{"kind":"give_iron_to_agent_2"}`. All joint steps must name every agent. Requests last 10 turns unless fulfilled. Checkpoints serialize all authoritative state; structured and legacy NEV are both retained.

## Role semantics

- Warrior deals double base combat damage.
- Forager can team-heal and rests more efficiently.
- Miner alone gathers advanced ores, receives double ore yield, and crafts advanced equipment.

## Parity and author-reference boundaries

Python and Rust are independent runtime authorities with the same deterministic map generator, world/player state, simultaneous conflict rules, role abilities, requests/trades, collection and crafting, mobs and projectiles, plants/chests/potions/books/enchantments, attributes, traversal, boss progression, rewards, checkpoints, observations, NEV, and terminal conditions. `scripts/verify_python_rust_parity.py` compares canonical cooperative, combat, collection, expiry, plant/time, boss, death, timestep, and checkpoint scenarios.

This is a pure-language semantic port, not a byte-for-byte execution of the authors' JAX program. Consequently JAX PRNG bitstreams and vectorized update ordering are not reproduced. The GameBench task provides symbolic JSON/ASCII rather than the author repository's pixel asset renderer, and represents the long-tail mob/projectile taxonomy through the same shared combat model instead of importing JAX array layouts. These are explicit representation boundaries; none falls back to `craftax-singleplayer` or removes the requested cooperative mechanics.

Python and Rust emit the same structured and legacy NEV contracts, but internal event granularity is not byte-for-byte identical: Rust records some simultaneous resolution details as separate events. The deterministic HTTP policy fixture therefore requires identical terminal state, reward, achievements, trades, and observation fields while reporting each runtime's event counts independently.

## Usage

`python scripts/run_policy.py --seed 101 --steps 100`

`python scripts/run_service.py --port 8080`

`cargo run --manifest-path gold_rust/Cargo.toml --example smoke`

`cargo run --manifest-path gold_rust/Cargo.toml --bin service -- 127.0.0.1:8081`

`python scripts/verify_python_rust_parity.py`

Shared HTTP policy runner (works against either service):

`python scripts/run_http_policy.py --base-url http://127.0.0.1:8080 --runtime python --seed 404 --steps 300 --output reports/http_e2e/python_seed404.json`

Code-policy rollout:

`python containers/codepolicy/rollout_code_policy.py --policy policies/heuristic_baseline.py --seed 101 --steps 100 --output reports/codepolicy/heuristic_seed101.json`

Three-agent Gemini 3.1 Flash Lite ReAct rollout (requires `GEMINI_API_KEY`):

`python containers/react/run_react_policy.py --model gemini-3.1-flash-lite --seed 101 --steps 30 --output reports/react/gemini_3_1_flash_lite_seed101.json`
