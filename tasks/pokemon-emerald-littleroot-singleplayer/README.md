# Pokémon Emerald — Littleroot Town

This is the GameBench Rust-port lane for a pixel-identical reproduction of the
Pokémon Emerald opening map, beginning with Littleroot Town. It follows the
same shape as the existing Rogue and Craftax ports: a Rust gold library, JSON
scenario CLI, HTTP gold-service binary, deterministic frame hashes, and frozen
reference artifacts.

Implementation coverage is tracked in [PROGRESS.md](PROGRESS.md).

The authoritative visual target is the local mGBA/PokeAgent Emerald reference
at `../../../pokeagent-speedrun/Emerald-GBAdvance/rom.gba`. That ROM is an oracle,
not a runtime dependency: the finished Rust lane must render its own 240×160
RGB frames from locally represented map, sprite, palette, and timing data.

## Current scope

- Fixed 240×160 RGB framebuffer and SHA-256 frame fingerprinting.
- Seventy-three byte-identical mGBA oracle frames embedded in the Rust gold crate,
  covering title timing through the first Professor Birch-intro frame, staged
  checkpoint idles, all four bedroom movement directions at 16/32/48 frames,
  outdoor first-step movement, and the opening Pokédex navigation sequence.
- Frame-accurate input vocabulary and deterministic session state.
- Source-derived bounds and warp destinations for Little Root, both homes, and
  Professor Birch's Lab, with 16-frame walking cadence in the world model.
- Rust-native terrain composition paths for the exterior plus those five
  interiors, sourced from staged Porymap layouts and tilesets.
- Rust scenario CLI (`scenario`) and HTTP server (`emerald_gold`) matching the
  established GameBench gold-port entrypoints.
- Explicit reference-capture manifest format for frozen Littleroot input/frame
  traces.

The May-bedroom, Little Root, and Birch-exterior idle boundaries are
pixel-identical. Some exact action boundaries are decoded reference receipts,
not proof of continuous native rendering. Full-town completion still requires
continuous player/NPC animation timing, collision, fade timing, menus, scripts,
and source traces for every reachable view.

## Entry points

```bash
cd tasks/pokemon-emerald-littleroot-singleplayer
cargo run --manifest-path gold_rust/Cargo.toml --bin scenario
cargo run --manifest-path gold_rust/Cargo.toml --bin emerald_gold -- --port 8103
```

The committed continuous opening replay starts at the title screen, selects
May, and reaches the rival encounter without checkpoint injection. It expands
its compact repeat groups and verifies its expected terminal readout:

```bash
cargo run --manifest-path gold_rust/Cargo.toml --bin scenario < fixtures/gold/replays/title_to_met_rival_may.json
```

This is functional replay evidence, not a blanket pixel-parity claim: the
individual exact frame traces remain listed in the frame manifest, while the
continuous exterior compositor is still under active parity work.

## Coverage and validity dashboard

`scripts/emerald_coverage_dashboard.py` reports the scoped-route evidence
separately from implementation completeness. It inventories the eight exposed
checkpoints plus intermediate Oldale, Lab, battle, and handoff segments.
`source_differential` is granted only to an authenticated mGBA oracle report;
frozen frames are endpoints, and Rust transport/self-consistency is excluded
from source correctness. Missing fields are intentionally `UNKNOWN`.

```bash
python3 scripts/emerald_coverage_dashboard.py \
  --report /absolute/path/to/emerald-differential.json \
  --json-out /new/path/emerald-coverage.json
```

Future canonical tape metadata may be supplied with `--tape-spec`. Its
input-owner, transition, and outcome labels remain `UNKNOWN` until that spec
declares authenticated source execution; an unexecuted spec is reported as
`tape_spec_unexecuted`.

To execute every presently authenticated registry row and refresh both the
dashboard table and JSON in a new directory, use the coverage orchestrator.
It first loads each promoted savestate twice through the oracle and rejects an
identity/RGB/source-state mismatch. Pending capture rows and non-concrete battle
tape plans remain explicitly unexecuted.

```bash
python3 scripts/emerald_coverage_orchestrator.py \
  --rom /absolute/path/to/emerald.gba \
  --oracle-command "scripts/run_mgba_jsonl_oracle.sh /absolute/path/to/emerald.gba /absolute/path/to/bedroom.state" \
  --state bedroom_idle=/absolute/path/to/bedroom.state \
  --output-dir /new/path/emerald-coverage-run
```

`--dry-run` validates the plan and reports pending/executed counts without
starting an oracle. Source-only battle traces are counted as executed only when
their plan digest, savestate round-trip receipt, frame sequence, and trace
digest all validate; they do not become Rust differential correctness.

