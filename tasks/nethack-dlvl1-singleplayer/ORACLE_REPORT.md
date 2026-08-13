# NetHack judge-first fidelity report — 2026-07-30

## Verdict

The 15 frozen canonical tapes pass exact deterministic replay in both own
lanes. This is narrow evidence, not general NetHack fidelity. A fresh live-NLE
navigation campaign diverges in every case and establishes a **P1 fidelity
gap** in ordinary movement/visibility/entity projection.

## Source-state scoring contract

The live progress report now has an assertion-first source-state boundary.
Every action requirement is tagged `reset-observed`, `prior-turn-observed`,
`capture-annotation`, or `unknown`. An action needing unknown source state,
and its causal suffix, is `unjudgeable`: it is neither an equal/diverged trace
result nor part of the exact-prefix denominator. The progress table records
that count as `unjudgeable_turns` and emits `partial_unjudgeable` rather than
`pass` when no eligible transition diverged.

This is enforced fail-closed: Python and Rust must report identical eligible
and unjudgeable counts, and malformed/future provenance rejects the report.
`prompt-probe-v0` excludes `PICKUP` and is therefore fully source-eligible by
construction. Pickup remains separately evidenced by the known-underlay
multi-seed verifier and the two frozen pickup tapes; a later screen reveal is
not retroactively eligible evidence for an earlier pickup action.

## Reproduction evidence

Live oracle command (NLE 0.9.0 / NetHack 3.6.6, CPython 3.10):

```bash
python scripts/fuzz_nle_differential.py \
  --cases 10 --steps 32 --seed 20260725 --lane both \
  --output /tmp/nethack-live-drift-20260730
```

Observed result:

- process exit: nonzero; `status: diverged`
- 10 cases, 320 selected inputs, 9 distinct action IDs
- 20 / 20 lane transition results diverged
- first divergence occurred at step 1 in 5 cases, step 2 in 4 cases, and
  step 3 in 1 case
- all first divergences were exact `chars[y][x]` terminal-map cell mismatches
- representative case 0, step 1 east: oracle space, gold `#`
- representative case 1, step 3 northeast: oracle `f`, gold `<`

This is consistent with the existing open room/corridor visibility and moving
entity backlog. The follow-up fix round removed future-tape terrain hydration
from the live reset, recovered only oracle-proven static terrain beneath the
reset hero, and added one evidence-backed corridor rule: from room floor, an
unseen corridor cell is not revealed beyond Chebyshev distance 1. Two
nonlocal floor discoveries remain unexplained and were not special-cased.

The extended progress runner was then exercised on 10 cases × 32 requested
inputs for both `navigation-v0` and `prompt-probe-v0`. The prompt-probe report
is
`nethack-progress-20260730-111300-90309.json` in the out-of-tree audit output
directory. It found:

- source exact-prefix fidelity: 42 / 320 transitions (13.1%)
- prompt-mode comparisons: 62 / 62 error-free through first divergence
- turn-consumption comparisons: 52 / 52 error-free through first divergence
- terminal UI: 10 / 10 cases failed, with 1,270 exact character/color cell
  mismatches across the compared prefix
- NLE repeatability: 330 / 330 snapshots matched on a fresh replay
- held-out reset state: the same 13.1% prefix fidelity, showing the result does
  not depend on hydrating the gold task from future oracle snapshots
- checkpoint continuation: 10 / 10 cases failed because Rust restored
  `inventory.items[0].oclass` as `2` while uninterrupted execution retained
  `41`
- terminal boundaries: zero comparisons, explicitly `not_exercised`
- NLE `specials`: nonzero cells were present in every case, while the current
  gold public contract has no corresponding plane

## Fix-round results

After minimizing the first errors, the following safe changes were made in
both own lanes:

- canonical inventory `oclass` now survives Python-to-Rust checkpoints
- `INVENTORY` is an exact persistent zero-turn display, including 24×80
  layout, colors, row clearing, cursor, ignored keys, and ESC dismissal
- `APPLY` emits NLE's exact applicable-tool prompt
- `QUIT` emits NLE's exact prompt and its confirmed terminal primary
  observation plus score-screen TTY; the concrete `quit` cause remains private
- the live task reset is causal rather than hydrated from future tape frames
- the narrow room-to-corridor visibility rule above replaces nine observed
  false-positive corridor reveals

The user-scale `prompt-probe-v0` run (25 cases × 64 inputs) produced
`nethack-progress-20260730-113452-63747.json`:

- exact-prefix fidelity increased from 6.7% to 8.8%, despite the stricter
  causal reset
- checkpoint continuation increased from 50% to 100%
- prompt-mode, turn-consumption, and NLE-repeatability checks remained 100%
- no first error is now `INVENTORY` or `APPLY`
- remaining first errors are fixed-stair pickup, kick/stat RNG, moving
  entities, and visibility/object projection

The explicit `terminal-probe-v0` run (3 cases × 2 inputs) produced
`nethack-progress-20260730-113653-69347.json`. Source behavior, prompt mode,
turn consumption, exact terminal UI, terminal boundary, NLE repeatability,
held-out state, and checkpoint continuation all pass at 100%. Only the
deliberately unsupported `specials` plane remains non-green.

The causal `navigation-v0` run (10 cases × 32 inputs) produced
`nethack-progress-20260730-113619-67908.json`: first errors occur at step 1 in
4 cases, step 2 in 5, and step 3 in 1. The unexplained errors remain exact map
cells rather than verifier bootstrap leakage.

## Assertion-first swarm round

The next Terra swarm added fail-closed source eligibility, seeded observable
outcome assertions, and layered visibility/entity transition assertions
before attempting more simulation fixes. The fresh user-scale
`prompt-probe-v0` report is
`nethack-progress-20260730-120436-53133.json`:

- source eligibility: 1,600 / 1,600 turns (100%), with zero unjudgeable turns
- exact-prefix source fidelity: 15.8%
- prompt mode and turn consumption: 99.3% each; the remaining two cases are
  pet-attack confirmation
