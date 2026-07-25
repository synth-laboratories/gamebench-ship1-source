# Hanabi Multiplayer

A deterministic two-player Hanabi environment for cooperative code-policy
optimization. The candidate controls `agent_0`; a fixed convention-aware
baseline controls `agent_1`. Both receive private observations that hide their
own cards.

The gold engine owns deck construction, seeded shuffling, hints, card
knowledge, fireworks, discards, tokens, final-round timing, NEV events, and
checkpoint/restore behavior. It has no external runtime dependencies.

Policy contract:

```python
def act(observation: dict) -> dict:
    return {"kind": "hint", "rank": 1}
```

Actions are `{"kind": "play", "slot": N}`,
`{"kind": "discard", "slot": N}`, and a `hint` with exactly one of `color` or
`rank`.

Run the baseline sweep from the repository root:

```bash
python3 tasks/hanabi-multiplayer/scripts/run_policy_sweep.py \
  --policy tasks/hanabi-multiplayer/policies/heuristic_baseline.py \
  --output /tmp/hanabi-baseline.json
```
