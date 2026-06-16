# GameBench — working notes

**Repo:** https://github.com/JoshuaPurtell/gamebench (private)  
**Created:** 2026-06-16  
**Related:** [engine-bench](https://github.com/JoshuaPurtell/engine-bench), [engine-bench-tcg](https://github.com/JoshuaPurtell/engine-bench-tcg), Synth `engine_bench` container lane

---

## North star

**GameBench** evaluates whether an agent (or human workflow) can **replicate recognizable game environments** — Crafter, Craftax, Minigrid, NetHack — in **Python or Rust**, such that behavior is verified by **event-log–based tests**, not brittle pixel/state snapshots alone.

Success means: same *kinds* of events and outcomes as reference envs, with engineering properties we care about for agent eval and training loops.

---

## Scope (initial)

| Reference env | Notes | Impl language (TBD) |
|---------------|-------|---------------------|
| **Crafter** | 2D survival/crafting; modular Rust reference in `crafter-rs` | Python or Rust |
| **Craftax** | JAX/Crafter-like; long-horizon agent evals in Synth stack | Python or Rust |
| **Minigrid** | Gridworld RL; compact, good for smoke + CI | Python likely |
| **NetHack / NLE** | Roguelike; `liter` / Netter modules in engine-bench lineage | Rust or Python wrapper |

Not in v0 unless trivial: full 3D engines, networked multiplayer, training-at-scale infra.

---

## Core evaluation model

### Event-log tests (primary verifier)

- Env emits a **structured event stream** (actions, state transitions, rewards, terminal conditions).
- Tests assert **sequences / predicates** on events (order, counts, invariants), not full world tensors.
- Reference runs produce **golden event logs** (or compact summaries) for regression.
- Favor **deterministic replay**: given seed + action log → same event log.

### What we are *not* optimizing for first

- Pixel-identical rendering
- Bit-identical float state across Python/Rust ports (unless we explicitly pin that)
- Leaderboard scores on original upstream harnesses (nice later, not gate v0)

---

## Desiderata (engineering)

These are **requirements** for any GameBench env implementation we ship:

1. **Cheap checkpoints** — snapshot/restorable state small and fast (target: ms-scale restore, KB–MB not GB).
2. **Deterministic stepping** — seeded RNG; reproducible event logs.
3. **Event log as first-class artifact** — every rollout exports a canonical log format.
4. **Headless / CI-friendly** — no GPU required for default test suite.
5. **Dual implementation tolerance** — same event-log contract across Python and Rust where we claim parity.
6. **Composable scenarios** — short tasks (smoke) + longer horizons without new infra each time.
7. **Agent-agnostic runner** — Harbor / synth-container / plain pytest hooks (don't pick one winner in v0 notes).

Stretch:

- Fork/resume from checkpoint mid-episode for agent recovery evals
- Diff event logs for debugging failed rollouts
- Cost accounting (steps, wall time) per scenario

---

## Relationship to Engine-Bench

| | Engine-Bench | GameBench |
|---|--------------|-----------|
| Focus | Implement **modules** inside existing engine repos (TCG cards, Netter modules, Crafter modules) | **Replicate whole env families** with shared test contract |
| Verifier | `cargo test` + compile score | Event-log predicates + optional compile/test |
| Upstream | Clones `engine-bench-tcg`, `liter`, `crafter-rs` | Reference behavior from Crafter, Craftax, Minigrid, NLE |
| Audience | Harbor / Terminal-Bench tasks | Agent eval + Synth lanes + possible public benchmark |

GameBench can **consume** Engine-Bench task ideas (e.g. Crafter modules) but owns the **cross-env event contract** and checkpoint story.

---

## Proposed repo structure (future — not implemented yet)

```
gamebench/
  NOTES.md              # this file
  spec/
    event_log.md        # event schema + examples
    checkpoint.md       # checkpoint format + size budgets
  envs/
    crafter/
    craftax/
    minigrid/
    nethack/
  tests/                # cross-env contract tests
  scenarios/            # named scenarios → env + seed + event expectations
```

---

## Open questions

- [ ] **Event schema:** one global schema vs per-env extensions?
- [ ] **Checkpoint format:** serde/json snapshot vs custom binary vs upstream-native save formats?
- [ ] **Parity bar:** exact event match vs semantic equivalence class?
- [ ] **First env:** Crafter (Rust lineage) vs Minigrid (smallest) for v0 smoke?
- [ ] **Synth integration:** new container template vs extend `engine_bench` vs Harbor-only?
- [ ] **Public vs private:** keep private until first scenario green, then mirror subset public?

---

## Next steps (suggested)

1. Write `spec/event_log.md` — minimal v0 schema (timestamp, kind, payload, episode_id, step).
2. Pick **one** env (Minigrid or Crafter) for **one** golden scenario + event-log test.
3. Implement **reference runner** that records events and diffs against golden.
4. Document checkpoint size/latency budget with a single benchmark script.
5. Link from Synth evals lane once smoke is green (no launch claim until proved).

---

## Links

- Engine-Bench Harbor wrapper: https://github.com/JoshuaPurtell/engine-bench
- Crafter Rust: https://github.com/JoshuaPurtell/crafter-rs
- Netter / liter: https://github.com/JoshuaPurtell/liter
- Backend engine_bench container: `backend/services/container_pools/containers/templates/engine_bench/`