- seeded KICK/FIGHT outcome fidelity: 7 / 26 comparisons (26.9%)
- visibility/entity transition fidelity: 39.1%
- NLE repeatability and checkpoint continuation: 100%
- `specials` remains explicitly unsupported, and terminal boundaries were not
  exercised by this campaign

Three bounded live probes add evidence outside that aggregate score:

- known-underlay pickup: 5 / 5 independent seeds exactly reproduce the fixed
  stair message and turn sequence
- visible entity-overlay restoration: 24 distinct source cases directly show
  static terrain restored after a presentation glyph vacates a visible cell
- visible-target KICK: 37 repeatable cases over 16 seeds (16 floor, 7 wall,
  4 door, 10 visible overlays)

At that stage only the multi-seed stable wall message, raw
`Ouch!  That hurts!`, was added to both gold lanes. Seed-dependent injury/stat
loss, overlay identity, and entity scheduling were not fabricated; the later
round added only source-pinned immediate pet confirmation.

## Validity-first Terra swarm round

The next swarm corrected semantic contamination before optimizing fidelity:

- reset characters are classified with pinned NLE glyph predicates, not
  `char.isalpha`; the hero is explicitly excluded, a `d` statue remains a
  statue presentation, and an object rendered as `+` remains an object
- reset entities/objects are inert `presentation_overlays`, with exact pixel
  provenance and no collision, combat, pickup, identity, or scheduling fields
- reset overlays and pet interaction markers survive zero-turn prompts; the
  source-proven stationary WAIT/SEARCH hold retains the exact pet pixel once,
  then expires on the next consumed turn. Hidden underlays are reported as
  source-unknown rather than FOV failures
- pet markers require `glyph_is_pet`/`MG_PET` and
  `glyph_to_mon -> permonst.mname`; they support only immediate KICK
  confirmation and never enter the monster scheduler
- `specials` is now a strict frozen-judge layer. Gold causally derives
  `MG_PET`; corpse/statue/object-pile and unmaterialized dynamic-pet cells fail
  closed as unjudgeable

Independent evidence includes 59 repeatable pet-action cases, a four-seed
two-ESC pet-cancel probe, and a 25-seed specials audit with source values
`{0: 41443, 8: 25, 32: 1, 65: 6}` and zero glyph-predicate contradictions.

The fresh 25×64 prompt report is
`nethack-progress-20260730-123705-82973.json`:

- source eligibility and NLE repeatability: 100%
- core exact-prefix fidelity: 15.8%
- prompt mode and turn consumption: 99.3%
- terminal UI: 47.9%; reset-only overlay expiry exposes the honest dynamic
  entity/underlay gap instead of freezing source pixels
- causal positive `MG_PET` coverage: 48.2%, with 230 cells explicitly
  unjudgeable and zero specials errors
- visibility/entity transitions: 44.9%, with 2,176 source-unknown surface
  records quarantined
- checkpoint continuation: 100%

The frozen judge now passes 12 fixtures / 23 inputs / 420 exact layer
comparisons. No dynamic schedule, hidden underlay, unsupported special bit,
or injury RNG was inferred to improve these numbers.

## Scheduler, FOV, combat, and RNG validity frontier

The dependency-ordered Terra wave first probed scheduling and underlay/FOV,
then allowed combat and KICK work only after those contracts were evaluated.

- Dynamic pet evidence covered 24 independent seeds, WAIT and SEARCH, five
  turns, and exact repeated replay. The initial stationary consumed turn was
  exact in 48/48 cases. Later evidence contained 114 movement candidates over
  21 seeds and 16 distinct displacements, including two-cell moves plus
  item/combat effects. Both gold lanes therefore implement only the one-shot
  source-marked initial stationary presentation hold.
- A diagnostic prior-source static replay imported 148 previously observed
  cmap cells without conflicts and reduced navigation visibility errors from
  11,963 to 8,250. It did not move first divergence and cannot predict fresh
  reveals. A subsequent pinned-native reader exported exact true terrain,
  `IN_SIGHT`/`COULD_SEE`, map-memory glyphs, and `seenv`. Its six-lane held-out
  bootstrap reduced aggregate visibility errors from 2,080 to 1,778 but
  regressed first divergence to step 1 in every lane, so the promotion gate
  rejected it. Both lanes are excluded from conformance.
- Five independent adjacent non-pet monster cases exactly repeated and showed
  FIGHT followed by direction has the same public result as direct movement
  attack. Native sidecars now expose the missing entity and RNG source state,
  but all five remain implementation-ineligible because destination/combat
  branch logic and actor/RNG call chronology have not been causally mapped.
- Direct reset-time wall KICK produced seven exact static-wall cases. In 7/7
  same-seed controls, a preceding WAIT changed the full KICK result. NLE
  `get_seeds()` remained unchanged through reset, SEARCH, prompt, and result,
  proving it is configuration evidence rather than advancing PRNG state. The
  exact wall message is consequently restricted to the immediate
  source-observed reset state; injury/stat deltas remain unjudgeable.
- A subsequent pinned-native audit moved the RNG blocker one layer deeper.
  The exact copied macOS `libnethack` binary retains a local `rnglist` symbol;
  a read-only reader verifies its binary hash, Mach-O slide, C layout, function
  pointers, and both ISAAC64 indices before copying state. Eight independent
  twice-replayed SEARCH cases used 4–9 core draws and zero display draws;
  seven reset-wall KICK results used 9–15 core draws. Capture itself was
  non-mutating. Gold RNG remains ineligible until those draws are causally
  assigned to KICK/combat branches and dynamic-actor scheduling.

The validity guards also require equal Python/Rust denominators and reject
future-frame terrain, inferred entity identity, coordinate/seed schedules,
masked overlays, and zero-comparison passes.

