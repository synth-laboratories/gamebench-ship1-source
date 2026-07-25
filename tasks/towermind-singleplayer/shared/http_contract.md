# TowerMind local service contract

The Python local service is dependency-free and intended for local policy/DEO
work. It exposes `GET /health`, `POST /rollouts`, and `POST`
`/rollouts/{id}/step|checkpoint|restore`. All request and response bodies are
JSON. `POST /rollouts` accepts `level`, `seed`, and optional `initial_gold`;
the step endpoint accepts `{"action": <discrete action>}`.

Gold lanes are the authority. This service does not proxy a Unity process or an
upstream TowerMind runtime.
