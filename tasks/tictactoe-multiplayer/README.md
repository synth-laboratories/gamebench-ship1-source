# Tic-Tac-Toe multiplayer — GameBench gold reference

Gold reference for **MARL joint-step** tic-tac-toe (`agent_0` = X, `agent_1` = O). Step API follows JaxMARL/Overcooked conventions — see [`spec/marl_env_standards.md`](../../spec/marl_env_standards.md). Task JSON format: [`spec/task_bundle_format.md`](../../spec/task_bundle_format.md).

Contrast with [`tasks/tictactoe-singleplayer/`](../tictactoe-singleplayer/) which uses a single `action` dict per step (`player` + `position`).

## Layout

```text
tasks/tictactoe-multiplayer/
  gold/           joint-step engine, per-agent obs/rewards/dones, HTTP service
  policies/       bundled opponent policies
  tasks/          Rich per-task JSON (`agent_0_policy` / `agent_1_policy`)
  fixtures/gold/  Golden NEV (JointTurn / MoveApplied(agent_id,…))
  scripts/        run_service, verify_gold_nev
  docs/           HTTP protocol
```

## Quick start

```bash
cd tasks/tictactoe-multiplayer
PYTHONPATH=. python scripts/verify_gold_nev.py
PYTHONPATH=. python scripts/run_service.py
```

Default port `8082` (eval lane default `18082`).

## Joint step example

```json
{
  "joint_action": {
    "agent_0": {"kind": "place", "position": 4},
    "agent_1": {"kind": "wait"}
  }
}
```

## Correctness gate

```bash
PYTHONPATH=. python scripts/verify_gold_nev.py
```

## Container routes

- `GET /health`, `GET /info`, `GET /agents`
- `POST /rollout`, `POST /run_scenario`
- `POST /reset`, `POST /rollouts/{id}/step` (body uses `joint_action`)
- Checkpoint + NEV routes (same as single-player lane)

See [`docs/http_protocol.md`](docs/http_protocol.md).
