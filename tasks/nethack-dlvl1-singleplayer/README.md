# NetHack dlvl-1 single-player

This is an **own Python + Rust symbolic emulator** of Main Dungeon level 1 for
GameBench.  It ends an episode on death, quit, truncation, or the first use of
the down stair.  It does not generate or simulate dlvl 2, branches, or the
rest of NetHack.

For the high-level done/partial/blocked view, see
[`IMPLEMENTATION_MAP.md`](IMPLEMENTATION_MAP.md).

NLE is a discrepancy oracle, not a runtime dependency or wrapper.  Gold code
does not import `nle`, call a NetHack binary, open a PTY, or delegate actions to
an emulator.  When an NLE development environment is available,
`scripts/capture_nle_fixture.py` freezes level dumps, action tapes, and
observation snapshots.  Both gold lanes then replay those files without NLE.

The canonical gate is `scripts/judge_nle_tapes.py`. It validates each tape's
byte-locked manifest, replays each lane twice, rejects nondeterminism, and
compares lifecycle, messages, mechanics, screen planes, and the composed 24×80
terminal UI as separate exact layers. It fails when the corpus, input count, or
any required comparison layer is empty.

The current dynamic-entity promotion is intentionally narrow: with a
reset-bound authoritative entity projection, the first consumed `SEARCH`,
`WAIT`, or `TAKEOFF` retains the exact reset presentation pixels. Native held-out evidence
backs this first-turn hold; later scheduling, pathing, collision, and combat
remain separate frontiers.

Reset captures may also include the complete source floor-object stacks and
tame-monster inventories. A source-shaped kitten scheduler candidate consumes
those reset inputs, but remains fail-closed: unexplained `obj_resists` RNG
draws in the pinned navigation trace currently block public pet movement
promotion.

Re-run its source-only validity check with:

```bash
.venv/bin/python scripts/verify_first_turn_stationary_entities.py \
  --cases 20 --seed 20260725 --report /tmp/nethack-first-turn-stationary.json
```

Live captures also carry an optional reset-only topology projection.  It is
the pinned native `rm.typ`/`rm.flags`/`rm.horizontal` 21×79 map, sanitized to
JSON with source/binary identity and a digest.  Both gold lanes validate and
checkpoint it privately. When the complete reset static-light extension is
present, it also drives the narrow source-shaped static `COULD_SEE` reveal
path; it does not hydrate the reset screen or future dynamic FOV. Pathing and
full visibility consumers remain blocked until their own held-out transition
evidence promotes them.

## Contract

- The public wire action is the integer index in pinned `nle.nethack.ACTIONS`.
  See [`shared/nle_action_map.md`](shared/nle_action_map.md).
- All actions in that table are accepted, including command, Meta/control, and
  prompt-text actions.  The engine publishes an explicit mode stack:
  `normal`, `direction`, `inventory_letter`, `ynq`, `menu`, `string`, or `more`.
- Fixtures provide the authoritative dlvl-1 `level_dump`; open-play seeds use
  gold's own deterministic mixer and make no same-seed NLE generation claim.
- Observations expose a fixed 21×79 `chars`/`colors`/`glyphs` projection,
  27-slot NLE `blstats` (including condition and alignment), normalized message plus raw bytes, inventory arrays, and
  terminal state.
- `>` performed while standing on the captured down-stair emits
  `stairs_descend` and `terminal(descended)`.  No post-descend NLE map is read.
  Capture refuses an unproven `DOWN`: it needs an earlier raw `>` observation
  at the hero coordinate, freezes that pre-action projection, and never steps
  NLE into dlvl 2.  Promotion rechecks that proof and every raw snapshot's Main
  Dungeon dlvl-1 identity.

## Layout