An additional all-public-surface audit inspected all 17 documented NLE 0.9.0
observation buffers (including the opt-in `internal`, `program_state`,
`screen_descriptions`, and `misc` fields), the public high-level environment,
and the public raw wrapper. Six held-out seeds were each reset twice with
byte-exact public observations. The public capability gate correctly rejected
every run. A separate exact-hash, ABI-checked native source exporter now
provides stable monster IDs, species, allegiance, HP, movement points/speed,
iteration order, terrain underlays, complete floor-object stacks, `mux/muy`,
four-cell `mtrack`, strategy/status, and tame `edog` state. A six-seed mixed
SEARCH/WAIT/E lane produced 119 exact entity transitions: 52 moves, 67
stationary events, 16 directly rendered static underlay restorations, and
seven concrete ready-but-stationary counterexamples. A separate twice-replayed
path-state audit made 40 positive comparisons. This is eligible for source
assertions only: candidate sets, `mfndpos` flags, complete collision/player
inputs, combat outcomes, and RNG branch ownership remain incomplete.

All new live captures also write an action-bound pre-action sidecar containing
raw terrain type, door flags/orientation, FOV/memory, entity/path/underlay,
player combat/KICK state, and exact raw core/display ISAAC64 states. Player
evidence includes the full pinned `dokick.c` martial predicate, rather than
role alone. Missing, zero, reordered, tampered, future-boundary,
binary-mismatched, or semantically malformed recomputed-hash evidence fails
closed. Sidecars are explicitly prohibited from gold input, level-dump
hydration, and conformance denominators. The 12 historical fixtures remain
judgeable and are truthfully labeled `legacy_no_native_pre_action_evidence`.

New v2 captures also carry `native_reset_entity_state.json` and place its
sanitized `authoritative_reset_entities.v1` projection in the task level dump.
That portable projection supplies stable entity IDs, source-complete underlays,
movement points/queue order, target/path/status and tame state, plus the player
reset position/time; it is the only entity reset source gold may consume. The
separate native receipt is bound to the exact projection, level dump, action
tape, pinned oracle/runtime/binary identity, and its own state hash. It
contains no raw RNG state because portability has not been proved. The
validator rejects future or pre-action-sidecar references even if all outer
hashes are recomputed. The receipt itself does not hydrate gold, checkpoints,
or conformance. Older v1 fixtures remain judgeable but cannot satisfy the new
reset scheduler-source eligibility gate.

The massive causal swarm promoted no new gold behavior. That is the valid
result:

- Full-state RNG replay proves exact whole-boundary call counts, but KICK,
  combat, pet AI, and the scheduler contain conditional calls whose ownership
  is not identified by a total.
- `struct rm.typ` is insufficient for doors; source-proven `flags`/doormask
  changed twice in each 36-pair vertical/horizontal door audit while type
  remained unchanged.
- Movement points >= 12 are necessary in the sample but demonstrably not
  sufficient. A monster also moved onto a preoccupied monster square, proving
  that “empty destination only” is not even a necessary collision rule.
- The shared promotion gate therefore reports source assertion/export
  eligibility separately from gold implementation eligibility and rejects
  every proposed frontier rule with counterexamples or earlier held-out first
  divergence.

The post-wave 25×64 `prompt-probe-v0` report is
`nethack-progress-20260730-130422-76327.json`. It remains intentionally red:
core exact-prefix fidelity is 16.6%, prompt/turn contracts are 100%, terminal
UI is 60.8%, causal specials coverage is 76.9% with zero errors, and
visibility/entity fidelity is 45.1%. Seeded outcome fidelity is now 7.4%
because history-dependent KICK outcomes that the old simulator guessed are
correctly surfaced as errors. This is a validity improvement, not a parity
regression hidden by denominator changes.

Frozen judge command:

```bash
python scripts/judge_nle_tapes.py \
  --lane both --report reports/oracle_judge_20260730.json
```

Observed result after judge hardening:

- 12 fixtures and 23 exact recorded inputs
- two independent replays per fixture/lane
- 420 layered comparisons across Python and Rust
- exact equality for lifecycle, messages/raw bytes, blstats/inventory,
  character/color/glyph planes, and composed 24×80 terminal UI
- 12 legacy captures truthfully flagged as lacking historical binary-level
  runtime provenance

## Native reset map/FOV diagnostic (not a conformance lane)

The pinned macOS NLE binary exposes read-only local `level` and `viz_array`
symbols. `scripts/nle_native_map_fov.py` fail-closes on the exact binary SHA-256
`7ac1270dfd5fa0a5fb2f715ef6a7151058f06cda595e4b722ac6d070ce0f2057`, Mach-O
symbol slide, and the independently checked `struct rm` layout before exporting
separate reset/pre-action terrain, FOV, and map-memory planes. The six-seed
contract report is `reports/authoritative_map_fov_native_20260730.json`.

This makes a native-reset diagnostic lane possible, but never hydrates gold
from a later source frame and never renders native true terrain into a
source-hidden reset cell. Across six navigation cases (three calibration,
three held-out; Python and Rust each), every reset-hidden negative control
passed: 9,581 exact source-hidden terminal cells stayed source-rendered.

The held-out comparison rejects promotion: ordinary traces first diverged at
steps `{2: 4, 3: 2}` with 2,080 visibility errors, while native bootstrap
traces first diverged at step 1 in all six lanes despite lowering visibility
errors to 1,778. The gate requires both no first-divergence regression and no
visibility-error regression on every lane of at least three held-out seeds;
its result is `rejected_no_general_rule`. Therefore this evidence caused **no
gold Python or Rust behavior change**. Dynamic scheduling, underlay/FOV rules,
combat, and KICK injury RNG remain blocked on additional causal evidence.

## Severity ledger

