# GameBench — Sokoban singleplayer gold

You are in a **cleanroom** Harbor workspace. Rebuild the Sokoban **singleplayer gold** simulation from the provided specs.

## Deliverable

Implement a Python package under `/workspace/candidate` with the same layout as the GameBench task lane:

- `gold_python/` — engine, NEV log, checkpoint, observations, render, `service.py` (FastAPI)
- `shared/` — task resolver + HTTP contract helpers (copy/adapt from specs)
- `scripts/run_service.py` — starts the HTTP gold service (`--lane python`)

The verifier will:

1. spawn your HTTP service on port `19092`
2. run **15 fixed scenarios** (inline puzzles + curriculum seeds)
3. compare **legacy NEV event strings** and **terminal public state** against hidden gold fixtures
4. score **spectrum correctness** (mean NEV hit rate)

## Allowed inputs

- `/workspace/spec/` — normative specs (deterministic tasks, NEV, HTTP protocol, checkpoints)
- Your own reasoning and code in `/workspace/candidate`

## Forbidden

- Reading `/task/tests/fixtures` or any hidden verifier data
- Copying from `/task/reference` (not available to you during agent phase)
- Internet access

## HTTP surface (minimum)

Your service must implement the gold routes documented in `spec/http_protocol.md`:

- `GET /health`
- `POST /run_scenario` with `{"task": {...}}`
- `POST /rollouts` with `{"task": {...}, "seed": N}`
- `POST /rollouts/{rollout_id}/step`
- `GET /rollouts/{rollout_id}/readout`
- checkpoint save/restore routes used by the gold eval lane

## Scoring (ProgramBench-style spectrum)

Per scenario:

- `nev_hit_rate` — fraction of gold NEV strings matched in order
- `public_hit_rate` — fraction of terminal public fields matching gold

Aggregate:

- **resolved** = 100% on both signals
- **almost** = ≥95% on both
- Harbor reward defaults to **mean NEV hit rate** across scenarios

See `spec/spectrum_correctness.md`.

## Tips

- All randomness must come from task `seed` — no wall clock, no UUID episode ids in the parity surface.
- Push semantics follow standard Sokoban: player moves into boxes; illegal pushes emit `push_blocked` NEV.
- Start with `GET /health` and one inline scenario before expanding.

When finished, ensure `python /workspace/candidate/scripts/run_service.py --lane python` starts cleanly on port `19092`.