```text
gold_python/     Python FastAPI lane and scenario runner
gold_rust/       Rust Axum lane and JSON-stdin scenario runner
shared/          wire contract, action map, resolver, NEV vocabulary
fixtures/gold/   owned GameBench scenarios / expected projections
fixtures/nle_oracle/
                 frozen NLE captures; no NLE installation needed to replay them
scripts/         capture, discrepancy, parity, fixture, service, policy tools
reports/         dated judge/drift evidence and severity assessment
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

## Canonical NLE capture workflow

Capture always stages **outside** this task; it cannot write directly into the
canonical corpus.  A staged capture retains the initial NLE blstats, message
buffer, inventory arrays, unseen planes, and initial visibility mask.  Static
terrain/glyph/color cells are hydrated only when the same NLE tape later
observes them.  Gold owns later FOW refreshes from hero/terrain state and its
own LOS rule; a fixture may not encode an action-indexed future-visibility
schedule.  Gold never calls NLE while replaying a fixture.

Visible dynamic glyphs must be represented by owned `objects`, `monsters`, or
`traps` annotations rather than left in terrain.  A `terrain_underlay` entry
may fill only a visible dynamic reset cell and must use static values supported
by NLE evidence.  Annotations cannot replace raw planes or reset metadata.

```bash
.venv/bin/python scripts/capture_nle_fixture.py \
  --fixture-id val-east-seed-20260725 \
  --actions /tmp/val-east.jsonl \
  --seed 20260725 \
  --output /tmp/val-east-seed-20260725

.venv-properties/bin/python scripts/promote_nle_fixture.py \
  --source /tmp/val-east-seed-20260725 \
  --fixture-id val-east-seed-20260725
```

Promotion refuses an existing destination and requires strict Python and Rust
replay to be green first.  It also validates the pinned action table, schema,
contiguous step-zero snapshots, and rejects diagnostic-fuzz artifacts or
future-visibility schedules.  It copies only `meta.json`, `level_dump.json`,
`actions.jsonl`, `snapshots.jsonl`, and the byte-locked `tape_manifest.json`.
New captures fingerprint the Python executable, platform, installed NLE binary
files, distribution RECORD, capture script, and the pinned NLE source artifact.
Every manifest chains the exact input record to pre- and post-turn state hashes.

Run the harsh frozen-oracle gate and save machine-readable evidence:

```bash
python scripts/judge_nle_tapes.py --lane both --report reports/oracle_judge.json
```

Historical captures predate binary fingerprinting. Their manifests say
`legacy_version_only` explicitly; their raw bytes and known version/action
identity are locked, but the missing historical binary identity is not
retroactively invented. New promotion requires the exact runtime fingerprint.

## Live NLE differential fuzzing

The optional fuzzer gives live NLE and both own lanes the exact same
pinned action IDs from the same capture-backed reset.  It compares every
captured public plane—characters, glyphs, colors, raw messages, blstats, and
inventory—at reset and after every action. It is a diagnostic oracle tool: it
never imports NLE from gold code and it does not write candidate captures into
the checked-in corpus automatically.

On this macOS host, use CPython 3.10 for NLE 0.9.0.  Its bundled bindings do
not build on CPython 3.11, and CMake 4 needs the policy compatibility setting
during the NLE build:

```bash
uv venv --python 3.10 .venv
CMAKE_POLICY_VERSION_MINIMUM=3.5 uv pip install --python .venv/bin/python -r requirements-nle-fuzz.txt
.venv/bin/python scripts/fuzz_nle_differential.py --cases 10 --steps 32 --seed 20260725 --lane rust --output /tmp/nethack-nle-fuzz
```

Use `--lane both` to include the independent Python trace lane. Strict reset
and transition comparison is the default; `--mask-baseline` is an explicit
diagnostic-only escape hatch for isolating later transitions. The output directory holds
reproducible, capture-shaped cases and structured discrepancy reports; inspect
or replay it without copying artifacts under `fixtures/nle_oracle/`:

```bash
python scripts/compare_nle_discrepancies.py --root /tmp/nethack-nle-fuzz --lane both
```

The default `navigation-v0` campaign generates visible navigation and explicit
`MORE` inputs.  `prompt-probe-v0` adds a bounded safe command family, resolves
direction and `MORE` prompts, and uses `ESC` to recover other raw prompts.
PICKUP is excluded because the reset hero occludes the required terrain and
floor stack; it has a separate known-underlay verifier:

```bash
.venv/bin/python scripts/fuzz_nle_differential.py --cases 25 --steps 32 --seed 20260725 --lane rust --campaign prompt-probe-v0 --output /tmp/nethack-nle-prompt-probe
.venv/bin/python scripts/verify_known_underlay_pickup.py --report reports/known_underlay_pickup.json
```

`terminal-probe-v0` performs an isolated QUIT/yes sequence so the primary
terminal observation and exact score-screen TTY contract are exercised
without crossing beyond dlvl 1:

```bash
bash scripts/run_fuzz_progress.sh 3 4 terminal-probe-v0
```

Pass `--actions <jsonl>` to replay arbitrary pinned action IDs.  A `DOWN`
without earlier raw `>` evidence at the hero coordinate is rejected before NLE
can cross the geography boundary; a proven descent is emitted as a terminal
pre-dlvl-2 boundary.  Risky host/episode-escaping commands remain for explicit
tapes rather than generated campaigns.

Every run writes `coverage.json` beside `run.json`.  It separates selected
action IDs from action IDs actually stepped in NLE (a protected pre-dlvl-2
descent is selected but intentionally not stepped), then records `(action,
inferred-input-mode)` contexts, action families, inferred prompt modes,
terminal reasons, observed public-plane/blstats deltas, lane discrepancy
signatures, and a per-case novelty hash.  These are diagnostic coverage
measurements, not a conformance percentage.

For an Emerald-style progress table with case failures, exact-prefix score,
pixel/state error counts, and the first actionable errors, run:

```bash
bash scripts/run_fuzz_progress.sh 25 64 prompt-probe-v0
```

The runner first requires the frozen tape contract to pass, then reports the
live source comparison, a separate `source_state_eligibility` lane, prompt
mode, turn consumption, exact terminal UI, seeded observable action outcomes,
visibility/entity transitions, NLE `specials`, terminal boundaries, NLE
repeatability, held-out reset state, and checkpoint continuation.
`source_behavior_oracle` and
`heldout_state_oracle` scores use only source-eligible action transitions
before each case's first divergence; `unjudgeable_turns` is shown separately
and never enters that denominator. A source-unknown campaign reports
`partial_unjudgeable`, never `pass` or `divergences_found` for its unknown
actions. The JSON field name is retained for compatibility: for the
visibility/entity and specials lanes its value counts source-unknown surface
records/cells, not whole turns. Prompt probing deliberately excludes `PICKUP`, so its generated
action family is fully source-eligible; pickup evidence remains in the
separate known-underlay campaign. Other scores are the percentage of compared
steps without an error. `pixel_errors` and
`state_errors` are distinct leaf mismatches at the first divergent step,
deduplicated across the Python and Rust lanes; later states are not counted
because they are causally contaminated.

Two narrow live evidence commands cover state that the broad prompt campaign
must not guess:

```bash
.venv/bin/python scripts/verify_entity_overlay_restoration.py \
  --run /path/to/fuzz/run.json \
  --report reports/entity_overlay_restoration.json