| Severity | Finding | Evidence | Disposition |
| --- | --- | --- | --- |
| P1 | General navigation fidelity is not established and currently drifts | Native bootstrap reduced visibility errors 2,080→1,778 but regressed every lane to first divergence at step 1 | Open; authoritative planes exist, but no causal general FOV rule passed promotion |
| P1 | General entity scheduling/combat remains behaviorally underdetermined | Native source assertions expose IDs/state/underlays; 53 moves and 48 restorations prove necessary scheduling facts, not destinations or AI | Open; no trajectory, collision, combat branch, or actor/RNG chronology inferred |
| P1 | No authentic terminal death/descent tape is canonical | Coverage ledger remains 0/33 for death and descent | Open; do not infer terminal parity from bootstrap gold scenarios |
| P2 | Cross-language checkpoint continuation changed inventory `oclass` representation | Before: 10/10 live cases failed; after: 25/25 prompt cases pass | Fixed with canonical `oclass_code`/`oclass` precedence |
| P2 | Inventory and quit terminal screens were not modeled | Exact raw NLE TTY comparison | Fixed for the observed capture-backed inventory classes and explicit quit boundary |
| P2 | NLE `specials` is only partially causally derivable | 25-seed audit contains pet, statue, corpse, and object-pile bits | `MG_PET` plus the source-proven initial stationary pet hold are implemented; other bits/later pets remain unjudgeable |
| P2 | KICK injury/stat RNG chronology is incomplete | Exact native state is now observable, but seven wall results consume 9–15 core draws shared with action/scheduler logic | Immediate reset-wall message retained; injury/stat model awaits draw-to-branch and actor chronology |
| P2 | Public NLE has no entity/scheduler/underlay authority | Public-surface audit rejected all candidates; pinned native sidecars now provide assertion-grade pre-action source state | Native source assertion contract added; gold behavior remains blocked on causal destination/AI/call chronology |
| P2 | Historical oracle binaries were not fingerprinted | All 12 old tapes are `legacy_version_only` | Honest limitation; all future captures fingerprint runtime binaries |
| P2 | Previous comparator could succeed with zero fixtures by default | Old `no_fixtures` success path | Fixed in the canonical harsh judge; negative control added |
| P2 | Previous passes did not prove deterministic repeat replay | One execution per lane | Fixed; every tape/lane now runs twice and full traces must match |
| P2 | Raw `tty_*` evidence was captured but not judged | Previous comparator selected only public projection fields | Fixed for exact message/map/status/cursor terminal composition |
| P3 | Tape files had no byte-level chain of custody | Version/action metadata only | Fixed with raw-file and per-turn SHA-256 manifests |

## Safe changes made

The judge workflow now includes exact source artifact pinning, runtime
fingerprinting for new captures, per-turn input/state hashes, manifest
validation on promotion, deterministic double replay, layered exact evidence,
non-vacuity guards, first-divergence mismatch census, prompt and turn
contracts, terminal UI, terminal boundary and `specials` checks, independent
live-NLE repeatability, held-out state construction, checkpoint continuation,
and negative controls. Simulation changes were limited to the minimized,
cross-seed behaviors listed above; unresolved nonlocal visibility, dynamic
entities, combat RNG, and hidden stair state remain open rather than guessed.

## Final verification refresh

The final pinned-runtime run passes 179 Python tests, Rust tests, frozen tape
replay (12 fixtures, 23 inputs, 420 exact layers), and Python-to-Rust
checkpoint parity. A fresh terminal-held-out 3×4 campaign is green for every
exercised contract. The equally fresh navigation-held-out 3×4 campaign remains
honestly red: exact-prefix source fidelity is 33.3%, with first divergences in
map/entity presentation rather than a masked denominator.

Source instrumentation was strengthened without adding gold behavior. Native
entity sidecars now fail closed on malformed action-bound counters, IDs,
queue/path state, scheduler fields, or underlay/object stacks. The FOV audit
now recognizes legal x-ray `IN_SIGHT` without `COULD_SEE` per pinned
`vision.c:618-657`; its six-seed source assertions are clean but do not form a
gold FOV rule. Fresh scheduler/RNG evidence binds 60 exact ISAAC64 lane
boundaries and the source gate remains non-promotable: call totals do not own
branches, dynamic actor chronology remains incomplete, and sidecars are
forbidden gold input. See the dated `reports/*_20260730_final.json` artifacts.

## Exact branch attribution refresh

Two independent trace mechanisms now close important attribution gaps without
changing gold behavior. The reproducible KICK report binds clean pinned source,
patch/toolchain/binary identity, exact callsites, raw RNG boundaries, and
independent replay; three wall-KICK transitions and 33 events are
exact-equivalent to baseline. The untouched-wheel LLDB report captures
`mfndpos`, `dog_move`, and `m_move`: six preselected seeds yielded 30
transitions and 52 matched branch records with zero observation, native-state,
RNG, replay, unmatched-event, or trace errors.

Both are source evidence only. The frontier gate still rejects gold promotion
because branch candidates do not prove selection/collision and gold lacks
portable pre-branch RNG state. The expanded vision contract also passed 12
replayed pre-action comparisons across six seeds, but positive dynamic-light,
boulder, and mimic transitions remain unexercised. Its behavioral FOV
candidate is rejected because first divergence regresses despite lower
aggregate error count.

## Dynamic vision and selector follow-up

Positive source coverage now exists for boulder blocking and active object
lighting: 40 boulder states/135 checks and six lamp-on states/209 checks,
respectively. Both campaigns pin runtime and verifier identity, retain exact
before/after native and terminal hashes, and repeat replay. A 12-seed mimic
probe found no positive state and therefore remains an explicit coverage
failure, not evidence that mimics are absent.

The selector trace was tightened to bind exact caller return boundaries. A
fresh 29-record probe found two unmatched `mfndpos` events, so the hypothesis
is rejected despite zero public, native, RNG, and replay mismatches. Promotion
now additionally requires frozen split/artifact hashes, per-fixture/lane
nonregression, and positive exact selector membership, destination, and
underlay-conservation comparisons. No current candidate meets those
requirements.

## Mimic construction and selector-boundary audit

The previous zero-positive mimic gap is closed with a pinned, fixed wizard
construction used strictly as a source-state generator. Six contiguous seeds,
504 exact input boundaries, and two independent runs produced 236 positive
mimic states, 309 positive cells, and 1,323 exact native record/plane
comparisons. Terminal evidence is retained for deterministic replay but is not
used to derive native blocker state or gold behavior.