Replay the committed frozen frame corpus with full SHA-256 and pixel-diff
verification:

```bash
cargo run --manifest-path gold_rust/Cargo.toml --bin scenario -- --verify-manifest
```

This verifies every frame presently committed to the manifest; it does not
replace the remaining required captures for other reachable views.

## Differential mGBA oracle

The Netherite-style regression gate replays the same button tape through the
Rust service and a locked mGBA source, compares exact 240×160 RGB bytes after
every VBlank, and records a per-VBlank state/hash proof tape. It refuses a
different ROM, state, emulator image, adapter, initial frame, or zero-frame
comparison. The reviewed bedroom identity remains in
`fixtures/gold/oracle_manifest.json`; new runs resolve a named source boundary
through `fixtures/gold/oracle_registry.json`.

Adapter v8 also records bounded source-level observability on every VBlank:
player gender, three Littleroot story variables, selected story/system flags,
both script contexts, palette-fade status, active-task fingerprints, and main
and field callbacks. These are raw source facts, not inferred story labels.
The matching pret revision, linker-map digest, addresses, struct offsets, and
variable/flag derivations are pinned in
`fixtures/gold/emerald_source_observability.json`; the decoder source digest is
part of the emulator identity, so older evidence cannot silently validate
under this schema.

The ROM is user-supplied and must have SHA-256
`a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af`.
Run from this directory with Docker available:

```bash
cargo build --release --manifest-path gold_rust/Cargo.toml
python3 scripts/fuzz_emerald_differential.py \
  --mode both \
  --random-cases 16 \
  --steps 64 \
  --oracle-rom /absolute/path/to/emerald.gba \
  --oracle-state /absolute/path/to/02_starter.state \
  --oracle-checkpoint bedroom_idle \
  --oracle-command "scripts/run_mgba_jsonl_oracle.sh /absolute/path/to/emerald.gba /absolute/path/to/02_starter.state bedroom_idle" \
  --output /new/path/emerald-differential.json
```

Exit status 0 means every comparison was exact, 1 means the judge found a
behavior/pixel divergence, and 2 means the source identity or protocol failed.
Reports are write-once: the harness refuses to overwrite an existing result.

The bedroom is now a permanent regression gate.  A bedroom checkpoint run is
accepted only at `26/26` tapes, `1687/1687` compared VBlanks, `977/977` exact
state checks, and `21/21` transport contracts, with zero RGB or semantic
errors.  The wrapper enforces that contract:

```bash
scripts/run_emerald_fuzz_progress.sh
```

The next contiguous authenticated segment starts from that same `bedroom_idle`
identity and covers the Mays House 1F stair/arrival, downstairs interaction,
and house-exit transition.  Its mandatory and random tapes use the same exact
RGB/state/transport judge.  The segment is currently closed at `18/18` exact
tapes, `6384/6384` RGB VBlanks, `968/968` state checks, and `21/21` transport
contracts; the wrapper below remains the reproducible regression gate:

```bash
scripts/run_emerald_mays_house_progress.sh
```

That wrapper also runs `scripts/emerald_mays_house_gate.py`, which fails closed
if the authenticated `bedroom_idle`/`mays_house_exit` identity, mandatory/random
corpus, exact-count contract, or zero-error requirement changes.

The segment runner exits `1` on measured divergence and writes its report under
the external audit output directory.  It must not be used to weaken or replace
the frozen bedroom gate.

The next closed seam is Route 101's wild-battle entry handoff. It is frozen at
two authenticated tapes, `127/127` exact RGB VBlanks, `5/5` semantic checks,
and the scoped five-case transport contract:

```bash
scripts/run_emerald_route101_wild_gate.sh
```

This narrow gate reports only the 127-frame entry/command corpus. The
authenticated turn-2 through turn-6 idle/default rails are covered by the
dedicated differential reports under the local audit outputs; arbitrary random
battle tapes remain an explicitly open dynamic-controller lane and are not
counted as a pass by this gate.

The registry explicitly marks every source boundary without a locally verified
raw mGBA state as `capture_required`. Each row includes the deterministic
replay/capture handoff required to authenticate it. Selecting one before it is
registered fails closed, rather than treating a planned or unknown state as an
oracle.

To capture one after its authenticated predecessor and concrete VBlank tape
exist, use `scripts/capture_emerald_oracle_checkpoint.py`. It writes the raw
state only to an explicit path outside this repository, then proves that a
fresh mGBA adapter reload matches the original no-input continuation before it
can promote a `capture_required` row. The bedroom zero-input tape in
`fixtures/gold/oracle_capture_tapes/` is a verification fixture only; it does
not alter the bedroom receipt.

