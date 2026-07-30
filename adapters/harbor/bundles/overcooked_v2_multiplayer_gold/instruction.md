# GameBench — Overcooked v2 multiplayer gold

You are in a **cleanroom** Harbor workspace. Rebuild the Overcooked v2 **multiplayer gold** simulation from the provided specs.

## Deliverable

Implement a Python package under `/workspace/candidate` with:

- `gold_python/` — simultaneous joint-step MARL engine, NEV log, checkpoint, `service.py` (FastAPI)
- `shared/` — layout parser, task resolver
- `scripts/run_service.py` — starts the HTTP gold service (`--lane python`)

The verifier will:

1. spawn your HTTP service on port `19094`
2. run **13 fixed scenarios** with scripted `joint_actions`
3. compare **legacy NEV event strings** and **terminal public state** against hidden gold fixtures
4. score **spectrum correctness** (mean NEV hit rate)

## MARL contract

- Two agents: `agent_0`, `agent_1`
- **Simultaneous** joint step each tick: `{"agent_0": {...}, "agent_1": {...}}`
- Actions: `move` (N/S/E/W), `interact`, `wait`
- See `spec/marl_env_standards.md`

## HTTP surface (minimum)

- `GET /health`
- `POST /run_scenario` with `{"task": {...}}` (task may include `joint_actions`)
- `POST /rollouts` with `{"task": {...}, "seed": N}`
- `POST /rollouts/{rollout_id}/step` with `{"joint_action": {...}}`
- checkpoint save/restore routes

## Forbidden

- Reading `/task/tests/fixtures` or hidden verifier data
- Internet access
