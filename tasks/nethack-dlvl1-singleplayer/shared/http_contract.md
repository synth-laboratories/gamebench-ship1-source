# NetHack dlvl-1 HTTP contract

Both gold lanes expose the same endpoints:

- `GET /health`
- `POST /run_scenario`
- `POST /rollouts`
- `POST /rollouts/{id}/step`
- `POST /rollouts/{id}/checkpoint`
- `POST /rollouts/{id}/restore`
- `POST /rollouts/{id}/simulate`
- `GET /rollouts/{id}/readout`
- `GET /rollouts/{id}/event_log`

`POST /rollouts/{id}/step` accepts either an integer NLE action-space index or a
canonical action name:

```json
{"action": 57}
```

```json
{"action": "Command.OPEN"}
```

The first form is the wire authority.  The second is a scenario-authoring
adapter.  Raw printable keys are accepted only as a convenience and must not be
used to establish oracle tapes.

Every rollout response contains `readout.public`, whose stable comparison fields
are `chars`, `colors`, `glyphs`, `blstats`, `message`, `inventory`, `input_mode`,
`done`, and `terminal_reason`.  The map plane is always a 21×79 crop.  `blstats`
uses the pinned 25-field NLE ordering and is accompanied by `blstats_named`.

Checkpoint blobs use `gamebench.checkpoint.v1`, include the resolved fixture
input, simulator state, and complete structured NEV log, and can be restored
across Python and Rust lanes.

The episode ends with `terminal_reason=descended` when `MiscDirection.DOWN` is
performed on the dlvl-1 down stair.  The response never represents dlvl 2.
