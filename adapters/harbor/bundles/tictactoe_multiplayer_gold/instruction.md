# GameBench — Tic-Tac-Toe multiplayer gold

You are in a **cleanroom** Harbor workspace. Rebuild the tic-tac-toe **multiplayer gold** simulation from the provided specs.

## Deliverable

Implement a Python package under `/workspace/candidate` with the same layout as a GameBench task lane:

- `gold/` — engine, NEV log, checkpoint, observations, render, `service.py` (FastAPI)
- `policies/` — Monty opponent modules referenced by scenario tasks
- `scripts/run_service.py` — starts the HTTP gold service

The verifier will:

1. spawn your HTTP service
2. run **20 fixed scenarios** (distinct seeds / policy pairings)
3. compare **legacy NEV event strings** and **terminal public state** against hidden gold fixtures
4. score **spectrum correctness** (not just pass/fail)

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
- `POST /reset`
- `POST /rollouts/{rollout_id}/step`
- `GET /rollouts/{rollout_id}/events`
- checkpoint routes used by the gold eval lane

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

- All randomness must come from task `seed` + policy `(seed, ply)` — no wall clock, no UUID episode ids in the parity surface.
- `POST /run_scenario` must replay bundled Monty policies for `agent_0_policy` / `agent_1_policy` in the task JSON.
- Start with `GET /health` and one scenario before expanding.

When finished, ensure `python /workspace/candidate/scripts/run_service.py` starts cleanly on port `19082`.
