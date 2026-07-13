# Craftax-Coop multiplayer

This is a distinct, self-contained GameBench multiplayer task based on the semantics of Multi-Agent Craftax (arXiv:2511.04904) and the authors' `MA-Craftax` reference. It has no runtime dependency on JAX, Flax, JaxMARL, or `craftax-singleplayer`.

The default game uses three simultaneous agents (`agent_0` Warrior, `agent_1` Forager, `agent_2` Miner), nine deterministic 48×48 levels, shared rewards and achievements, common world/resources/combat, requests and directed giving, and boss/death/timestep endings. Observations are per-agent symbolic JSON with an 11×11 ASCII view and a shared teammate dashboard.

Actions are objects such as `{"kind":"left"}`, `{"kind":"request_iron"}`, or `{"kind":"give_iron_to_agent_2"}`. All joint steps must name every agent. Requests last 10 turns unless fulfilled. Checkpoints serialize all authoritative state; structured and legacy NEV are both retained.

## Role semantics

- Warrior deals double base combat damage.
- Forager can team-heal and rests more efficiently.
- Miner alone gathers advanced ores, receives double ore yield, and crafts advanced equipment.

## Intentional parity boundaries

The Python and Rust lanes share dimensions, roles, simultaneous movement conflict rules, request expiry, directed trades, shared rewards, checkpoint state, and death/timestep termination. Python is the complete GameBench HTTP/JSON authority and additionally implements collection/crafting, nine-level traversal, role-gated abilities, symbolic observations, achievements, and boss combat. Rust exposes the deterministic contract core as a library and CLI fixture runner; its map PRNG and currently smaller mechanic surface are an explicit parity deviation. Exact author-reference parity is also not claimed for JAX PRNG bitstreams, pixel rendering, procedural dungeon rooms, the complete Craftax mob taxonomy, projectile physics, enchantments, or every original achievement; those require JAX-specific arrays/assets or considerably broader engine work. These omissions are surfaced here rather than silently replaced with a single-player fallback.

## Usage

`python scripts/run_policy.py --seed 101 --steps 100`

`python scripts/run_service.py --port 8080`

`cargo run --manifest-path gold_rust/Cargo.toml --example smoke`
