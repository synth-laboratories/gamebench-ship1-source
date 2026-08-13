# Opening battle source-tape coverage

This directory is the source-only capture lane for the two battle-bearing
segments in the scoped Emerald opening:

1. Route 101: Birch rescue, starter picker, and the scripted Zigzagoon fight.
2. Route 103: rival approach, trainer fight, defeat/faint branches, and the
   return-to-field handoff.

It intentionally contains neither a ROM nor a save state.  It is not consumed
by `gold_rust`, and a recorded source trace must never be described as a Rust
comparison until a separate differential runner actually compares it.

## Evidence status at creation

The nearest known source anchors are the existing frozen-frame manifest rows:

| Source split | Anchor | RGB SHA-256 | What it proves |
| --- | --- | --- | --- |
| `splits/03_birch/03_birch.state` | `opening-birch-idle` | `8a5210e713369ac061ace3f3f336a1775acbed4cb87658f548c0c76f6878f8b7` | a source frame was recorded at the Birch split boundary |
| `splits/04_rival/04_rival.state` | `littleroot-outside-birch-lab-idle` | `9374924229cdd9d32aab80f701b2da3127a075b6b255d06473418a38f1f1d2c6` | a source frame was recorded at the post-rival split boundary |

These are frame anchors only: they do **not** establish a continuous battle
trace, a save-state digest, or any Rust parity claim.  On 2026-07-30 the local
paths named by the frame manifest (`../../../pokeagent-speedrun/...`) and all
locally discoverable `.state`/`.gba` files were unavailable, so no additional
source frame or semantic value was fabricated.  The pending rows in
`manifest.json` consequently have no hashes.

## Capture procedure

Use source-local checkpoint states.  Creating small checkpoints is deliberate:
it makes an individual behaviour a short, reproducible VBlank tape rather than
a multi-thousand-frame story replay whose timing obscures the first mismatch.

1. Restore the exact PokeAgent checkout and confirm the ROM hash is
   `a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af`.
2. From `03_birch.state`, replay only far enough to save the Route 101
   `plea`, `starter_select`, and settled `zigzagoon_command` surfaces.  From
   `04_rival.state` (or the earliest already-authenticated source state that
   can reach it), save `rival_prompt` and settled `rival_command` surfaces.
   Keep these local user-owned states out of the repository.
3. Record each source state SHA-256, its initial RGB SHA-256, the mGBA JSONL
   identity response, and the visible milestone in a local capture log.  Put
   only those hashes/provenance values—not the state—into the resulting trace.
4. Copy the selected tape definition from `manifest.json` into a small JSON
   file with a concrete `program` (one held-button action and its VBlank count
   per segment).  Do not guess fixed timings for a text/printer boundary:
   first locate it interactively and save a checkpoint at the settled surface.
5. Record it with the independent runner below.  It records frame zero and
   every subsequent VBlank in raw RGB SHA-256 form, preserves the adapter's
   complete available `source_state` object, and records physical
   held/pressed/released edges.  It refuses to overwrite a trace.

```sh
python3 fixtures/source_tapes/battle_coverage_v1/capture_source_tape.py \
  --oracle-command "scripts/run_mgba_jsonl_oracle.sh /secure/emerald.gba /secure/rival-command.state" \
  --rom /secure/emerald.gba \
  --state /secure/rival-command.state \
  --tape /secure/rival-run-rejection.json \
  --snapshot-output /oracle-output/rival-command-next.state \
  --output fixtures/source_tapes/battle_coverage_v1/recorded/rival-run-rejection.json
```

The runner is source-only.  Its output has `comparison.kind = "source_only"`
and cannot raise a coverage row to pixel-valid Rust coverage by itself.  The
optional snapshot flag must use a launcher invocation with an explicitly
mounted output directory; it records only the resulting path/digest in JSON,
never state bytes.

## What must be captured

`manifest.json` turns the desired coverage into named, checkpoint-local tapes.
For every tape, include the whole transition/animation interval and at least
one settled VBlank after the listed observation.  The required semantic fields
are the entire `source_state` object emitted by the adapter; the current
adapter supplies map/player location, RNG, save-block/avatar/object hashes,
and selected OAM/OBJ bytes.  If a future adapter supplies battle fields, keep
them verbatim under `source_state` rather than reducing or translating them.

The modal and branch rows specifically cover:

- premature versus ready dialogue advancement and A-release edges;
- command and move cursor navigation, B cancellation, and held A behaviour;
- battle entry and return-to-field transitions;
- HP, PP, status/stat-stage changes, and the trainer RUN rejection;
- victory handoff, plus a real faint/white-out branch if it is reachable from
  a restored deterministic checkpoint.

Absence of a source row remains a coverage gap, not a passing result.