Selector binding no longer relies on actor/order matching: each persisted
return references a unique candidate event ID and contains no raw process
pointer. One `dog_move` path from `monmove.c:826` still fails to reach the
expected caller-return breakpoint in both trace and replay. The conservation
audit consequently remains blocked: destination evidence is 29/29, candidate
membership has one counterexample among 28 movement returns, and selector-
boundary underlay has a zero denominator. Joining action-end underlay is
forbidden because later monster calls can intervene.

## Frozen scheduler source frontier

The former unmatched return was a measurement-model error. A pet attack
suspended `dog_move` at an NLE pagination boundary; the original `WAIT` did
not acknowledge it. The final predeclared tape ends with `SPACE`, resumes that
same invocation, and yields a clean six-seed calibration/held-out artifact:
42 causal selector records with zero observation, native-state, RNG, replay,
trace, or unmatched-event errors.

The source rule passes both splits. Calibration has 22 moving-membership, 25
destination, and 46 raw-underlay comparisons; held-out has 17, 17, and 34,
respectively, all exact. This establishes source semantics, not a gold
implementation. The pinned executable spec demonstrates that the public gold
pre-action projection omits actor identity/state, level candidate inputs,
path memory, scheduler chronology, combat state, and evolving RNG required by
`dog_move`/`m_move`. A separately frozen live Python shadow therefore emits
`indeterminate` with zero destination comparisons, and the gate remains
closed rather than consuming native sidecars at runtime.

## Authoritative reset entity task contract

The missing reset state now has a real task boundary. New level dumps may
contain a sanitized `authoritative_reset_entities.v1` projection captured
synchronously after reset and before action one. It carries pointer-free
stable entity identity, complete underlays, ordered scheduler state,
target/path/status/`edog`, and public-bound player/time. A separate native
receipt attests the projection and complete tape identity; it is never a gold
runtime or checkpoint input, and evolving native RNG is intentionally absent.

Both gold lanes validate and checkpoint the immutable level-dump projection.
They reject receipt/pre-action/future aliases, nested prohibited fields,
digest rebinding, queue/entity inconsistency, and reset player/time mismatch.
A fresh pinned NLE capture successfully crossed resolver → Python reset →
Python checkpoint → Rust restore with an identical projection digest and
queue. This promotes reset state availability, not a guessed transition:
selection, movement, combat, and RNG advancement remain disabled until their
portable post-reset rules pass held-out parity.

## Portable reset RNG contract

The reset task contract now carries a second independent projection:
`authoritative_reset_rng.v1`. It contains complete little-endian ISAAC64 core
and display contexts, not configured seed values, plus pinned source/header
identity and exact next-value semantics. Python replays the raw context
without native calls; Rust validates and preserves the same bytes through a
checkpoint.

This is reset-state availability, not permission to advance RNG in gold. The
portable projection has no branch ownership or actor chronology, and no
post-reset draw schedule has passed held-out Python/Rust parity. Gameplay RNG
therefore remains unchanged until that evidence exists.

## Confirmed-quit terminal contract — 2026-07-31

An authentic NLE `Command.QUIT` → `y` tape is now canonical as
`val-quit-seed-20260725`. NLE clears the live dungeon planes and emits a
24×80 score-screen TTY; the capture workflow now preserves that final terminal
observation and labels it `quit` from the already-recorded prompt boundary.
Promotion accepts this cleared final snapshot while remaining fail-closed for
any nonterminal snapshot that leaves Main Dungeon dlvl 1. Python and Rust both
match all 3 snapshots, including the terminal TTY, with 18 exact layer
comparisons. A second canonical tape, `val-quit-decline-seed-20260725`, pins
the converse: `n` leaves the episode live, restores the dungeon projection,
and emits an empty message rather than generic cancellation text. This adds
lifecycle evidence only; death, save, and descent still require their own
authentic tapes.

## Inventory display contract — 2026-07-31

The authentic zero-turn `Command.INVENTORY` tape
`val-inventory-seed-20260725` is now canonical. It pins the empty public
message, the inventory-page terminal characters/colors/cursor, unchanged
reset state, and the pager mode without consuming a gameplay turn. Python and
Rust both pass its two snapshots through the complete strict layer set. This
is display evidence for the captured inventory classes, not a claim that all
inventory commands or item semantics are complete.

## First-turn pet hypothesis rejection — 2026-07-31

A broader probe attempted to generalize the reset pet hold from stationary
WAIT/SEARCH to every first consumed action (cardinal movement included). That
generalization was rejected by its own held-out evidence: blocked movement
frequently had `blstats[20]` delta 0, while other seeds showed genuine first
turn pet displacement. The rejection artifact is
`reports/first_turn_pet_hold_20260731.json` (128 cases, 22 errors). The gold
lanes therefore retain only the narrower exact stationary WAIT/SEARCH hold;
no first-turn movement, destination, collision, or scheduler rule was
promoted. This negative control is part of the validity record, not a parity
claim.

## Descent promotion gate — 2026-07-31

A source-guided walk to the pinned full-map down stair at `(9,18)` was
captured out of tree as `/tmp/nethack-descend-20260731T175225`. The route
reached the observed stair and the capture emitted a valid pre-dlvl2 terminal
boundary, but promotion was correctly refused at the first consumed move:
NLE rendered the reset kitten at `$.chars[16]`, while both gold lanes cleared
that presentation overlay. This is a dynamic entity/presentation divergence,
not a descent-contract failure. The artifact remains diagnostic; no descent
tape was added to the corpus and no pet movement rule was inferred from one
route.

## Reset underlay surface restoration — 2026-07-31

The immutable `authoritative_reset_entities.v1` projection now supplies one
additional, narrowly scoped gold behavior: a visible reset presentation cell
may restore its exact source memory surface when that overlay expires. Python
and Rust admit only the pinned cmap surfaces `S_ndoor`, the four oriented door
surfaces, and `S_room`; blank/unknown glyphs, hidden entity cells, conflicting
direct reset terrain, object stacks, identity, movement, collision, FOV, and
RNG are untouched. Hidden underlays therefore remain unavailable to movement
and visibility until a causal source observation exposes them.

