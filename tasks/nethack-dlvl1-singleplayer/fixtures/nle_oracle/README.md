# Frozen NLE oracle corpus

Each authentic capture lives in its own directory:

```text
<fixture-id>/
  meta.json
  actions.jsonl
  snapshots.jsonl
  level_dump.json
  tape_manifest.json
```

`meta.json` pins NLE/NetHack versions, full ordered action mapping hash,
character options, seed data, observation-key order, and raw/auto-MORE policy.
`actions.jsonl` records one wire action index per line.  `snapshots.jsonl`
contains the projected observation after each action plus an initial step-zero
snapshot.  The down-stair boundary is captured without stepping live NLE into
dlvl 2.

`tape_manifest.json` locks every raw file by SHA-256 and records each exact
input with hashes of its pre-state, post-state, and raw terminal evidence.
The harsh judge refuses missing or stale manifests. Captures made after the
manifest workflow was introduced also contain exact capture-runtime binary and
script fingerprints; older captures are truthfully marked
`legacy_version_only`.

No synthetic gold output may be put in this directory. The corpus currently
contains 31 strict-green captures, including navigation, fixed-stair pickup,
food/open prompt cancellation, empty search, stationary WAIT, EXTCMD prompt/cancel, ENGRAVE prompt/cancel, DROP prompt/cancel, WEAR/PUTON no-item cancellation, TAKEOFF, WIELD prompt/cancel, QUAFF/READ no-item cancellation, FIRE no-ammo redirect, THROW/QUIVER prompt/cancel, REMOVE/INVOKE empty selectors, ZAP no-wand cancellation, failed kick, closed/no-door
close, raw horizontal and vertical door opening, confirmed quit terminal UI,
declined quit, and the zero-turn inventory display. Every capture is replayed
against both gold lanes across the full public observation planes; no fixture
is a message-only or character-only claim.

The required 33 tapes are a v0 minimum: a strict-green, hand-reviewed canonical
gate. It is expected to grow beyond 33, but generated diagnostic artifacts
remain outside this directory until they are reproducible, minimized, confined
to Main Dungeon dlvl 1, directly annotated from NLE observations, and strict
green in both own lanes.