`route103_post_rival_south_exit` is the next rehabilitation boundary after the
continuous May-victory proof. Its existing snapshot receipt is audit evidence,
not a one-load proof, so it remains quarantined. The following **non-promoting**
command is the reproducible replay/receipt contract; it must write to a new,
existing external evidence directory. A later promotion requires a dedicated
one-load/zero-reload continuous field trace, not this round-trip capture.

```bash
EVIDENCE_DIR=/absolute/existing/evidence-dir
python3 scripts/capture_emerald_oracle_checkpoint.py \
  --from-checkpoint route103_rival_victory_field --verify-only \
  --rom '/Users/joshuapurtell/Downloads/Pokemon - Emerald Version (USA, Europe).gba' \
  --state /Users/joshuapurtell/Documents/Codex/2026-07-30/emerald-gamebench-audit/work/emerald_oracle/v8_route103_rival_victory_rehabilitation_20260730/terminal.state \
  --tape fixtures/source_tapes/battle_coverage_v1/concrete/route103_victory_to_south_exit_v8.json \
  --snapshot-output "$EVIDENCE_DIR/route103_post_rival_south_exit.state" \
  --trace-output "$EVIDENCE_DIR/route103_post_rival_south_exit.trace.json" \
  --receipt-output "$EVIDENCE_DIR/route103_post_rival_south_exit.receipt.json"
```

When their authenticated predecessors and concrete battle-tape programs are
available, the named capture outputs are deliberately outside the repository:

```bash
python3 scripts/capture_emerald_oracle_checkpoint.py \
  --from-checkpoint birch_lab_exterior \
  --promote-checkpoint route101_rescue \
  --tape /absolute/path/to/route101-rescue-concrete.json \
  --rom /absolute/path/to/emerald.gba \
  --state /absolute/path/to/03_birch.state \
  --snapshot-output /secure/oracle-states/route101_rescue.state

python3 scripts/capture_emerald_oracle_checkpoint.py \
  --from-checkpoint oldale_town \
  --promote-checkpoint route103_rival \
  --tape /absolute/path/to/route103-rival-concrete.json \
  --rom /absolute/path/to/emerald.gba \
  --state /absolute/path/to/oldale.state \
  --snapshot-output /secure/oracle-states/route103_rival.state
```

For a resumable capture, also write immutable evidence artifacts outside the
repository.  A receipt is valid only when its digest, the optional per-VBlank
trace digest, and the external raw state SHA-256 all agree:

```bash
python3 scripts/capture_emerald_oracle_checkpoint.py ... \
  --trace-output /secure/oracle-evidence/route101.trace.json \
  --receipt-output /secure/oracle-evidence/route101.receipt.json
python3 scripts/verify_emerald_capture_receipt.py \
  --receipt /secure/oracle-evidence/route101.receipt.json
```

The current verifier fails closed on v7 receipts because their per-VBlank
source-state schema predates v8 observability. To inspect a preserved v7
artifact without promoting it to current evidence, pass
`--allow-superseded-identity`; a successful integrity check is then labeled
`audit_only`. Coverage accounting always requires the current pinned v9
identity.

Battle memory is captured through a separate sidecar so the pinned v9 adapter
and image do not change. The launcher mounts the sidecar and its pret-derived
symbol manifest read-only into the exact v9 image; its canonical JSON binds the
ROM, raw state, image, script, and symbol-manifest hashes:

```bash
scripts/run_emerald_battle_memory_sidecar.sh \
  /absolute/path/to/emerald.gba \
  /absolute/path/to/starter_battle.state \
  > /secure/oracle-evidence/starter_battle.battle-memory.json
python3 scripts/verify_emerald_battle_memory_receipt.py \
  --receipt /secure/oracle-evidence/starter_battle.battle-memory.json \
  --state /absolute/path/to/starter_battle.state
python3 scripts/attach_emerald_battle_memory_receipt.py \
  --checkpoint starter_battle \
  --receipt /secure/oracle-evidence/starter_battle.battle-memory.json \
  --expect-battle-json '{"battlers_count":2}'
```

The sidecar emits raw `gBattleMons`, battler count/positions, controller
flags, turn-action phase, outcome, and battle-main pointer values. It does not
pretend those fields came from the adapter's `source_state`. Registry
attachment is allowed only after the receipt verifies and its state SHA-256
equals the authenticated checkpoint.

For causal battle evidence without savestate-boundary drift, use the continuous
runner. It loads once, never reloads during the tape, samples battle memory and
callbacks after every VBlank (including named markers), and writes exactly one
terminal snapshot:

