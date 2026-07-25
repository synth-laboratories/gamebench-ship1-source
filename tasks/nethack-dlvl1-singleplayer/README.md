# NetHack dlvl-1 single-player

This is an **own Python + Rust symbolic emulator** of Main Dungeon level 1 for
GameBench.  It ends an episode on death, quit, truncation, or the first use of
the down stair.  It does not generate or simulate dlvl 2, branches, or the
rest of NetHack.

NLE is a discrepancy oracle, not a runtime dependency or wrapper.  Gold code
does not import `nle`, call a NetHack binary, open a PTY, or delegate actions to
an emulator.  When an NLE development environment is available,
`scripts/capture_nle_fixture.py` freezes level dumps, action tapes, and
observation snapshots.  Both gold lanes then replay those files without NLE.

## Contract

- The public wire action is the integer index in pinned `nle.nethack.ACTIONS`.
  See [`shared/nle_action_map.md`](shared/nle_action_map.md).
- All actions in that table are accepted, including command, Meta/control, and
  prompt-text actions.  The engine publishes an explicit mode stack:
  `normal`, `direction`, `inventory_letter`, `ynq`, `menu`, `string`, or `more`.
- Fixtures provide the authoritative dlvl-1 `level_dump`; open-play seeds use
  gold's own deterministic mixer and make no same-seed NLE generation claim.
- Observations expose a fixed 21×79 `chars`/`colors`/`glyphs` projection,
  25-slot `blstats`, normalized message plus raw bytes, inventory arrays, and
  terminal state.
- `>` performed while standing on the captured down-stair emits
  `stairs_descend` and `terminal(descended)`.  No post-descend NLE map is read.

## Layout

```text
gold_python/     Python FastAPI lane and scenario runner
gold_rust/       Rust Axum lane and JSON-stdin scenario runner
shared/          wire contract, action map, resolver, NEV vocabulary
fixtures/gold/   owned GameBench scenarios / expected projections
fixtures/nle_oracle/
                 frozen NLE captures; no NLE installation needed to replay them
scripts/         capture, discrepancy, parity, fixture, service, policy tools
```

## Local use

Run either HTTP lane:

```bash
python scripts/run_service.py --lane python --port 8120
python scripts/run_service.py --lane rust --port 8121
```

Run a fixture through the Python or Rust scenario lane:

```bash
python scripts/run_policy.py --lane python --scenario fixtures/gold/scenarios/bootstrap_descend.json
python scripts/run_policy.py --lane rust --scenario fixtures/gold/scenarios/bootstrap_descend.json
```

The NLE capture script is intentionally optional.  It errors with a direct
dependency explanation if `nle==0.9.0` is unavailable; minimal CI only replays
already committed captures.  Capture default is raw NLE `MORE` behavior, so
every `MiscAction.MORE` remains visible in a tape.

## Current status

The checked-in implementation establishes the dual-lane engine, full action
acceptance, fixed-crop observation contract, deterministic checkpoint/restore,
and capture/discrepancy plumbing.  It is not yet an assertion that the required
33 authentic NLE tapes have been captured; coverage and deliberate stubs are
tracked in [`PROGRESS.md`](PROGRESS.md).