The behavior is symmetric and checkpoint-safe. Focused presentation, native
entity, reset-projection, and frozen-judge tests pass; a release-built Rust
replay also passes all 31 canonical fixtures / 59 inputs. A fresh two-seed
navigation probe (`/tmp/nethack-underlay-probe-20260731T190258Z`) still
diverges at dynamic map/entity pixels and its native-bootstrap candidate is
diagnostic-only: ordinary traces had 120 held-out visibility errors versus
218 for the bootstrap candidate, and the candidate moved first divergence to
step 1. No general FOV or scheduler rule was promoted from this result.

The corresponding readable progress report is
`/tmp/nethack-progress-out/nethack-progress-20260731-150745-88118.json`:
source exact-prefix fidelity is 9.4% (2/2 cases), source eligibility and
NLE repeatability are 100%, checkpoint continuation is 100%, and the
visibility/entity layer remains 3.1% with 108 quarantined surface records.
These are two-case diagnostics, not a corpus score.

## Source-backed stationary WAIT — 2026-07-31

`val-wait-seed-20260725` is a minimized, independently captured one-action
NLE tape. Its reset presentation includes the source-marked pet and its
consumed `MiscDirection.WAIT` snapshot has an empty message. Both gold lanes
now select that exact empty message when the immutable reset projection is
present; synthetic authored fixtures without source provenance retain their
legacy acknowledgement. Release-built Python/Rust replay is strict-green for
the new tape and all prior canonical tapes. No actor movement, collision, or
RNG advancement is inferred from this result.

## Source-backed extended-command prompt — 2026-07-31

`val-extcmd-seed-20260725` is a minimized two-action NLE tape covering
`Command.EXTCMD` followed by `Command.ESC`. NLE enters a string mode whose
prompt is exactly `#`, and Escape returns to normal mode with an empty message.
Python and Rust now reproduce that prompt/cancellation pair; the existing
direction and item prompts retain their separately captured `Never mind.`
contract. The tape is strict-green in both lanes, and no command execution or
turn advancement is inferred from the cancelled prompt.

## Source-backed ENGRAVE prompt — 2026-07-31

`val-engrave-seed-20260725` covers `Command.ENGRAVE` followed by Escape.
With the captured starting inventory, NLE presents the exact weapon selector
`What do you want to write with? [- ab or ?*]`; cancellation returns
`Never mind.` without consuming a turn. Python and Rust now derive the weapon
letters from source-backed inventory state for this prompt while preserving
the legacy generic prompt for authored fixtures without that provenance. The
two-action tape is strict-green in both lanes and does not claim engraving
text execution or floor-state semantics.

## Source-backed DROP prompt — 2026-07-31

`val-drop-seed-20260725` covers `Command.DROP` followed by Escape. NLE lists
every captured inventory letter as `What do you want to drop? [abcde or ?*]`
and returns `Never mind.` on cancellation. Both gold lanes now derive the
letter list from their source-backed reset inventory and pass the strict
two-action tape. This adds prompt coverage only; no item transfer or floor
object semantics are inferred.

## Source-backed WEAR no-item path — 2026-07-31

`val-wear-seed-20260725` covers a reset where the only armor is already worn.
NLE answers `Command.WEAR` with `You don't have anything else to wear.`
without entering an inventory prompt, and the following Escape clears the
message. Python and Rust now gate that no-candidate path on the immutable
source reset projection and preserve the legacy prompt behavior for authored
fixtures. The two-action tape is strict-green; no armor mutation is inferred.

## Source-backed PUTON no-item path — 2026-07-31

`val-puton-seed-20260725` covers a reset with no rings or amulets. NLE emits
`You don't have anything else to put on.` directly for `Command.PUTON`; the
following Escape clears the message without opening a prompt or consuming a
turn. Both gold lanes gate this no-candidate response on source-backed reset
inventory and pass the strict tape. No accessory behavior is inferred.

## Source-backed TAKEOFF transition — 2026-07-31

`val-takeoff-seed-20260725` captures removal of the starting uncursed small
shield. NLE consumes one turn, emits `You were wearing an uncursed +3 small
shield.`, raises AC from 6 to 10, and removes `(being worn)` from the raw
inventory string; the following Escape clears the message. Python and Rust
reproduce those public state changes and preserve the source-backed inventory
padding glyphs/classes. No general armor tables or multi-item equipment rule
is inferred.

## Source-backed WIELD prompt — 2026-07-31

`val-wield-seed-20260725` captures the reset `Command.WIELD` prompt and its
Escape cancellation. NLE presents `What do you want to wield? [- ab or ?*]`
for the two visible weapon letters, with no turn consumed. Python and Rust
derive the same source-backed weapon selector and pass the strict tape; actual
weapon selection remains unclaimed because the pinned action surface has no
letter input in this tape.

## Source-backed QUAFF no-item path — 2026-07-31

`val-quaff-seed-20260725` covers a reset with no potion inventory. NLE emits
`You don't have anything to drink.` directly for `Command.QUAFF`; Escape then
clears the message without a prompt or turn. Both gold lanes gate this path on
the source-backed inventory classes and pass the strict tape. Potion effects
and RNG are intentionally outside this assertion.

## Source-backed READ no-item path — 2026-07-31

`val-read-seed-20260725` covers a reset with no scrolls. NLE emits
`You don't have anything to read.` directly for `Command.READ`; Escape clears
the message without a prompt or turn. Both gold lanes reproduce the source
inventory-class guard and pass the strict tape. Scroll decoding and effects
remain outside this assertion.

## Source-backed FIRE no-ammunition redirect — 2026-07-31

`val-fire-seed-20260725` captures `Command.FIRE` with an empty quiver. NLE
first emits `You have no ammunition readied.`; the next Escape opens the
weapon-backed throw selector `What do you want to throw? [ab or ?*]` rather
than simply dismissing. Python and Rust reproduce this reset-only prompt
redirect and pass the strict tape. Projectile execution and combat RNG remain
unimplemented here.

## Source-backed THROW prompt — 2026-07-31