```bash
scripts/run_emerald_continuous_battle_trace.sh \
  /absolute/path/to/emerald.gba \
  /absolute/path/to/starter_battle.state \
  /absolute/path/to/battle_tape.json \
  /secure/oracle-evidence/battle-terminal.state \
  > /secure/oracle-evidence/battle-trace.receipt.json
python3 scripts/verify_emerald_continuous_battle_trace.py \
  --receipt /secure/oracle-evidence/battle-trace.receipt.json \
  --input-state /absolute/path/to/starter_battle.state \
  --terminal-state /secure/oracle-evidence/battle-terminal.state \
  --tape /absolute/path/to/battle_tape.json
```

The verifier requires one core load, zero intermediate reloads, a contiguous
`0..N` VBlank sample sequence, `N+1` samples, and exact input, terminal, tape,
image, script, and symbol-manifest hashes.

`shared/opening_tape.py` contains a committed May replay which is useful only
as a candidate program.  Export a bounded interval (the known clock index is
123), replay it through the capture command, and use the trace/receipt—not the
candidate or its Rust endpoint—as evidence:

```bash
python3 scripts/export_emerald_opening_route.py \
  --start-index 123 --end-index 156 --coverage-segment new_home_clock_tv \
  --output /secure/oracle-evidence/clock-candidate.json
```

The current machine lacks those source states, so these commands intentionally
cannot be run or promoted yet.

For an opt-in, deterministic triage pass, ask the harness to delta-debug a
small number of failures.  It reloads the pinned source checkpoint for every
candidate, compares the selected property on every VBlank, and writes a
self-contained proof tape with the ROM/state/manifest/emulator identity.  It
never treats a missing source or an absent target as a pass:

```bash
EMERALD_FUZZ_MINIMIZE=pixel EMERALD_FUZZ_MINIMIZE_LIMIT=3 \
  scripts/run_emerald_fuzz_progress.sh
```

Use `EMERALD_FUZZ_MINIMIZE=semantic` to preserve the first semantic mismatch
instead.  Minimised proof JSON and the exact source/Rust PPM pair are written
under the run's `*-artifacts/minimized/` directory.  Surface attribution
(`field`, `menu_ui`, or `transition`) is evidence-based triage from available
readout/source metadata, not a substitute for source task debugging.

## Opt-in full-PPU failure receipts

Default JSONL traces remain compact. For a minimized failure, opt in to one
bounded external PPU receipt per proof with
`--capture-minimized-ppu-dir /secure/ppu-receipts`. The capture replays the
minimized prefix twice in the pinned v9 image and rejects it unless the fresh
replay has identical framebuffer and source semantics. It writes raw VRAM,
palette RAM, OAM, and the PPU IO backing image only below that external root.

To capture and inspect the authenticated starter-battle VBlank zero directly:

```bash
python3 scripts/capture_emerald_ppu_receipt.py \
  --checkpoint starter_battle \
  --rom /absolute/path/to/emerald.gba \
  --state /absolute/path/to/starter_battle.state \
  --output-dir /secure/ppu-receipts/starter-battle-vblank0
python3 scripts/verify_emerald_ppu_receipt.py \
  --receipt /secure/ppu-receipts/starter-battle-vblank0/receipt.json
cargo run --manifest-path gold_rust/Cargo.toml --bin ppu_receipt -- \
  /secure/ppu-receipts/starter-battle-vblank0/receipt.json \
  /secure/ppu-receipts/starter-battle-vblank0/recomposed.rgb \
  --layers-dir /secure/ppu-receipts/starter-battle-vblank0/layers
```

The receipt stores DISPCNT, BG control/scroll/affine registers, windows,
mosaic, blend registers, all palette RAM, contiguous BG/OBJ VRAM, OAM, hashes,
ROM/state/tape/checkpoint/registry/adapter provenance, and the exact
fresh-replay attestation. The diagnostic emits BG0–BG3, OBJ, window-mask, and
final PPMs from captured PPU state. It does not assert mGBA per-layer output:
mGBA exposes its final RGB surface only.

The HTTP service offers `/health`, `/info`, `POST /rollouts`,
`POST /rollouts/{id}/step`, `POST /rollouts/{id}/checkpoint`,
`POST /rollouts/{id}/restore`, `POST /rollouts/{id}/simulate`,
`GET /rollouts/{id}/readout`, and `GET /rollouts/{id}/frame`. Checkpoint
payloads are renderer-independent JSON state encoded as base64; restore redraws
the frame from Rust-owned state before a branch continues.
