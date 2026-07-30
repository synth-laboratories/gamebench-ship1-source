# FrogsGame Singleplayer

FrogsGame is a deterministic placement puzzle. An `N x N` board has exactly `N` color regions. A valid terminal placement has exactly one frog in each row, each column, and each color, with no two frogs touching orthogonally or diagonally.

The reward is defined programmatically in `shared/scoring.py`: `1.0` iff the submitted board is complete and valid, otherwise `0.0`.

Cybernetic example: invariant explainer and move-order repair over Rust gold — [docs/cybernetic_example.md](docs/cybernetic_example.md).

## Gold Lanes

- `gold_python/`: Python gold engine and FastAPI service.
- `gold_rust/`: Rust gold engine, scenario runner, benchmark binary, and axum service.
- `shared/`: scoring, task resolution, NEV kinds, and HTTP contract.
- `fixtures/gold/`: canonical scenarios and eventlog fixture metadata.
- `scripts/`: parity verification, checkpoint benchmark, lane comparison, and service runner.

## Commands

```bash
python3 scripts/verify_gold_nev.py --lane both
python3 scripts/compare_gold_lanes.py --parity-only
python3 scripts/bench_checkpoint.py --lane both --iterations 300
python3 scripts/generate_eventlogs.py
bash containers/codepolicy/smoke_rollout.sh
bash containers/react/smoke_rollout.sh
python3 scripts/run_service.py --lane python
python3 scripts/run_service.py --lane rust
```
