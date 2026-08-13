# Sokoban singleplayer (GameBench)

Classic authority: **`gold_python/`** (FastAPI gold HTTP).

Rust gold lane: **`gold_rust/`** (axum bin `sokoban_gold`) — same [`shared/http_contract.md`](shared/http_contract.md) routes as Python.  
`GET …/render.svg` and `…/render.png` remain **Python-only** until ported.

## Quick start

```bash
# Python gold (port 8092)
python scripts/run_service.py --lane python

# Rust gold (port 8093) — requires cargo
python scripts/run_service.py --lane rust
```

## Parity

```bash
python scripts/parity_rust_python.py
# cargo test --manifest-path gold_rust/Cargo.toml
python scripts/run_policy_sweep.py \
  --engine-lane rust \
  --policy containers/codepolicy/heuristic_policy.py \
  --suite defaults/policy_sweep/policy_smoke_v1.json \
  --output /tmp/sokoban_rust_policy_smoke.json
```

Fixture: [`fixtures/gold/parity/parity_mini.json`](fixtures/gold/parity/parity_mini.json).

## Follow-on (outside this task lane)

Craftax_speedrun CISPO / synth-container `/verify`+`/annotate` wiring against this gold is deferred — see  
`experiments/craftax_speedrun/SOKOBAN_RUST_FOLLOWON.md` in the experiments repo.
