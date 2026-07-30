# Pokémon Emerald Littleroot HTTP Contract

The Rust gold service defaults to port `8103` and exposes the common GameBench
rollout surface:

- `GET /health`
- `GET /info`
- `POST /rollouts` — optional `{ "checkpoint": "title_menu|truck_arrival|bedroom_idle|birch_lab_exterior|rival_outside_lab|route101_rescue|route103_rival|running_shoes" }`; defaults to `rival_outside_lab`.
- `POST /rollouts/{rollout_id}/step` — `{ "action": "up|down|left|right|a|b|start|select|noop", "frames": integer }`
- `GET /rollouts/{rollout_id}/readout`
- `GET /rollouts/{rollout_id}/frame` — raw RGB24 payload with headers for width,
  height, and SHA-256.
- `GET /rollouts/{rollout_id}/render.png` — lossless PNG encoding of the same
  canonical RGB24 frame.

`GET /frame` is deliberately raw RGB rather than a PNG during bootstrap. This
keeps the parity oracle focused on the canonical 240×160 pixel buffer; a PNG
adapter can be added without changing the rendered bytes.

Every rollout `readout` includes `reference_diff` when an exact captured trace
or a declared comparison baseline exists. It reports differing pixels/channels,
maximum channel delta, and total channel delta; `baseline_only` is true when no
matching input replay has been captured yet.