`val-throw-seed-20260725` captures the source-backed `Command.THROW` selector
after reset. NLE presents `What do you want to throw? [ab or ?*]`; Escape
returns `Never mind.` without consuming a turn. Python and Rust derive the
weapon-letter list from the captured inventory and pass the strict tape. Item
selection, projectile motion, and combat RNG remain outside this assertion.

## Source-backed ZAP no-wand path — 2026-07-31

`val-zap-seed-20260725` covers a reset with no wand inventory. NLE emits
`You don't have anything to zap.` directly for `Command.ZAP`; Escape then
clears the message without opening a selector or consuming a turn. Python and
Rust gate this no-candidate path on source-backed inventory classes and pass
the strict tape. Wand effects and direction targeting remain outside this
assertion.

## Source-backed QUIVER selector — 2026-07-31

`val-quiver-seed-20260725` captures `Command.QUIVER` on the reset inventory.
NLE presents `What do you want to ready? [- b or ?*]`, excluding the weapon
currently in hand; Escape returns `Never mind.` without consuming a turn.
Python and Rust derive that source-backed selector and pass the strict tape.
Actual quiver assignment and ranged execution remain outside this assertion.

## Source-backed REMOVE selector — 2026-07-31

`val-remove-seed-20260725` captures `Command.REMOVE` with no rings or amulets
in the reset inventory. NLE still opens the exact empty selector
`What do you want to remove? [*]`; Escape returns `Never mind.` without a turn.
Python and Rust reproduce this source-backed prompt and pass the strict tape.
Accessory removal effects remain outside this assertion.

## Source-backed INVOKE selector — 2026-07-31

`val-invoke-seed-20260725` captures `Command.INVOKE` with no invokable item in
the reset inventory. NLE presents `What do you want to invoke? [*]`; Escape
returns `Never mind.` without consuming a turn. Python and Rust preserve this
empty source-backed selector exactly. Artifact invocation and effects remain
outside this assertion.

## Reset-owned scheduler boundary — 2026-08-02

Both gold lanes now retain the immutable reset entity queue and portable core
ISAAC context in checkpoint state. An offline candidate helper implements the
source `mcalcmove` rounding and `movemon` eligibility arithmetic, but live gold
does not advance it. The native descent route proves that core draws are
interleaved with `distfleeck`, `dog_move`, and post-turn calls; a one-word-per-
action advancement would therefore be an invalid chronology shortcut.

The route at `/tmp/nethack-descend-20260731T175225` remains diagnostic-only:
its first strict divergence is the dynamic pet destination/underlay. No future
source frame or pre-action sidecar is hydrated into either lane. The 31-tape,
59-input dual-lane judge remains strict-green after this boundary change.

The candidate accounting now mirrors repeated `movemon` passes in native queue
order and records each movement debit before post-drain `mcalcmove` allocation.
It remains source-only: it never selects a destination or advances live gold
state. An 8-seed held-out run covers 40 action boundaries and 80 exact
ISAAC64 lane comparisons; the promotion gate remains fail-closed because
cross-language pre-action destination evidence is still absent.

The next evidence boundary is now explicit. The exact-wheel `dog_move` report
joins each retained event to the unique entity and hero scheduler state from
the immediately preceding source frame. Three independent seeds yield 14
joined events with zero public/native/final-RNG mismatches and exact replay:
`/tmp/dogmove-return-20260802-joined.json`. The eight-seed scheduler report
also carries hero movement points at both sides of each action:
`/tmp/native-scheduler-20260802-8seed-hero.json`. These are source assertions,
not behavior candidates; the gate still rejects Python/Rust dynamic pathing
until a general pre-action destination/collision contract is established.

The first-action held-out sweep also falsified the old boundary assertion:
across 20 seeds (`CompassDirection.N`, then `WAIT`), two tame entities moved
from action-boundary movement points of zero and ended at 12. The verifier now
records both as explicit allocation-boundary ambiguities rather than source
errors (`/tmp/native-first-action-20260802.json`). This confirms that the
captured action boundary can precede `mcalcmove`; action-boundary readiness is
not a safe scheduler rule, and dynamic entity behavior remains blocked.

An exact-wheel `mcalcmove` entry/return trace now captures the missing source
boundary itself. Eight independent seeds produce 106 allocation events with
zero public/native/final-RNG mismatches, zero replay mismatches, and complete
pre-action joins (`/tmp/mcalcmove-20260802-8seed.json`). Every retained actor
enters allocation at zero movement points and receives 0, 12, or 24 points
from the pinned source return; this explains the earlier action-boundary
ambiguity. It remains source-only: the trace does not expose a sufficient
destination, collision, or pet-AI contract for either gold lane.

The fixed 20-seed `CompassDirection.N`/`WAIT` family adds 134 exact
`mcalcmove` events with zero mismatches and exact replay
(`/tmp/mcalcmove-first-action-20260802.json`). For both earlier moved-pet
seeds, the native trace shows allocation of 12 points before the observed
move. That closes the scheduler-allocation chronology gap, but destination
selection remains unobserved and unpromoted.

## Cross-lane semantic replay guard — 2026-08-04

The frozen judge now records a private-state trace for each gold lane and
compares Python against Rust at every replay prefix. This is intentionally a
gold-to-gold validity plane: it does not consume native sidecars or claim that
private state is oracle evidence. It catches a hidden scheduler, inventory,
object, actor, or terminal-state split even when both lanes render the same
public frame. The 31-fixture corpus passes with 90/90 exact semantic prefix
comparisons and zero divergences in
`/tmp/nethack-judge-semantic-20260804.json`.

## Source spawn-gate identity correction — 2026-08-04

The native pre-action RNG ledger for held-out seed `20260806` showed that
action 21 consumes 41 core draws, including `allmain.c`'s `rn2(70)` spawn gate,
the fountain/sound gate, and the engraving gate. Both gold lanes had suppressed
that spawn draw from the clock `(source_turn + dynamic_turns, dynamic_turns) ==
(21,20)` alone, shifting the ISAAC cursor by one and causing the first actor
presentation drift on the following turn. The guard is now keyed to the full
kitten-at-(29,5)/lichen-corpse-at-(29,4) receipt that independently proves the
native early return. An unrelated five-actor population consumes the spawn
gate in both Python and Rust.

