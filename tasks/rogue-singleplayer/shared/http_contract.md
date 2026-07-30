# Rogue HTTP Contract

The Rogue gold lanes expose:

- `GET /health`
- `POST /run_scenario`
- `POST /rollouts`
- `POST /rollouts/{id}/step`
- `POST /rollouts/{id}/checkpoint`
- `POST /rollouts/{id}/restore`
- `POST /rollouts/{id}/simulate`
- `GET /rollouts/{id}/readout`
- `GET /rollouts/{id}/event_log`

Actions are Rogue command characters: `h`, `j`, `k`, `l`, `y`, `u`, `b`, `n`, `.`, `,`, `>`, and `s`.