.venv/bin/python scripts/verify_visible_target_kick.py \
  --report reports/visible_target_kick.json
.venv/bin/python scripts/verify_dynamic_pet_presentation.py \
  --report reports/dynamic_pet_presentation.json
.venv/bin/python scripts/verify_visible_target_combat.py \
  --report reports/visible_target_combat.json
.venv/bin/python scripts/verify_authoritative_rng_state.py \
  --report reports/authoritative_rng.json
.venv/bin/python scripts/verify_reset_wall_kick_blocker.py \
  --cases 20 --seed 20260725 \
  --report reports/reset_wall_kick_blocker.json
.venv/bin/python scripts/audit_nle_map_fov_contract.py \
  --report reports/authoritative_map_fov_native.json
.venv/bin/python scripts/verify_nle_native_entities.py \
  --report reports/native_entities.json
.venv/bin/python scripts/verify_native_scheduler.py \
  --report reports/native_scheduler.json
.venv/bin/python scripts/verify_native_path_state.py \
  --report reports/native_path_state.json
.venv/bin/python scripts/verify_native_map_fov_transitions.py \
  --report reports/native_map_fov_transitions.json
.venv/bin/python scripts/verify_native_algorithm_c_fov.py \
  --report reports/native_algorithm_c_fov.json
```

Any proposed native-assisted gold rule must also pass
`scripts/frontier_promotion_gate.py`. The gate requires positive source and
held-out comparison counts, exact replay, anti-leakage and seed/coordinate
independence, Python/Rust parity, zero held-out counterexamples, and no
first-divergence or total-error regression. A lower aggregate error count
cannot compensate for an earlier first error.

The restoration verifier asserts only directly visible static terrain after a
presentation-continuity glyph vacates a cell; it never claims entity identity.
The kick verifier classifies only raw-visible target surfaces and requires
fresh same-seed NLE runs to reproduce exact prompt and observable outcome
deltas. Its exact static-wall message assertion is eligible only for an
immediate reset-time KICK with no prior consumed action; variable injury and
stat loss remain unjudgeable because `exercise()` also mutates hidden
`aexe`/`atime` state and attribute-check timing is not a public plane. The
`verify_reset_wall_kick_blocker.py` report captures those reset/post-action
fields and independent replay, but is intentionally `source_pass_gold_blocked`.
On the pinned macOS wheel, the authoritative RNG
verifier additionally resolves the exact copied `libnethack` Mach-O state
using verified symbol layout and binary identity. It is read-only and records
the exact 4,128-byte pre/post-action ISAAC64 states and recovers exact call
counts by replaying a private state clone through the pinned binary;
it does not by itself
authorize a gold RNG because draw-to-branch and dynamic-actor chronology are
separate contracts. The pet verifier proves only the stationary WAIT/SEARCH
presentation hold. The combat verifier proves exact public
FIGHT-direction/direct-movement equivalence while rejecting implementation
without causal destination, combat-branch, and actor/RNG call chronology.

Future live captures additionally write `native_pre_action_evidence.jsonl`.
Each record is bound to its exact action, runtime, oracle identity, native
binary, and source-state digest and contains separate raw terrain/door-state/
FOV/memory, entity/underlay/target/path state, player combat/KICK state, and
raw RNG planes captured before the action. Validation
fails closed on absent, empty, reordered, tampered, future-boundary, or
binary-mismatched evidence, including malformed content whose outer hashes
were recomputed. This sidecar is source evidence only: it is never read by the
gold engines, never hydrates a `level_dump`, and never contributes to the
conformance denominator.

New v2 captures also write `native_reset_entity_state.json` and embed its
sanitized `authoritative_reset_entities.v1` projection in `level_dump`. The
projection is task data: stable entities, complete occupied-cell underlays,
movement points, queue order, target/path/status state, tame `edog` state, and
the player reset position/time. Gold may consume only this projection. The
native receipt is a single copy made immediately after `reset()` and before
action one; it attests the projection plus oracle/runtime/binary identity,
exact reset public projection, final level dump, and full action tape. It
deliberately omits raw ISAAC64 state because that state has no portable gold RNG
contract. The validator rejects future/pre-action-sidecar references, changed
level dumps or action tapes, turn-boundary mismatch, and recomputed-hash
tampering. Historical v1 tapes remain replayable but are explicitly ineligible
for this reset scheduler-source contract; the native receipt itself is never a
gold/checkpoint input.

The fuzzer also has a separate diagnostic `prior_source_static_replay_v1`
lane. It imports only glyph-classified static cmap cells from the immediately
preceding NLE frame, fills unknown memory only, and rejects overlays, hero
underlay, malformed cells, duplicates, and conflicts. This lane is useful for
measuring missing map state but is never included in gold conformance scores:
prior observations cannot authorize predictions of newly revealed geometry.

The public gold observation now derives `MG_PET` only from a visible,
source-pinned pet marker. The progress row scores positive pet semantics
separately from its millions of zero-cell negative controls; corpse, statue,
object-pile, and unmaterialized dynamic-pet cells are explicitly
`partially_unjudgeable`. Reset presentation markers survive zero-turn prompts;
the source-proven stationary WAIT/SEARCH hold retains the exact pixel once,
then expires on the next consumed turn so a sampled screen cannot become an
invented entity schedule. A `not_exercised` terminal row means the generated
inputs never reached a terminal boundary, not that terminal behavior is
correct.

The fuzzer labels bootstrap-masked transition results as diagnostics, not as
canonical conformance passes or contributions to the required 33 tapes.

## Property invariants

`requirements-property-tests.txt` pins the optional Hypothesis dependency for
the task-local Python/Rust integrity suite.  It covers constrained dlvl-1 lab
fixtures, action-adapter equivalence, observation shapes, determinism,
checkpoint continuation, and short cross-lane traces.  It does not make an NLE
fidelity claim; frozen strict NLE replay remains the parity authority.

```bash
uv venv --python 3.10 .venv-properties
uv pip install --python .venv-properties/bin/python -r requirements-property-tests.txt
.venv-properties/bin/python -m unittest discover -s tests -p 'test_*.py'
```

## Corpus growth

The required 33 authentic NLE tapes are the v0 **minimum**, not a cap.  Keep
them as strict-green, hand-reviewed canonical regressions.  Grow a separate
focused regression corpus (target 60–100+ tapes) from minimized novel behavior
signatures, and retain large live-fuzz campaigns only as out-of-tree diagnostic
artifacts until a candidate is deterministic, dlvl-1-only, fully annotated from
NLE observations, and strict-green in both lanes.

## Current status

The checked-in implementation establishes the dual-lane engine, full action
acceptance, fixed-crop observation contract, deterministic checkpoint/restore,
source-gated reset safepet displacement, and capture/discrepancy plumbing.
The canonical corpus is now **31 / 33
(93.9%)** required v0 tapes.  Every promoted tape is strict-green in both own
lanes: chars, glyph IDs, colors, raw messages, blstats, and inventory must all
match NLE at every recorded action.  That is a pixel-faithful evidence claim
for these tapes, not a general parity claim. Full dynamic FOV, dynamic entities
beyond the bounded safepet branch,
hidden terrain under the hero, combat/RNG, traps/death, and descent still need
authoritative source-state contracts and authentic strict-green evidence; see
[`PROGRESS.md`](PROGRESS.md).

The latest validity wave adds a narrow promoted static-FOV rule plus source-only
exact branch evidence. The source-shaped NetHack Algorithm C `COULD_SEE`
geometry, reset static-light/night-vision gate, and one-sided wall/closed-door
lighting are now used by both gold lanes when the complete reset map extension
is present. Six independent native reset seeds produce 9,954 public-cell
comparisons with zero mismatches. This is deliberately not full source-backed
`IN_SIGHT`: mobile/temporary light, xray/blindness, dynamic boulder/mimic
blockers, and historical memory remain unpromoted on the native reset path.
The generic authored-level runtime now has bounded temporary light, xray, and
blindness lifecycle rules; those do not upgrade the native reset claim. The same wave adds reproducible KICK RNG
callsite tracing, untouched-wheel LLDB `mfndpos` candidate tracing, and a
compiled/semantic native vision-input contract. All are equivalence- and
replay-gated and excluded from gold/scoring. No destination, combat, or
injury-RNG behavior was promoted; live navigation remains red on dynamic actor
and message chronology even after the static FOV improvement.

The reset-owned scheduler boundary is now preserved in both gold lanes for
checkpoint inspection. Its portable ISAAC context and ordered entity state are
not advanced during gameplay: native RNG chronology is interleaved with
`distfleeck`, `dog_move`, and post-turn calls, and a one-draw-per-action model
would be an invalid shortcut. The diagnostic descent route therefore remains
blocked on a held-out destination/underlay rule rather than being promoted from
future sidecar evidence.

The offline scheduler candidate also preserves the source `movemon` ordering:
repeated queue passes debit one `NORMAL_SPEED` per eligible entity, then the
candidate allocates the next turn's movement budget. This is audit/checkpoint
evidence only; no destination, collision, or live RNG behavior is inferred.

The exact-wheel `dog_move` verifier now binds each return event to the unique
pre-action entity and hero scheduler snapshot (14 joined events across three
independent seeds, exact replay). The held-out eight-seed scheduler probe also
records hero movement points at every action boundary. These receipts improve
causal validity but remain source-only until a general destination/collision
contract passes the promotion gate.

The source-only LLDB `mcalcmove` trace now records the allocation return at
the actual native boundary (106 events across eight held-out seeds, exact
replay). This resolves action-boundary scheduler ambiguity but does not grant
destination, collision, or pet-AI behavior to either gold lane.

The bounded player/safepet branch is now source-validated as well. In pinned
`hack.c`, `attack()` consumes a core `rn2(7)` before deciding whether an
adjacent tame pet blocks movement or swaps into the hero's previous cell. A
20-seed native gate replays the reset-bound ISAAC64 core state with zero branch,
position, and repeatability errors (`/tmp/safe-pet-displacement-20260802.json`).
Both gold lanes implement that branch only at the first post-reset movement
boundary, and only when reset identity, the exact pet presentation marker,
and the portable reset RNG are all present; the staged
positive case is strict-green in both lanes (`/tmp/judge-safe-pet-staged-20260802.json`).
This does not promote later pet scheduling, pathing, traps, or combat RNG.