The corrected held-out replay `/tmp/nethack-live-20260804-case2-fix` has zero
gold-lane transition divergences through all 24 actions, and Python's core
ISAAC state matches every native pre-action state hash. The regression suite
adds a negative-control test for the same clock without the corpse surface;
Python source tests pass 32/32, Rust unit tests pass 4/4, and the frozen
31-fixture dual-lane judge remains green.

## Source PM_NEWT collision, death, and corpse receipt — 2026-08-04

The corrected native RNG trace for `fuzz-case-0000-seed-20260807` binds the
level-0 newt at screen `(12,14)` to `mattacku` (hero bite/miss), then binds
the kitten at `(13,13)` to `mattackm` (1d6 bite, cancellation, corpse chance,
temporary corpse timer, and `grow_up`). The fresh corpse is object 24 with
`otyp=240`, `corpsenm=318`, glyph 2146, class 7, color 3, and source order 0.
The source trace also proves that the kitten's second fast pass commits to the
corpse cell before the kill pager; `MiscAction.MORE` then consumes the exact
`obj_resists(100) -> distfleeck(5)` prefix and emits `The kitten eats a newt
corpse.`.

Both gold lanes now reproduce that complete seven-step boundary exactly,
including hero HP, public `f` placement over the corpse, pager input mode,
corpse removal, message/raw-message bytes, and private scheduler state. The
held-out replay artifact is
`/private/tmp/nethack-live-20260804-case3-final5-1785874650`; its Python/Rust
strict reports are equal through step 7 with no runtime errors. The longer
24-step diagnostic remains deliberately fail-hard at step 8 on the unrelated
random-position source-spawn branch; no generic spawn rule was inferred.

## Source sewer-rat spawn receipt — 2026-08-04

The next native boundary is now joined for the same pinned reset. The source
`makemon_rnd_goodpos` wheel consumes nine exact `(rn1(77,2), rn2(21))` pairs:
`(27,12)`, `(7,3)`, `(52,20)`, `(65,11)`, `(32,7)`, `(69,13)`, `(22,7)`,
`(48,15)`, and `(41,4)`. The first eight cells are rejected by the static
`goodpos` substrate; the ninth is screen `(40,4)`. The following source calls
are `rnd(21)=8` (PM_SEWER_RAT), `rnd(4)=1` HP, gender `rn2(2)`, group gate
`rn2(2)=0`, and level-zero `m_initinv` gates `rn2(50)=34`, `rn2(100)=11`,
`rn2(100)=59`. Native queue identity is `m_id=25`; the dead PM_NEWT is purged
before the existing kitten/jackal queue orders are incremented.

Python and Rust now materialize the exact sewer-rat `mons[]` profile and remain
strict-equal through 40 actions with no runtime errors in
`/tmp/nethack-spawn-32-1785877399`. The frozen semantic judge remains green
after the change (`fixtures=31`, `inputs=59`, `cross_lane.semantic_state=90`,
`status=pass` in `/tmp/nethack-judge-after-spawn-20260804.json`). This is a
reset-bound species/allocator receipt; other random spawn species and source
identity contexts remain fail-hard.

## Source PM_NEWT random-spawn receipt — 2026-08-04

Held-out seed `20260726` supplies a second independently joined spawn wheel.
The native position search consumes `(17,15)` then `(30,7)`, rejecting the
first static-wall cell and accepting screen `(29,7)`. `rndmonst` reports
choice 19 of 21 (`PM_NEWT`), `rnd(4)=4` HP, gender `rn2(2)=1`, the entered
small-group gate `rn2(2)=1` and `rnd(3)=1`, followed by `m_initinv` gates
`rn2(50)=37` and `rn2(100)=72`. The new actor is native ID 28; the existing
queue IDs `[27,15,13,12,9]` retain source order after the head insertion.

Python and Rust now reproduce the receipt and run the 40-action tape without
runtime errors. The remaining public mismatch begins at the known action-18
visibility/entity presentation edge, so no general spawn or movement rule is
inferred. The frozen judge remains `pass` with the exact report at
`/tmp/nethack-judge-after-newt-20260804.json`.

## PM_NEWT spawn-turn chronology correction — 2026-08-04

The native seed-20260726 boundary consumes the `nfountains=1` `dosounds`
gate (`rn2(400)=230`) after the newt spawn, but does not consume the ordinary
engraving roll. The previous gold cursor therefore advanced one draw too far
before the next kitten turn. Both lanes now omit only that engraving draw when
the complete ID-28 PM_NEWT receipt and six-actor allocator population are
present; unrelated populations still consume the normal gate.

The native and gold core ISAAC states now match at action 17 and action 18,
and both lanes are strict-equal through 40 actions in
`/tmp/nethack-spawn-newt2.Hb4y8f/run`. This is a source-owned chronology
receipt, not a general engraving rule.

## Corpse-chance and held-out pet-path validity correction — 2026-08-04

Native source evidence showed that `corpse_chance` is a construction gate,
not merely an RNG prefix. Python now returns that receipt and guards both
lichen and newt corpse materialization; Rust already had the newt guard and
now has the same lichen guard. The focused Python source suite is 38/38 and
Rust library tests are 5/5. The frozen dual-lane judge remains `pass` with
`fixtures=31`, `inputs=59`, and `cross_lane.semantic_state=90` in
`/tmp/nethack-judge-after-lichen-chance-20260804.json`.

On held-out seed `20260733`, both lanes cross the former step-10 object
interest failure. An instrumented native dog trace then justifies one narrow
second-pass destination receipt for kitten entity 40 at source turn 14,
ending at NLE `(25,15)`. After that receipt the replay reaches step 23, where
the random-position spawn wheel remains unjoined and fails hard in both lanes;
no generic spawn or movement behavior was inferred.
