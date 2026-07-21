# Rogue Singleplayer

This task is a compact deterministic GameBench lane for Rogue 5.4.4 on the `modern-rogue` branch of `Davidslv/rogue`.

Status: source-witnessed. The Python and Rust gold lanes use upstream `modern-rogue` C source as the behavior authority for the modeled GameBench command, state, event, reward, checkpoint, save, and policy surfaces.

It preserves the benchmark-facing command surface and symbols needed for deterministic policy work:

- vi movement: `h`, `j`, `k`, `l`, `y`, `u`, `b`, `n`
- rest/search/pickup/descend: `.`, `s`, `,`, `>`
- Rogue symbols: `@`, `.`, `|`, `-`, `*`, `:`, `%`

It is not a terminal/curses adapter, scorefile implementation, or lockfile implementation. GameBench-visible behavior is modeled as structured state transitions and NEV events rather than terminal screen scraping.

Cybernetic example: inventory/frontier/survival planner over Rust gold — [docs/cybernetic_example.md](docs/cybernetic_example.md).

## 1:1 Requirement

The Rogue lane uses the upstream `modern-rogue` C source as the behavior authority while remaining pure Python and pure Rust. No C wrapper, PTY adapter, or compiled C binding is part of the GameBench lane.

Independent Python/Rust source ports are accepted only where behavior is proven against source-derived C witnesses, Python/Rust lane parity, upstream-equivalent command traces, and serialized state/checkpoint projections.

Observed upstream facts:

- `./configure --enable-wizardmode=yes --enable-scorefile=no --enable-lockfile=no` succeeds.
- `make` succeeds on this machine.
- deterministic `SEED` is honored only in wizard mode.
- runtime input flows through curses `readchar()`/`md_readchar()`.
- save/checkpoint authority lives in upstream `state.c`/`save.c`.

## Commands

```bash
python3 scripts/verify_gold_nev.py --lane both
python3 scripts/compare_gold_lanes.py --parity-only
python3 scripts/bench_checkpoint.py --lane both --iterations 300
bash containers/codepolicy/smoke_rollout.sh
bash containers/react/smoke_rollout.sh
```
