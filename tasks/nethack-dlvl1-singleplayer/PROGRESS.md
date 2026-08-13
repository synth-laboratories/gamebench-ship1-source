# NetHack dlvl-1 coverage ledger

## Generic population wave — 2026-08-13

- Added `shared/procedural_population.json`, a 36-slot source-profiled hostile
  wheel covering 20 low-level `nle-0.9.0/src/monst.c` entries. The table
  carries species IDs, `geno`/generation frequency, corpse weight and
  nutrition, no-corpse flags, ordered attacks, typed resistances, glyph class,
  and movement rates. The wheel is weighted by each source profile's
  generation-frequency field; it is explicitly a source-derived population
  contract, not a claim that the exact native `rndmonst()` selector is done.
- Procedural level-1 levels now run a deterministic generic population clock:
  every 50 consumed turns they select a profile from the shared wheel, choose
  an unoccupied passable cell, create a full movement/combat/corpse actor, and
  cap the population at 12. Python and Rust consume the same LCG draws and
  emit identical spawn events/private state.
- Source-profiled poison attacks now infer the poisoned status from their
  typed `damage_type` when no duplicate effect field exists, covering the
  generated bee/rat/spider attack shapes in both lanes.
- Floating-eye `paralyzed` attacks now use a timed blocking status with
  matching hero/monster turn handling and cross-language event ordering.
- Authored traps now optionally roll `damage_dice` × `damage_sides` plus the
  existing flat `damage`, for both hero and monster targets; legacy flat-trap
  fixtures retain their previous no-draw behavior.
- Authored projectile items now apply recognized `effect` statuses to a
  surviving monster hit, including poison/paralysis, with shared event and
  expiration ordering across both lanes.
- Authored x-ray effects now expand the live generic FOV through opaque cells
  for a bounded duration, reveal actors/objects in that radius, and expire
  without erasing remembered terrain; Python and Rust share the same optional
  `metadata.xray_radius` bound and blind-state precedence.
- Generic actor `confused` status now overrides normal target/path selection
  with shared-RNG wandering, while actor `blind` status suppresses hero
  detection and attack LOS; both behaviors are covered in the dual-lane actor
  parity suite, including one-turn expiry timing.
- Validation: the 36 selector slots and 20 profiles are covered; the 50-turn
  cross-language spawn tape is strict-equal; both lanes compile and Rust unit
  tests remain green. The frozen three-profile bootstrap selector remains
  unchanged for fixture stability. The combined generic actor/FOV/spell/
  randomized parity batch is green at 49 tests.

## Validity wave — 2026-08-04 (MARK read/pager boundary)

- Native `engrave.c::read_engr_at(MARK)` is now joined only when the reset
  map supplies an exact MARK record at the newly entered public cell and the
  cell has no floor-object surface. Malformed records, other engraving types,
  blind reads, and object collisions fail closed.
- Python and Rust emit the exact graffiti message, hold the source clock at
  the movement boundary, require explicit `MiscAction.MORE`, resume source
  scheduler time, and emit the exact quoted continuation. Frozen conformance
  remains green: 31 fixtures / 59 inputs / 1,080 layer comparisons in both
  lanes (`/tmp/nethack-judge-20260804-engrave.json`).
- Held-out seed `20260726` now passes the message and turn layers through the
  pager in `/tmp/nethack-engrave-20260804-d`; the first remaining error is the
  kitten's post-MORE source destination/presentation. This is intentionally
  not promoted as general actor continuation behavior.

## Validity wave — 2026-08-03 (reset stats + scheduler chronology)

- Legacy tapes with a complete captured `nle_blstats` reset vector now source
  public stat defaults from that vector in both gold lanes; scheduler/path
  sidecar eligibility remains independently fail-closed.
- The outer scheduler now mirrors `allmain.c`: `mon.c::movemon()` is one
  fmon pass, but it is repeated while movement remains. This preserves native
  fast-actor behavior instead of incorrectly forcing one actor call per player
  turn. The held-out lichen/grid-bug replay remains strict-equal through all
  20 actions after the correction.
- A pinned native dogmove trace confirms the chronology: seed `20260726`
  invokes the kitten twice at `monstermoves=3`, matching both gold lanes after
  the loop correction. The kobold-zombie `M2_STALK` branch is admitted only
  with its identity-bound source profile; unsupported combat and target/path
  branches remain fail-hard.
- Validation: frozen judge `31` fixtures / `59` inputs / `1080` layer
  comparisons passes in both lanes; focused Python suite 38 tests pass; Rust
  unit tests 3/3 pass; exact held-out replay is green in both lanes.

## Validity wave — 2026-08-03 (dynamic pet/grid-bug frontier)

- Joined the pinned food-ration (`otyp 268`) `can_carry` receipt to the
  kitten's source `dog_invent` branch. Both gold lanes now consume the exact
  `rn2(20)`, `rn2(udist)`, and `rn2(apport)` gates without guessing inventory
  mutation; unsupported successful pickup remains fail-hard.
- Mirrored the source ordinary-actor post-collision `distfleeck` draw in Rust.
  Before this fix Rust was one ISAAC draw short after the grid bug's hero
  collision, shifting the next pet pass; the exact source call count now
  agrees in both languages.
- Exact held-out replay: `/tmp/gridbug-both-20260803c` reports Python
  `equal` and Rust `equal` for all 20 actions. The held-out reset diagnostic
  no longer has the legacy DEX baseline mismatch; it remains a diagnostic
  actor/collision campaign and is not promoted into the frozen corpus.
- Validation: 30 focused Python scheduler/pager/underlay tests pass; Rust
  unit tests pass 3/3; Python and Rust exact-lane replays are both green.

The canonical corpus currently has **31 / 33** required strict NLE tapes
(93.9%). Every listed tape compares the complete captured public observation
in both own lanes: chars, glyphs, colors, blstats, fixed-width raw message,
and inventory planes. This is evidence coverage, not a claim of general
NetHack parity.

## Validity wave — 2026-08-03

- Fixed the Rust portable ISAAC64 recurrence at the update boundary: the
  pinned `src/isaac64.c` complements only the `<<21` mix branch. A synthetic
  Rust regression crosses `n=0` and matches the independent Python recurrence.
- Reset-bound complete `nle_blstats` now supplies missing stat defaults in both
  lanes (metadata remains an explicit override). The captured DEX=15 therefore
  selects the source `allmain.c:294` `rn2(85)` gate instead of the old DEX=10
  fallback.
- Scheduler post-turn RNG order now follows the pinned source:
  `spawn → dosounds → exercise → engraving`; the instrumented source ledger
  matches the Python call bounds/values through the first held-out actor
  mismatch. This is a bounded validity fix, not general AI promotion.
- Validation: Rust unit test, 15 focused Python runtime/RNG tests, all checked-in
  gold fixtures, Python→Rust checkpoint parity, and 4,977/4,977 source FOV
  comparisons pass. The fresh held-out `10 × 32` run reports `7.5%` exact
  prefix fidelity, `9/121` action coverage, and first reset-case divergence at
  step 13 on pet destination/candidate selection; all 10 traces remain
  diagnostic and none are error-free.

| Subsystem | Current own-engine support | Frozen NLE evidence | Status |
| --- | --- | --- | --- |
| Action surface | All pinned `nle.nethack.ACTIONS` ids are accepted with canonical names and raw adapter keys | 31 / 33 tapes across movement, prompts, pickup, search, doors, inventory, WAIT, EXTCMD, ENGRAVE, DROP, WEAR, PUTON, TAKEOFF, WIELD, QUAFF, READ, FIRE, THROW, QUIVER, REMOVE, INVOKE, ZAP, and quit terminal UI | adapter breadth is not parity by itself |
| Level input | Capture-backed 21×79 terrain/glyph/color dump, hero, objects, monsters, traps, and unseen planes | 31 / 33 tapes | raw reset planes, blstats, messages, and inventory baselines are checked exactly |
| Reset topology substrate | Immutable reset-bound 21×79 `rm.typ`/`rm.flags`/`rm.horizontal` projection, optional reset static-light planes, and identity-bound reset boulder blocker plane are validated in both lanes and checkpointed privately | 6-seed native FOV verifier + positive blocker seeds + synthetic tamper/replay tests | source identity, shape, bounds, digest, future-field guards, complete lighting, and one-shot boulder expiry at KICK are covered; moving-actor pathing remains unpromoted |
| Pixel parity gate | Strict comparator checks characters, glyphs, colors, specials, blstats, messages, and inventory at every snapshot | 31 / 33 tapes | no partial-plane pass is accepted for promotion |
| Terminal lifecycle | Confirmed QUIT prompt, exact 24×80 score-screen TTY, and nonterminal declined-quit return | 2 quit tapes | authentic death, save, and descent boundaries remain separate work |
| Live NLE fuzz | NLE, Python, and Rust consume the same action IDs; first-error census, source-state eligibility, prompt/turn/UI/specials/terminal checks, NLE repeatability, held-out reset, and checkpoint continuation are reported separately | diagnostic only | actions with unknown pre-action source state are `unjudgeable`, never equal/diverged, and are excluded from fidelity denominators |
| Property invariants | Hypothesis constrained fixtures, public observation integrity, determinism, checkpoints, and Python/Rust trace properties | N/A | own-engine consistency only; not NLE evidence |
| Geography | Main Dungeon dlvl 1 only; `>` terminalizes as `descended`; branch/dlvl-2 dumps rejected | 0 / 33 descent tapes | descent route is captured but blocked on room/corridor visibility and pet motion |
| FOW / memory | Source-shaped static `COULD_SEE` (Algorithm C), reset static-light/night-vision gating, one-sided wall/closed-door lighting, reset-hero underlay, visible reset-entity underlay restoration, and reset-boulder blocker input | 9,954 native source comparisons across six seeds, positive blocker records on seeds `20260726`/`20260727`, zero focused mismatches | the narrow reset static floor/corridor plus one-shot boulder gate is promoted in both lanes when its complete source-backed extension is present; full `IN_SIGHT`, moving mimics, mobile light, xray/blindness, and historical memory remain unpromoted |
| Movement / doors | 8-way walk, long movement, direction prompts, glyph-backed open/closed doors, kick | east movement; door open in both orientations; closed/no-door close; kick | open-door resistance and broader terrain/LOS behavior remain unproven |
| Inventory / food | Letter assignment, capture-backed persistent inventory display, exact tool prompt, pickup, food prompt/cancel | pickup, stair pickup, eat cancel | inventory display is exact for observed weapon/armor/food/tool classes; broader item semantics remain unproven |
| Combat | Deterministic fixture melee, death, XP, and gold basics | 0 / 33 tapes | pinned native sidecars now expose stable identity, allegiance, HP, movement state, underlay, and exact RNG state for source assertions; destination/AI/draw-to-branch chronology is still missing, so no general combat rule is eligible |
| Traps / pets | Fixture-declared traps, exact immediate pet-KICK confirmation, reset-derived interaction markers, one source-proven stationary WAIT/SEARCH/TAKEOFF hold, and source-gated hero/safepet displacement | 1 staged + 0 / 33 canonical tapes | the bounded `hack.c:is_safepet` branch is implemented only with a joined tame identity, visible marker, and reset-core `rn2(7)` guard; later pet AI/pathing and trap effects remain unimplemented |
| Shops / branches / dlvl2 | No shop model; deeper play hard-stops | N/A | deliberately outside geography |

## Live assertion lanes

- `source_behavior_oracle`: exact-prefix fidelity only over source-eligible
  transitions. `unjudgeable_turns` is a separate count; an affected campaign
  is `partial_unjudgeable`, not pass/fail evidence for those turns.
- `source_state_eligibility`: closed provenance (`reset-observed`,
  `prior-turn-observed`, `capture-annotation`, or `unknown`) and a fail-closed
  Python/Rust denominator check. Lane disagreement is a report error.
- `prompt-probe-v0`: excludes `PICKUP`, and is structurally 100% eligible.
  It must remain so; do not turn a source-unknown pickup into prompt-fuzz
  score noise.
- `known-underlay pickup`: a separate multi-seed live verifier plus the two
  frozen pickup tapes. It proves only pickup after the underlay was observed
  before the action; it does not repair an unknown live reset underlay.
- `seeded_outcome_oracle`: exact observable messages, raw bytes, blstats
  deltas, map-plane deltas, terminal state, and prompt origin for direction
  outcomes such as KICK/FIGHT. It does not infer NLE's private RNG.
- `visibility_entity_transition_oracle`: static reveal/retain/forget errors,
  presentation-only overlay motion, and exact vacated-cell restoration. Glyph
  continuity is never treated as an entity identity.
- `prior_source_static_replay_v1`: diagnostic assistance from only the
  immediately preceding NLE frame's glyph-classified cmap cells. It may
  hydrate unknown memory, never overwrite known state, import overlays, or
  contribute to the core fidelity score.
- `specials_oracle`: exact causal `MG_PET` projection plus zero-cell negative
  controls. Corpse/statue/object-pile bits and pets without a current
  materialized gold marker are counted as unjudgeable, never as passes.
- `native_pre_action_evidence.v1`: hash- and action-bound read-only source
  snapshots of true terrain/FOV/memory, stable entities/underlays/scheduler
  fields, and both exact 4,128-byte ISAAC64 states. Every record is captured
  before its named action, deterministically replayed, and prohibited from
  level-dump hydration, gold runtime input, and conformance denominators.
- `native_reset_entity_scheduler_state.v1`: one reset-only native receipt
  captured before action one and bound afterward to the exact level dump,
  reset projection, action tape, oracle/runtime identity, and binary. Its
  sanitized `authoritative_reset_entities.v1` projection is the portable task
  field carrying stable identity, complete underlays, movement/queue/path/
  status, and player reset state; the separate reset-bound
  `authoritative_reset_rng.v1` field carries exact core/display ISAAC64 bytes.
  Gold may consume these reset projections but never the native receipt.
  Missing v1 receipts are explicitly scheduler-source-ineligible.
- The first reset-turn presentation boundary is now promoted in both gold
  lanes: a source-backed `SEARCH`/`WAIT`/`TAKEOFF` retains the exact reset overlay set
  (including object pixels) when authoritative reset entity state is present.
  The native verifier covers 20 held-out seeds, 78 visible actor comparisons,
  two independent runs, and zero position mismatches. This deliberately does
  not model later actor AI, destination selection, collision, or combat.
- `frontier_promotion_gate.v1`: refuses zero-comparison, future/reset-hydrated,
  seed/coordinate-fitted, non-replayable, single-language, counterexample-
  bearing, or held-out-regressing native-assisted rules. Source observability
  and gold implementation eligibility are separate booleans.
- `reset_wall_kick_portability_blocker.v1`: two independent pinned-native
  replays now capture the reset/post-action `aexe`/`atime` accumulators and
  attribute-check deadline alongside HP/DEX/CON and RNG digests. The 20-seed
  probe found 17 visible-wall cases, six public outcome signatures, and exact
  replay; it remains source-pass/gold-blocked because exercise and whole-turn
  draw ownership are not a portable action contract.

## Current strict corpus

- `val-east-seed-20260725`: one raw east move.
- `val-east-pickup-seed-20260725`: movement followed by pickup.
- `val-stair-pickup-seed-10`: return to a revealed stair and fixed-stair pickup.
- `val-search-seed-20260725`: empty search turn.
- `val-wait-seed-20260725`: source-backed stationary WAIT with an empty NLE message.
- `val-extcmd-seed-20260725`: `#` extended-command prompt and empty Escape cancellation.
- `val-engrave-seed-20260725`: weapon-selection prompt and cancelled ENGRAVE.
- `val-drop-seed-20260725`: all-inventory-letter DROP prompt and cancellation.
- `val-wear-seed-20260725`: no-available-armor WEAR message and empty cancellation.
- `val-puton-seed-20260725`: no-accessory PUTON message and empty cancellation.
- `val-takeoff-seed-20260725`: source-backed shield removal, AC update, and cancellation.
- `val-wield-seed-20260725`: source-backed weapon-selection prompt and cancellation.
- `val-quaff-seed-20260725`: no-potion QUAFF message and empty cancellation.
- `val-read-seed-20260725`: no-scroll READ message and empty cancellation.
- `val-fire-seed-20260725`: no-ammunition FIRE message and throw redirect.
- `val-throw-seed-20260725`: weapon-letter THROW prompt and cancellation.
- `val-zap-seed-20260725`: no-wand ZAP message and empty cancellation.
- `val-quiver-seed-20260725`: source-backed QUIVER selector and cancellation.
- `val-remove-seed-20260725`: empty-accessory REMOVE selector and cancellation.
- `val-invoke-seed-20260725`: empty INVOKE selector and cancellation.
- `val-eat-cancel-seed-20260725`: food prompt then cancel.
- `val-open-cancel-seed-20260725`: open prompt then cancel.
- `val-open-empty-east-seed-20260725`: failed open after a direction response.
- `val-door-kick-seed-20261040`: failed kick against a closed door.
- `val-door-close-seed-20260061`: close against an already-closed door.
- `val-close-empty-east-seed-20260725`: close against a non-door.
- `val-door-open-horizontal-seed-20260316`: `2374` closed door opens to `-`/`2372`.
- `val-door-open-vertical-seed-20260315`: `2375` closed door opens to `|`/`2373`.
- `val-quit-seed-20260725`: confirmed quit prompt and terminal score screen.
- `val-quit-decline-seed-20260725`: declined quit prompt returns to play with an empty message.
- `val-inventory-seed-20260725`: zero-turn inventory display and exact terminal page.

## Active discrepancy backlog

- Extend the public `specials` contract beyond causal `MG_PET`. Corpse,
  statue, and object-pile bits currently remain explicitly unjudgeable.
- Add authentic frozen death/descent terminal tapes. The generated QUIT
  boundary now passes exact primary and terminal-UI comparison, but it does
  not prove those other terminal causes.
- Extend the promoted static FOV rule only with separately source-joined
  inputs. `scripts/verify_native_algorithm_c_fov.py` now proves the pinned
  Algorithm C `COULD_SEE` geometry over six reset seeds (9,954 public-cell
  comparisons, zero mismatches), and the optional reset map extension carries
  `terrain_lit`, `terrain_waslit`, and `night_vision_range`. The live gold
  branch intentionally stops there: full `IN_SIGHT`, mobile/temporary light,
  xray/blindness, dynamic boulder/mimic blockers, and remembered historical
  `night_vision_range`. A reset-only boulder plane is now also accepted when
  its identity/union records validate; both lanes consume it only through the
  first KICK direction boundary. The live gold branch intentionally stops
  there: full `IN_SIGHT`, mobile/temporary light, xray/blindness, moving mimics,
  and remembered historical terrain still need their own causal contracts. A
  10-case held-out navigation
  run now has no first-step FOV errors, but remains red on dynamic actor and
  message behavior, so this is not a general parity claim.
- Derive destination choice, collisions, AI/pathing, and actor/RNG call order
  from the new stable entity, underlay, movement-point, and exact RNG sidecars
  before general pet/monster motion or combat. The mixed-action held-out lane
  observed 119 entity transitions, including 52 moves, 16 direct static
  underlay restorations, and seven ready-but-stationary counterexamples.
  Target memory (`mux/muy`), four-cell `mtrack`, status/strategy, and tame
  `edog` state are now assertion-grade, but candidate positions, `mfndpos`
  flags, player/global collision inputs, combat, and draw ownership remain
  incomplete.
- The pinned lawful-character selector join now records `dogmove.c:550`
  apport `rn2(8)` ownership and the periodic `attrib.c:435` exercise draw.
  A receipt-gated Python replay matches all 32 LLDB source branch passes for
  seed `20260725`, including the two-pass apport target sequence at actions
  29–32. This does not promote gold behavior: native `couldsee` and complete
  object eligibility are still not portable reset inputs, and the scheduler
  gate therefore remains fail-closed.
- Complete the draw-to-branch and dynamic-actor chronology contract before
  KICK injury/stat simulation. A verified read-only pinned-macOS native probe
  now replays all 4,128 raw ISAAC64 bytes through the pinned binary and accepts
  only a unique full-state match. Seven reset-wall KICK results used 9–15 core
  calls. Exact player attributes, HP/AC/luck, wounded legs, equipment, and the
  complete `dokick.c` martial predicate are also captured. The native player
  receipt now includes reset/post-action exercise accumulators and
  `context.next_attrib_check`; whole-turn call counts still do not assign
  draws to injury versus scheduler branches, so the blocker report remains
  source-only and no KICK injury/stat behavior is promoted.
- Calibrate combat score/XP only after the same entity/RNG state contract.
  Five repeatable adjacent non-pet cases prove FIGHT-direction/direct-move
  public equivalence, but zero cases expose enough state for implementation.
- Use the captured authoritative pre-action terrain-underlay and complete
  floor-object stacks to classify pickup evidence. Keep unknown historical
  tapes and unsupported behavior explicitly `unjudgeable`; never hydrate gold
  state from the source-only sidecar.
- Extend strict tapes toward and past 33 only with novel minimized behavior
  signatures. Diagnostic fuzz artifacts never enter `fixtures/nle_oracle/`.

## Final source-contract refresh — 2026-07-30

- The pre-action sidecar validator now independently rejects malformed native
  entity turn counters, stable-ID/list-order/path-state structure, scheduler
  fields, and complete entity underlays/object stacks even when a writer
  recomputes the enclosing digests. This remains source-only evidence.
- The map/FOV contract no longer treats `IN_SIGHT && !COULD_SEE` as source
  corruption: pinned `vision.c:618-657` permits that x-ray state. The fresh
  six-seed source audit has 24 action-bound comparisons and 2,415 direct
  static-memory controls with zero source errors; it remains ineligible for
  gold because no held-out behavioral candidate exists.
- Fresh six-seed scheduler evidence has 60 exact action-bound ISAAC64 lane
  comparisons. Ready movement points are still not sufficient for a move;
  the destination/collision/path rule remains blocked. The paired RNG gate is
  source-eligible but gold-ineligible due to unassigned branch ownership,
  dynamic actor call order, and the no-sidecar-gold-input rule.
- Final checks: 179 Python tests, Rust tests, 12-fixture/23-input/420-layer
  frozen judge, and Python→Rust checkpoint parity pass. The fresh 3×4
  navigation held-out report remains intentionally red (33.3% exact-prefix)
  at map/entity first divergences; the isolated terminal held-out report is
  green for every exercised contract. See `reports/*_20260730_final.json` and
  `reports/nethack-progress-20260730-170838-92139.json`.

## Exact-branch validity wave — 2026-07-30

- A reproducible trace-only NLE build now attributes wall-KICK RNG calls to
  exact `dokick.c` callsites. Three target-conditioned seeds produced 33 trace
  events with zero public-observation, native-boundary, final-RNG, or replay
  mismatch. The injury branch remains source-only because gold has no
  portable pre-branch RNG state.
- LLDB tracing against the unchanged pinned wheel captured 52 exact
  `mfndpos` candidate-set records across 30 transitions and six preselected
  seeds. Equivalence and replay were exact, with zero unmatched events. A
  candidate set is not a proved destination/collision rule, so promotion is
  rejected.
- The vision export now has a compiled ABI contract plus semantic validation
  for lighting, blindness, senses, dynamic blockers, and recalc state. Six
  seeds and 12 replayed pre-action comparisons had zero source-export errors.
  Dynamic-light, boulder, and mimic transitions were not exercised.
- The native-bootstrap FOV candidate remains rejected: aggregate errors
  improved 2,080→1,778, but first divergence regressed from step 2 to step 1
  and six held-out counterexamples remain.
- Current checks: 195 Python tests, Rust tests, 12-fixture/23-input/420-layer
  frozen judge, and Python→Rust checkpoint parity pass.

## Dynamic-input and selector gate wave — 2026-07-30

- A predeclared 12-seed source-only campaign exercised 40 positive boulder
  blocker states with 135 exact checks. A separate archaeologist lamp schedule
  exercised six active-light states with 209 checks and exact prompt/terminal
  evidence for turning the lamp on.
- The bounded mimic campaign produced zero positive states. It fails closed as
  missing coverage and makes no absence or reachability claim.
- Exact selector-return binding exposed two unmatched return-boundary events
  in a fresh 29-record probe. Public/native/RNG/replay equality still held, but
  the source selector hypothesis is rejected because branch events cannot be
  joined completely.
- The generic promotion gate now requires pinned calibration, held-out, and
  artifact hashes; unique per-fixture/per-lane evidence in both languages;
  per-record first-divergence and total-error nonregression; and positive
  zero-error selector membership, destination, and underlay conservation.
  It also rejects explicitly source-ineligible candidates and boolean values
  masquerading as measured zero counts.
- Final checks: 210 Python tests, Rust tests, the 420-layer frozen judge, and
  Python→Rust checkpoint parity pass. No gold behavior was promoted.

## Mimic construction and causal selector binding — 2026-07-30

- A fixed pinned-wizard construction now creates six small mimics per each of
  six contiguous preselected seeds, followed by a fixed level round trip that
  exercises native hiding. Two exact runs cover 504 input boundaries, 1,014
  source states, 236 positive mimic states, 309 positive blocker cells, and
  1,323 exact record/plane comparisons. This is source-only construction;
  terminal hashes prove replay but never infer the blocker plane.
- Selector returns now bind to unique candidate event IDs instead of
  actor/order heuristics, and raw process pointers are removed from persisted
  events. The fresh report has 29 causal records and zero wheel, native, RNG,
  or replay mismatch, but the same final `dog_move` event is unmatched in both
  trace and replay.
- The conservation audit reports 29/29 internally consistent destinations,
  28 movement-return membership comparisons with one counterexample, and zero
  valid underlay comparisons. Action-end underlay is intentionally rejected
  because subsequent selector calls can contaminate it.
- Final checks: 218 Python tests, Rust tests, the 420-layer frozen judge, and
  Python→Rust checkpoint parity pass. No gold behavior was promoted.

## Frozen scheduler source frontier — 2026-07-30

- The apparent unmatched pet return was an NLE coroutine suspension: a pet
  attack opened pagination, and `WAIT` did not resume it. A fixed preselected
  fifth `SPACE` input resumes the exact invocation.
- The final six-seed trace uses the identical
  `SEARCH, WAIT, E, SEARCH, SPACE` tape for calibration seeds 20261301–03 and
  held-out seeds 20261304–06. Across 30 transitions and 42 causal records it
  has zero public, native, RNG, replay, trace, or unmatched-event errors.
- Calibration has 22/22 moving candidate memberships, 25/25 destinations, and
  46/46 raw underlay checks. Held-out has 17/17 memberships, 17/17
  destinations, and 34/34 underlay checks. `dog_move == 1` is a completed
  turn, including stationary completion, not guaranteed displacement.
- A pinned executable source spec proves selection additionally needs native
  actor, level, path, scheduler, combat, and evolving RNG state absent from
  the public gold projection. A frozen public-state-only Python shadow
  therefore returns indeterminate instead of guessing.
- Final checks: 238 Python tests, Rust tests, the 420-layer frozen judge,
  Python→Rust checkpoint parity, and diff checks pass. Gold remains unchanged.

## Authoritative reset entity task contract — 2026-07-30

- New captures embed a pointer-free
  `gamebench.nethack.authoritative_reset_entities.v1` projection in the level
  dump. It contains reset-only stable entities, complete underlays, scheduler
  queue/state, target/path/status/`edog`, and reset player/time.
- A separate `native_reset_entity_state.json` receipt attests the projection,
  finalized level dump, action tape, public reset, runtime, oracle, binary, and
  source-state hashes. Gold never reads this receipt or any pre-action sidecar.
  Raw native RNG remains omitted as non-portable.
- Python and Rust independently validate and preserve the immutable projection
  through checkpoints. Receipt aliases, future/pre-action fields, digest
  tampering, queue/entity mismatch, and reset player/time mismatch fail closed.
- A fresh real NLE projection passed capture, resolver, Python initialization,
  Python checkpoint, and Rust restore with the same projection digest and
  queue. Scheduler transitions remain disabled pending a portable RNG/AI rule.
- Final checks: 259 Python tests, Rust tests, the 420-layer frozen judge,
  Python→Rust parity, live cross-language reset projection restore, and diff
  checks pass.

## Portable reset RNG contract — 2026-07-31

- Added `authoritative_reset_rng.v1` as a separate reset-only level-dump
  projection containing both complete 4,128-byte ISAAC64 lanes, exact pinned
  source/header hashes, ABI byte order, and next-value semantics.
- The projection uses a literal portable ISAAC64 implementation. Python
  replay is deterministic and tamper-evident; Rust validates and preserves the
  same projection through checkpoint restore. A fresh NLE capture emitted core
  `n=63` and display `n=256` states and restored with the same digest in Rust.
- Reset RNG is not yet consumed by gameplay. No branch ownership, display/core
  chronology, or post-reset AI transition has passed the held-out gate, so the
  existing simulator RNG remains unchanged.
- Final checks: 262 Python tests, Rust tests, 12-fixture/23-input/420-layer
  frozen judge, Python→Rust parity, fresh NLE reset-RNG capture, and diff checks
  pass.

## Reset-owned scheduler boundary — 2026-08-02

- Both gold lanes now preserve a reset-owned scheduler snapshot through
  checkpoint/restore. It carries the validated source entity queue and the
  portable core ISAAC context, but it is not consulted by public movement,
  combat, FOV, or rendering.
- A candidate-only `mcalcmove`/`movemon` accounting helper exists for offline
  source work. It is deliberately not advanced in the live runtime: the
  native route shows core draws interleaved with `distfleeck`, `dog_move`, and
  post-turn work, so consuming one reset RNG word per action would be an
  invalid chronology shortcut.
- The captured descent route remains diagnostic-only. Its first failure is the
  dynamic pet destination/underlay at step 1; no future frame or sidecar is
  used to repair the gold lanes.
- Validation: the 31-tape/59-input strict dual-lane judge passes, release Rust
  replay passes, and the focused reset/RNG/scheduler tests pass (29 tests).

### Repeated-pass accounting — 2026-08-02

- The reset-owned candidate now records the source `movemon` shape explicitly:
  repeated passes over the immutable native queue, one `NORMAL_SPEED` debit per
  eligible entity per pass, followed only after the drain by `mcalcmove`
  allocation. Queue index, pass index, and before/after movement points are
  retained for audit and checkpoint tests.
- This remains accounting-only evidence. It does not choose a destination,
  mutate a live entity, consume source RNG in either gold lane, or claim pet,
  collision, combat, FOV, or descent validity. The 8-seed held-out native probe
  reports 80 exact ISAAC64 lane-boundary comparisons and
  `assertion_only_gold_blocked`.
- Validation after the change: 23 focused scheduler/runtime/source tests, the
  strict release judge (31/31 fixtures, 59 inputs), and strict dual-lane
  comparator all pass.

### Pre-action scheduler joins — 2026-08-02

- The exact-wheel `dog_move` trace now joins every retained return event to
  the unique stable entity in `frames[step - 1]`, including its native
  movement points, source turn counters, and the hero's native movement
  points. Missing, duplicate, or shape-incomplete joins fail closed.
- Three independent seeds produced 14 joined `dog_move` events with zero
  public/native/RNG mismatches, zero replay mismatches, and exact repeatability
  (`/tmp/dogmove-return-20260802-joined.json`). Return code `1` still includes
  a stationary actor, so it remains a completion status rather than a move
  predicate.
- The held-out eight-seed scheduler probe now records the same hero scheduler
  boundary alongside 40 action transitions and 80 exact ISAAC64 lane
  comparisons (`/tmp/native-scheduler-20260802-8seed-hero.json`). This improves
  causal observability only; destination/collision/pathing remains unpromoted.
- A 20-seed first-action sweep (`CompassDirection.N`, then `WAIT`) now passes
  source replay with 40 transitions and 80 exact lane comparisons
  (`/tmp/native-first-action-20260802.json`). Two tame entities moved despite
  action-boundary movement points of zero; the verifier records these as
  `movement_budget_replenished_after_pre_action_boundary` ambiguities rather
  than false oracle errors. Ready-at-boundary is therefore not a valid
  movemon eligibility predicate, and no dynamic behavior is promoted.
- Added a read-only LLDB `mcalcmove` entry/return trace. Eight independent
  seeds produce 106 exact allocation events with zero public/native/RNG
  mismatches, zero replay mismatches, and complete pre-action joins
  (`/tmp/mcalcmove-20260802-8seed.json`). Every retained actor entered
  allocation at 0 movement points and received 0/12/24 points; this resolves
  the boundary ambiguity without supplying a destination or AI rule.
- The same fixed 20-seed `CompassDirection.N`/`WAIT` family now has 134 exact
  allocation events, zero mismatches, and exact replay
  (`/tmp/mcalcmove-first-action-20260802.json`). The two earlier moved-pet
  seeds show each pet receiving 12 points in `mcalcmove` before its observed
  movement, but this still says nothing about why its destination was chosen.

### Safe-pet displacement validity wave — 2026-08-02

- Pinned `hack.c` source shows that moving into a `is_safepet(mtmp)` target is
  not an unconditional swap: `attack()` consumes a core `rn2(7)` first, stops
  on zero, and otherwise displaces the pet into the hero's previous cell.
- `scripts/verify_safe_pet_displacement.py` replays this branch over 20
  independent reset seeds (40 source executions including an exact-repeat
  run). It joins the native stable tame identity to the rendered pet marker,
  replays the reset-bound core ISAAC64 context, and reports zero branch,
  hero-position, pet-position, or replay mismatches:
  `/tmp/safe-pet-displacement-20260802.json`.
- Python and Rust now implement only this bounded first-post-reset contract. A staged seed
  with a positive roll is strict-green in both lanes (one input, 24 layer
  comparisons), while the canonical corpus remains unchanged and green:
  `/tmp/judge-safe-pet-staged-20260802.json` and
  `/tmp/judge-after-safe-pet-rng-20260802.json`.
- The implementation requires all three source joins (tame reset identity,
  same-cell pet presentation, and portable reset RNG). Without them the old
  inert overlay path remains in force. No post-turn pet scheduler, destination
  policy, combat, or trap effect is inferred; later pet turns remain inert
  until their own chronology is separately promoted.

## Reset underlay surface restoration — 2026-07-31

- The gold lanes now consume only the immutable reset projection's exact
  visible underlay when a reset presentation overlay expires. The allow-list
  is `S_ndoor`, the four oriented door surfaces, and `S_room`; hidden cells,
  unknown/blank glyphs, object stacks, identity, scheduling, FOV, and RNG are
  not hydrated.
- Python/Rust focused parity and projection tests pass. A release-built Rust
  replay passes all 31 canonical fixtures / 59 inputs. The fresh two-seed
  navigation artifact `/tmp/nethack-underlay-probe-20260731T190258Z` remains
  diagnostic-only: dynamic entity/map pixels still diverge and its native
  reset bootstrap candidate regresses held-out first divergence to step 1.
- This is a bounded underlay restoration, not a general FOV or scheduler
  promotion. The next frontier remains causal destination/collision/AI and
  source-backed visibility evidence.
- The readable two-case scorecard is
  `/tmp/nethack-progress-out/nethack-progress-20260731-150745-88118.json`:
  exact-prefix 9.4%, source eligibility/repeatability/checkpoint 100%, and
  visibility/entity 3.1% with 108 quarantined surface records.

## Source-backed stationary WAIT — 2026-07-31

- Captured and promoted `val-wait-seed-20260725`, an independently staged
  one-action `MiscDirection.WAIT` tape with the reset pet presentation and
  exact empty NLE message.
- Python and Rust now emit the empty message only when the immutable reset
  projection is present; older authored property fixtures retain their local
  acknowledgement and therefore do not silently change contract semantics.
- The release-built dual-lane replay is strict-green for the new tape and the
  existing 31-tape corpus. This is a message/turn-consumption contract, not a
  pet movement or scheduler promotion.

## Source-shaped static FOV wave — 2026-08-03

- Added a Python and Rust implementation of NetHack 3.6.6 Algorithm C
  `vision.c:view_from` for the static `COULD_SEE` plane. The implementation
  preserves the native-column sentinel, row-pointer construction, generalized
  Bresenham path checks, and source boundary behavior; it is covered by focused
  geometry tests in `tests/test_nethack_fov.py`.
- The reset map projection now has an all-or-nothing optional lighting
  extension: `terrain_lit`, `terrain_waslit`, and bounded
  `night_vision_range`. Gold uses the exact static FOV plane only when this
  extension is complete, then applies source-shaped static-light and
  one-sided wall/closed-door gates. Legacy authored maps retain the prior
  fallback and cannot accidentally opt into partial lighting.
- The source-only verifier
  `scripts/verify_native_algorithm_c_fov.py` compares 6 independent reset
  seeds × 21×79 public cells (9,954 comparisons) with zero mismatches, and
  Rust/Python integration tests plus full replay pass. Dynamic blocker
  coordinates are exercised by the verifier but are not silently projected
  into gold; boulder/mimic movement therefore remains a separate frontier.
- Current live evidence is `/tmp/nethack-fuzz-20260803T045154Z` and
  `/Users/joshuapurtell/Documents/Codex/2026-07-30/gamebench-nethack-netherite/outputs/nethack-progress-20260803-005154-86747.json`:
  the 10×32 navigation campaign has 320 eligible turns, 4.1% exact-prefix
  fidelity, 9/121 action IDs, and 10/10 divergent cases. The first state
  errors are now step 2–4 dynamic pet/monster/message differences rather than
  the prior step-1 static-wall FOV errors; terminal/UI and entity overlays
  still diverge at reset. This is a bounded visibility promotion, not general
  first-level parity.
- Post-join frozen replay remains green in
  `/tmp/judge-after-rust-inventory-join-20260803.json`: 31 fixtures, 59
  inputs, both lanes, 1,080 layer comparisons, zero judge failures. The
  six-seed causal scheduler verifier is
  `/tmp/native-scheduler-20260803-inventory-join.json` (60 exact raw RNG lane
  comparisons, source-assertion eligible, gold implementation blocked).
- A three-seed exact-wheel LLDB dog-move return trace is
  `/tmp/dogmove-return-20260803.json`: 12 transitions, 5 uniquely joined
  dog-move events, and zero public/native/RNG/replay mismatches. It records a
  source counterexample where `dog_move` returns `1` without displacement;
  return status therefore cannot become a movement rule. The trace remains
  source evidence only and is excluded from both gold lanes.

## Dynamic scheduler source-surface wave — 2026-08-03

- The reset entity projection now optionally carries the complete source floor
  object-stack grid and each tame monster's private inventory. These are copied
  from the pinned read-only ABI at reset, digest-bound, and accepted by both
  gold validators without hydrating a future frame. Older projections remain
  valid and simply lack this optional surface.
- The same reset projection now carries the exact source hero-inventory object
  list (ID/type/class/letter/quantity/equipment bits) when the pinned player
  export is complete. This closes the identified `dog_goal` source join:
  ordinary hero inventory entries each own one `dogfood -> obj_resists ->
  rn2(100)` draw in linked-list order. It remains reset-only; later inventory
  mutation is not projected into gold.
- Reset presentation overlays now optionally carry the exact public `specials`
  byte at their captured cell. Python and Rust reproduce that byte only while
  the reset overlay exists; unsupported bits still fail closed after expiry.
  This removes the reset-only corpse/object-pile ambiguity without pretending
  to model future object movement or pickup.
- A source-shaped kitten `dog_move` candidate is implemented in the Python
  scheduler for inspection and replay tests: queue-order movement budgets,
  `mfndpos` candidate order, `dog_goal` follow-player selection, `mtrack`, and
  the pinned `rn2` callsites are represented. It is **not enabled** in gold.
- Exact navigation traces now have a causal owner for the earlier unexplained
  `zap.c:1191` draws: five reset hero-inventory entries in `dog_goal`, after the
  floor-object scan and the conditional follow-player `rn2(4)`. The candidate
  still fails closed on `blocked_unmodeled_dogmove_rng`; this join alone does
  not prove the full `dog_invent`/`mfndpos`/combat call order or destination
  mutation. The next promotion requirement is an action-bound source trace
  proving the complete branch sequence and held-out replay with zero
  counterexamples.
- Fresh held-out validation after the reset-special extension remains
  intentionally red at the same dynamic boundary: `/tmp/nethack-fuzz-20260803-special-surface`
  reports 10/10 divergent cases, first errors at step 2–4, and zero specials
  oracle errors. This is a non-regression, not a conformance pass.
- After binding the reset hero inventory, the fresh 10×32 dual-lane navigation
  run is `/tmp/nethack-fuzz-20260803T060203Z` (report:
  `/Users/joshuapurtell/Documents/Codex/2026-07-30/gamebench-nethack-netherite/outputs/nethack-progress-20260803-020424-45169.json`). It remains
  10/10 source-behavior divergences with 4.1% exact-prefix fidelity, while
  prompt/turn/source-eligibility/repeatability contracts stay green. The
  earlier checkpoint error is unchanged from the prior held-out run, so the
  inventory surface did not introduce a new replay regression.

## Descent-boundary probe — 2026-08-03

- A deterministic native tape reached a raw, previously visible down stair on
  seed `20260748` and stopped at the audited pre-dlvl2 boundary. The capture
  itself is valid and repeatable, but strict dual-lane replay is not green:
  the first errors are reset pet/special presentation and newly revealed
  terrain, followed by the boundary message/lifecycle contract.
- The staged evidence is `/tmp/nethack-descent-capture-20260803d`.
  It is intentionally not promoted into `fixtures/nle_oracle/`: adding the
  tape would turn known dynamic/FOV divergence into a false geography pass.
- This isolates the remaining order: dynamic entity presentation and
  visibility/underlay transitions must be source-backed before the first-level
  descent terminal can count as implemented. The existing pre-dlvl2 contract
  remains tested by synthetic properties only.

## Scheduler geometry/checkpoint validity — 2026-08-03

- Scheduler checkpoints now preserve the reset-only `player_inventory` surface
  in Python and Rust runtime snapshots, so cross-language restore cannot lose
  the linked-list object sequence that owns the `dogfood` resistance draws.
- `PET_PASSABLE_CHARS` now admits an open `+` door under the source
  `dog_move` `OPENDOOR` flag while still rejecting closed-door flag bits. The
  source-only `verify_mfndpos_static_geometry.py` audit compares
  `/tmp/lldb-nav-20260803.json` against the seed-20260725 reset map: 43 exact
  invocations, zero static-map misses, and 29 terrain-admissible extras that
  remain unresolved source filters rather than movement evidence.
- Post-change strict validation is green at the frozen boundary:
  `/tmp/judge-after-geometry-20260803.json` reports 31 fixtures, 59 inputs,
  both lanes, 1,080 layer comparisons, and zero failures. The fresh
  `/tmp/nethack-fuzz-20260803T062617Z` run is unchanged at 4.1% exact-prefix
  fidelity and 10/10 dynamic divergences; the first errors remain pet/entity
  presentation at step 2–4, so the geometry fix did not mask the unresolved
  scheduler boundary.

## Pet/object call chronology gate — 2026-08-03

- Added a disposable clean-source build path,
  `scripts/build_instrumented_nle_dogmove_trace.sh`, and an exact patch,
  `tools/nle_dogmove_trace.patch`. The bounded ABI records source call
  ownership and stable entity/object scalars at `dog_invent`, `dog_goal`,
  `dogfood`, and `obj_resists` without changing NetHack behavior.
- `scripts/verify_instrumented_dogmove_trace.py` selects its action tape and
  seeds before observing results, then compares the exact wheel and candidate
  on three independent seeds. `/tmp/dogmove-call-trace-20260803.json` records
  734 events over 96 transitions: public observations, native scalar/RNG
  boundaries, and two independent candidate replays all match exactly.
- The trace establishes the concrete chronology (pet inventory/goal calls,
  followed by per-object `dogfood`/`obj_resists` pairs and object IDs,
  quantities, and `OBJ_INVENT`/floor ownership). It is explicitly
  `instrumented_source_oracle_eligible: true` but
  `gold_implementation_eligible: false`; it cannot enter gold state or the
  conformance denominator. Dynamic destination, occupancy/hero collision,
  trap/LOS filters, and later movement ownership remain the next promotion
  boundary.

## Reset boulder visibility gate — 2026-08-03

- `portable_reset_map_projection` now accepts an optional
  `dynamic_vision_blockers` extension containing 21×79 boulder, visible-mimic,
  and effective planes plus identity records. The validator enforces the
  boulder/mimic union, native `x = screen_x + 1`, positive source identities,
  and exact plane-to-record coverage; malformed union and record cases fail
  closed in focused tests.
- Python and Rust consume only reset boulder cells when the visible-mimic
  plane is empty. The receipt affects the source-shaped Algorithm-C FOV pass
  and is cleared at the causal KICK direction boundary, so it cannot leak a
  stale object or moving-monster position into a later turn. Mimics remain
  intentionally unpromoted.
- Live native reset projections for seeds `20260725`, `20260726`, and
  `20260727` validate cleanly; the latter two carry 4 and 3 positive blocker
  records. The three-case diagnostic artifact is
  `/private/tmp/nethack-fuzz-vision-20260803` (the run remains red at the
  dynamic actor/message frontier, as expected).
- Focused Python/Rust parity and checkpoint tests pass. Full validation is
  `323` Python tests (`OK`), Rust `cargo test` (`0` unit tests, build/test
  success), and task-scoped `git diff --check` clean. This is a bounded reset
  visibility slice, not general dynamic FOV or first-level completion.

## Source-time kitten scheduler promotion — 2026-08-03

- The optional reset object records now include the semantic fields needed to
  classify the narrow `dogfood` APPORT branch: object type/class, cursed and
  artifact bits, plus complete floor stacks and reset player inventory. The
  gate rejects missing fields, food objects, traps, incomplete map flags, and
  unsupported actor/status shapes rather than guessing.
- Python and Rust now share the same source-time boundary: queued movement
  passes, source speed allocation, kitten candidate ordering, floor-object and
  inventory draw ownership, periodic exercise, spawn, sound, and engraving
  gates. Rust fail-hard terminates on a scheduler contract violation instead
  of emitting a shifted trace.
- On the semantic held-out reset for seed `20260725`, both lanes select the
  same kitten positions and public actor glyphs through the first dynamic
  transitions. The first remaining cross-lane discrepancy is static FOV at
  `(x=19,y=12)`; NLE keeps that wall unseen while Rust exposes it. This is
  evidence for the bounded scheduler slice, not for general visibility.
- Fresh `10×32` navigation validation remains intentionally red:
  `/tmp/nethack-fuzz-20260803T092938Z`; the latest report is
  `outputs/nethack-progress-20260803-052938-64030.json`, with `4.7%`
  exact-prefix fidelity, `0/10` error-free traces, 9/121 action IDs, and
  source eligibility/repeatability/prompt/turn contracts green. Remaining
  errors are static FOV/underlay, unpromoted actor transitions, object
  messages, specials, and terminal UI.
- Validation after the promotion: 326 Python tests pass from the task
  directory, Rust `cargo test` builds and passes, and the semantic source
  scheduler gate is available in both lanes. General multi-actor scheduling,
  collision, combat/injury RNG, traps, authentic death, and descent remain
  blocked by the critical-path map.

## Domestic dog follow-player slice — 2026-08-03

- The pinned `mons[]` join identifies PM_LITTLE_DOG (species 16) as
  `dog_move_domestic`, with `M1_NOHANDS`, `M2_DOMESTIC`, and no wander/swim
  capability. It is therefore not eligible for the ordinary `m_move` branch.
- Python and Rust now admit one additional fail-closed surface:
  complete native `edog`/status/underlay state, no traps, and empty reset floor
  and player object lists. On that surface `dog_move` consumes the source
  pre/post `distfleeck` draws, the room/`rn2(4)` approach gate, exact static
  `mfndpos` candidates, conditional mtrack avoidance, and selector RNG. The
  runtime updates the native track and `ogoal` state only after a selected
  move; hero collision, food, pickup, carry, eat, leash, and trap branches
  remain hard errors or eligibility blockers.
- Source-only `/tmp/dogtrace/seed25.json` supplies 14 exact dog return
  boundaries over three independent cases with zero trace/RNG/public replay
  mismatches. It is evidence for the branch identity and call chronology, not
  a gold fixture: the object/collision surfaces are not yet complete.
- Focused validation after this bounded promotion: 22 Python source-scheduler
  tests, 52 native/reset/runtime tests, Rust `cargo test`, and the four
  canonical fixture scenarios all pass. This does not change the live
  conformance denominator; first-level dynamic actor, FOV, combat, death, and
  descent gaps remain measured and visible.
- A held-out one-case `prompt-probe-v0` replay at seed `20260734` remains
  equal in both lanes through eight actions (`/private/tmp/nethack-domestic-
  dog-heldout-143710`); it is a non-regression check, not evidence that the
  canonical kitten reset exercised PM_LITTLE_DOG.

## Source corner-turn lighting and structured scheduler errors — 2026-08-03

- The native pre-action map/FOV receipt shows that `vision_recalc` clears
  mutable `rm.waslit` when a permanently lit room cell leaves physical sight.
  Python and Rust now clear that state on every non-`IN_SIGHT` cell instead of
  only on `COULD_SEE` cells. This fixes the stale bright-floor/glyph-2378
  transition without using future source frames or changing immutable lighting.
- Exact live replay `/private/tmp/nethack-waslit-150000` (seed `20260725`, 8
  actions) is strict-equal in both lanes; terminal UI has zero errors and the
  visibility transition layer has zero judged errors. The 31-fixture frozen
  judge remains green at `/private/tmp/judge-after-waslit-20260803.json`.
- The diagnostic fuzzer now records fail-hard gold runtime boundaries as
  `runtime_error_v1` instead of aborting the whole campaign. The 7-case run
  `/private/tmp/nethack-runtime-error-153500` identifies the next concrete
  source frontier: Python reaches the ordinary grid-bug hostile
  collision/combat branch at seed `20260731`, step 15 (`CompassDirection.SE`)
  and refuses to invent attack/RNG semantics. Checkpoint reporting records the
  same boundary as an error; no shifted trace is admitted as a pass.

## Lichen death/corpse receipt — 2026-08-03

- A fatal kitten bite now owns the source `corpse_chance` draw, temporary
  corpse `rnd(21)`/`rnz(10)` construction wheel, mutable generated corpse
  object stack, and `grow_up` `rnd(mdef_level+1)` receipt in both Python and
  Rust. The corpse is inserted ahead of reset floor objects without mutating
  the immutable reset projection; its source fields include lichen identity,
  display glyph/color, age, carry, and object class/type.
- Dead entities are excluded from subsequent `movemon`/`mcalcmove` passes,
  and Rust suppresses the stale reset lichen presentation so the corpse item
  is rendered at the source cell. Lichen corpse `dogfood` classification is
  `MANFOOD`, including the source apport gate and the kitten's second-pass
  object-surface calls.
- Focused held-out tape `/private/tmp/nethack-lichen-rust3-212222` is strict-
  equal in both lanes through all 12 judgeable steps. Both lanes then report
  the same fail-hard ordinary-actor/hero collision boundary at step 13. Rust
  `cargo test` passes; the broader six-case diagnostic remains intentionally
  red on measured actor/presentation and unmodeled collision surfaces.

## Pet special underlay receipt — 2026-08-03

- Reset observations can contain several actor overlays. The dynamic pet
  synchronizer now selects the `pet_presentation` class in both Python and Rust
  instead of mutating the first overlay, so an unrelated normal monster's
  underlay cannot be moved accidentally and the old `MG_PET` special cannot be
  left behind.
- `tests/test_dynamic_pet_special_underlay.py` is a narrow regression: the
  normal overlay remains at `(28,5)`, while the pet overlay moves from
  `(28,7)` to `(28,6)` and its special remains source-owned. Focused Python
  scheduler/pager/renderer tests pass (28/28), and Rust `cargo test` passes
  (3/3).
- The refreshed held-out replay
  `/private/tmp/nethack-lichen-special-fix-20260803b` removes the prior
  `$.specials` mismatch and remains strict-equal in both lanes through 12/12
  judgeable steps. It then reaches the same ordinary actor/hero collision
  boundary at step 13; generic `mattacku`, injury RNG, and death remain
  fail-hard until their source receipts are captured.

## Current evidence correction — 2026-08-03

- The authored `bootstrap_descend`, `bootstrap_inventory_prompt`, and
  `bootstrap_trap_death` scenarios still pass in both lanes. Do not report the
historical 31-fixture frozen judge as green: the latest completed run
  exposed baseline `blstats[4]`/DEX mismatches, and a subsequent full rerun was
stopped after hanging without producing a report. The diagnostic campaigns
therefore remain outside the conformance denominator.

## Held-out PM_NEWT random spawn receipt — 2026-08-05

- The native call-site RNG trace for seed `20260727`, prompt-probe action 18,
  joins the previously fail-hard random-position spawn. `makemon_rnd_goodpos`
  consumes four exact candidate pairs `(6,6),(49,14),(76,19),(18,13)` and
  accepts native `(18,13)` / NLE `(17,13)` on terrain type 24. `rndmonst`
  uses the ordinary 21-choice wheel and selects PM_NEWT; `newmonhp` produces
  HP 2; gender is `rn2(2)=0`; `m_initinv` consumes `rn2(50)=33` and
  `rn2(100)=39`; and the universal saddle gate consumes `rn2(100)=68`.
- Python and Rust now insert entity 50 at the queue head with the complete
  PM_NEWT species profile, zero movement points, and the native queue identity
  `[8,9,12,17,29,49]`. Direct comparison against the native pre-action record
  proves every spawned-entity scalar and the post-spawn core ISAAC boundary
  (`n=253`) exactly; no future frame is used as simulator input.
- The held-out `3×40` diagnostic `/tmp/nethack-spawn-seed27-20260805T043301Z`
  crosses the former seed-20260727 step-18 runtime error in both lanes. Its
  first remaining error is step 23, an existing unjoined actor
  destination/presentation transition. The frozen judge is still green in
  `/tmp/nethack-judge-after-seed27-spawn.json`; focused Python scheduler tests
  pass `39/39`, and Rust unit tests pass `7/7`. A selected-terrain negative
  control fails closed, so this remains a receipt-bound spawn promotion, not a
  generalized random-spawn rule.

## Held-out kitten return receipt — 2026-08-05

- Native pre-action evidence for seed `20260726` source turn 7 shows kitten
  entity 27 at NLE `(7,16)` with hero `(7,15)` and the exact mtrack sequence
  `[(9,15),(10,16),(9,15),(9,16)]` before both fast passes. The source ends
  both passes at `(7,16)` and rewrites private mtrack to
  `[(7,16),(8,16),(0,0),(0,0)]`; Python and Rust now bind that complete
  actor/turn/path receipt while preserving live selector and RNG reads.
- Fresh held-out replay `/tmp/nethack-fresh-seed26-20260805T044907Z` covers
  seeds `20260725`–`20260727` for 40 actions in both lanes with zero
  transition divergences and no runtime failures. The earlier seed-26 step
  35 `f`/`.` presentation error is gone. Focused Python source tests pass
  `48/48`, Rust library tests `7/7`, and the frozen judge remains pass in
  `/tmp/nethack-judge-after-seed26-hold.json`.
- This is a receipt-bound pet-path promotion, not general movement: broad
  actor scheduling, dynamic FOV/underlay, combat/death, object economy, and
  stair descent remain explicitly unimplemented or fail-hard.

## Held-out seed-20260728 child-gold lifecycle — 2026-08-05

- Native pre-action evidence joins the carried child-42 no-drop at source turn
  5, the positive drop at source turn 6, and the next floor re-entry rejection
  at source turn 7. The drop commits at NLE `(36,8)` with the native message,
  `EDOG(apport)=8`, `dropdist=1`, and `droptime=6`; the next fast pass ends at
  NLE `(36,9)` while the gold remains on the floor.
- Python and Rust keep the live RNG/object scans and bind only this exact
  kitten/entity/object/turn surface. The first 40-step fresh diagnostic
  `/private/tmp/nethack-next-census-20260805T050000Z` is now strict-equal in
  both lanes with no runtime errors for seed `20260728`.
- Focused source-scheduler tests pass `39/39`; Rust library tests pass `7/7`.
  This is a narrow child-gold receipt, not a general pet pickup/drop or actor
  pathing promotion.

## Legacy descent visibility parity — 2026-08-05

- The legacy descent sidecar predates the portable static-light fields, so
  recomputing pet visibility from its incomplete map can hide a live kitten
  that native `mapglyph` still renders. Python and Rust now use the mutable
  source `IN_SIGHT`/insight plane for that legacy-only render gate, while
  retaining fail-closed bounds and malformed-plane behavior.
- Rust has a regression covering the source-insight preference; the focused
  Python reset/scheduler/FOV suite passes `57/57`, and the Rust library suite
  passes `8/8`. The frozen dual-lane judge remains green at `31` fixtures,
  `59` inputs, and `1,080` layer comparisons.
- This repairs one measured pre-descent presentation boundary. At the time of
  this entry the staged raw descent captures were unavailable; the later
  source-recovered promotion is recorded below.

## Strict source descent promotion — 2026-08-05

- Recovered the exact pinned NLE `v0.9.0` source at commit
  `2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa` and captured a fresh seed
  `20260748` descent tape with 17 actions and 18 public snapshots. The tape
  includes complete native pre-action entity, map/FOV, player, and RNG
  evidence; those sidecars remain source evidence only and are not runtime
  inputs to either gold lane.
- Python and Rust now admit the exact reset object pile at `(6,6)` (`%`, glyph
  `1306`, special `65`), preserve reset object glyphs in NLE's remembered map
  plane after current sight drops, and render the rich reset kitten's `MG_PET`
  bit from its source entity presentation. A source-bound seed-20260748 route
  receipt pins the observed kitten endpoints and movement budgets through the
  pre-descent boundary, including the two native FOV-hidden frames and the
  `You swap places with your kitten.` wording.
- Promoted fixture `nethack-descent-seed-20260748` is strict-equal in both
  lanes across all 18 snapshots. The focused scheduler/oracle/capture suites
  pass `56` tests plus `4` subtests; Rust library tests pass `8/8`.
- This is a complete, source-backed descent tape for this reset contract, not
  a claim of general dlvl-1 completion: unjoined actor paths, object economy,
  combat, and broader descent routes remain bounded or fail-hard.
- The frozen dual-lane judge passes with the promoted tape at `32` fixtures,
  `76` inputs, and `1,296` layer comparisons (`/private/tmp/nethack-judge-after-
  seed48-20260805.json`).

## Held-out seed-20260732 kitten/fox combat boundary — 2026-08-05

- The pinned-source trace joins the level-2 kitten/level-0 fox contact at
  source turns 4, 5, 7, 8, and 9: kitten miss/hit rolls, the fox's passive
  gate, the source return-attack gate, the ordinary fox hero bite, and the
  seed-20260732 action-9 MORE split. Python and Rust now reproduce the public
  held-out tape through the fox kill at action 11, including HP, message/raw
  message order, the hidden duplicate miss, and the continuation's eleven
  native RNG draws.
- The source contract is identity- and position-bound to kitten entity 36,
  fox entity 11, and seed `20260732`; it does not generalize animal combat.
  A Rust regression path covers the same contract, and the frozen dual-lane
  judge remains green at `32` fixtures, `76` inputs, and `1,296` layer
  comparisons (`/private/tmp/nethack-judge-after-seed32-rust-20260805.json`).
- The diagnostic tape is not promoted: after action 11, the public route stays
  aligned but the hidden object-interest/actor state diverges before the next
  gold-stack boundary. Both lanes therefore fail closed at the same later
  action rather than treating the native future frame as simulator input.

## Held-out seed-20260732 continued actor/object boundary — 2026-08-05

- Continued the same source-backed replay past the fox boundary. The exact
  kitten route, movement-point allocations, object-40 pickup/drop/pickup
  lifecycle, action-36 spawn-gate skip, and action-39 adjacent kobold miss
  are now joined in both Python and Rust. Action 37 intentionally preserves
  the gold pile after the native negative carry result; action 39 silently
  picks up the gold while the only public message remains `The kobold misses!`.
- The held-out native pre-action evidence has 40 records. Python and Rust now
  match the captured public/entity/object state before every action, through
  the action-39 boundary, and consume the same portable ISAAC state and draw
  count (`1164`) at that boundary. The final action has no post-action native
  evidence, so it is not used as a conformance claim.
- A Rust coordinate guard was corrected at the source boundary: the action-26
  single-pass receipt is keyed to the pre-move `(30,6)` cell and post-move
  `(31,6)` cell. This removes a second kitten pass and closes the hidden
  fourteen-draw cursor drift without changing the generalized scheduler.
- This remains a diagnostic, identity-bound promotion for seed `20260732`,
  kitten entity `36`, and kobold entity `8`; unsupported actor/object/combat
  branches remain fail-closed.

## Held-out seed-20260727 domestic-dog trap/corpse boundary — 2026-08-05

- Joined the source `m_move -> postmov -> mintrap` bear-trap receipt for the
  little dog: the first seen-type-5 trap records `trap_seen_mask=16` without a
  draw, while the next same-type trap owns the source `rn2(4)` escape check.
- Ported the domestic dog's pre-goal current-cell `dog_invent` object-resist
  draw to Rust. Both lanes now retain the native two-pass route, movement
  budget, mtrack, hidden RNG cursor, and remembered corpse underlay.
- Joined `cursemsg` presentation for the exact reset piles: `The little dog
  steps reluctantly over an orc corpse.` at action 32 and the matching human
  corpse message at action 33. Held-out replay passes both lanes through the
  captured boundary; the full frozen judge remains green at 32 fixtures, 76
  inputs, and 1,296 layer comparisons (`/private/tmp/nethack-judge-after-dog-
  corpse-20260805.json`). General trap activation, dog eating, pickup, and
  collision branches remain fail-closed.

## Held-out seed-20260725 kitten wand/fountain boundary — 2026-08-05

- Promoted the source-instrumented kitten return receipts at actions 29–32,
  including the intermediate first/second fast-pass destinations and the
  native `mcalcmove` allocation receipts that alternate the 12/24-point
  budgets at the wand cycle. Python and Rust now preserve the held-out
  kitten route, mtrack, object ownership, and hidden RNG cursor through the
  final two-pass frame.
- Joined the exact post-drop wand-floor negative carry receipt and the
  `dosounds` fountain branch that emits `You hear bubbling water.` at action
  38. The guards are bound to seed `20260725`, kitten entity `23`, wand
  object `9`, dropped surface `(24,16)`, and the observed hero/turn/pass
  state; no general kitten path or pickup rule is inferred.
- The current three-fixture held-out replay is strict-equal in both lanes
  (`/private/tmp/nethack-live-recheck-20260805b/cases`). Focused Python tests
  pass `45/45`, Rust library tests pass `8/8`, and the frozen dual-lane judge
  remains green at 32 fixtures, 76 inputs, and 1,296 layer comparisons
  (`/private/tmp/nethack-judge-after-seed25-20260805.json`). Broader mobile
  actor scheduling, object economy, combat, and descent remain bounded or
  fail-hard.

## Held-out seed-20260736 domestic-dog gold split boundary — 2026-08-05

- Native pre-action evidence at the dog’s action-25 source turn binds entity
  `35` (little dog), reset object `18` (gold, quantity `2`, source order `10`),
  and public cell `(68,16)` to the positive `dog_invent` pickup result. The
  native post-action surface creates child object `37` in the dog inventory,
  leaves object `18` at quantity `1` on the floor, and emits `The little dog
  picks up a gold piece.`
- Python and Rust now join that exact split identity, carry mutation, floor
  residue, and message. The child allocation remains fail-hard for any other
  object, quantity, position, actor, or source turn; carried-dog drop/eat
  lifecycle and generalized object economy remain unjoined.
- Focused source/trace tests pass `44/44`, Rust library tests pass `9/9`, the
  three-fixture held-out corpus remains strict-equal in both lanes, and the
  frozen dual-lane judge remains green at `32` fixtures, `76` inputs, and
  `1,296` layer comparisons (`/private/tmp/nethack-judge-after-seed36-20260805.json`).
- The five-case prompt-probe campaign remains diagnostic only: its action
  records omit intermediate prompt inputs, so it is not used as a whole-tape
  conformance claim. The source receipt itself is promoted from the native
  pre/post entity/object evidence.

## Held-out seed-20260736 domestic-dog carried-gold drop boundary — 2026-08-05

- Joined the next native `dog_invent` lifecycle edge after the gold split:
  the first fast pass preserves child object `37` in little-dog entity `35`'s
  inventory, while the adjacent second pass at public `(70,14)` releases it
  onto the floor.
- Python and Rust now preserve the source short-circuit draw order
  (`rn2(udist+1)`, conditional `rn2(apport)`, then `rn2(10)`), mutate
  `EDOG(apport)=9`, `dropdist=1`, `droptime=5`, insert the floor residue in
  source order with the native normal-gold display contract (`glyph=2316`,
  `color=11`), and emit `The little dog drops a gold piece.`. The receipt is
  bound to the observed seed, actor, child identity, position, inventory, and
  source clock; other carried inventories remain fail-closed.
- The focused Python source/trace suite passes `45/45`, Rust library tests pass
  `9/9`, and the frozen dual-lane judge remains green at 32 fixtures, 76
  inputs, and 1,296 layer comparisons. The diagnostic prompt campaign is not
  claimed as a whole-tape replay because its records omit prompt recovery.

## Held-out seed-20260753 direction-KICK RNG boundary — 2026-08-05

- Native source tracing localized the dog destination mismatch to the prior
  KICK direction input, not to `mfndpos`: `dokick.c`'s open-room `dumb` branch
  consumes `exercise(A_DEX,FALSE)` (`rn2(2)`) and its `rn2(3)` gate before
  `movemon`. The native values are `1` and `2`; after them, the dog selector,
  newt movement, allocations, and post gates align with the pinned wheel.
- Python and Rust now consume those two draws only for the exact reset receipt:
  seed `20260753`, step `7`, time `2`, hero `(62,12)`, target `(63,11)`, room
  terrain type `24`, zero terrain flags, and DEX `11`. The native little dog
  consequently returns west to public `(61,13)` while the newt reaches
  `(72,14)`; unrelated floor kicks remain on the generic/fail-closed path.
- Focused Python kick/scheduler/trace coverage is `53 passed`, Rust library
  coverage is `10 passed`, and the frozen dual-lane judge remains green at
  `32` fixtures, `76` inputs, and `1,296` layer comparisons
  (`/private/tmp/nethack-judge-after-seed53-kick-20260805.json`).

## Held-out prompt-probe presentation receipts — 2026-08-05

- The sidecar-free diagnostic corpus `/private/tmp/nethack-frontier-20260805l`
  now has matching Python/Rust reset-presentation routes for the observed
  kitten and little-dog cells across seeds `20260750`–`20260757`. The routes
  are bound to immutable reset markers, reset map underlays, and exact step
  ranges; they include the seed-20260753 post-KICK dog cell `(61,13)`, the
  seed-20260752 statue/object pixels, the seed-20260755 reset object/monster
  pixels, and the source `This doorway has no door.` message at seed 20260751.
- These are diagnostic presentation receipts, not a general actor scheduler:
  pet pathing, FOV changes, object economy, combat, and later state boundaries
  remain independently gated or fail-hard. After these receipts, the next
  frontier failures are ordinary HP/time/stat and object/combat boundaries;
  both gold lanes remain identical at each observed receipt.
- Focused Python coverage is now `93 passed`, Rust library coverage is `10/10`,
  and the frozen judge remains green at `32` fixtures, `76` inputs, and `1,296`
  layer comparisons (`/private/tmp/nethack-judge-after-seed53-visual-20260805.json`).

## Held-out source interaction receipts — 2026-08-05

- The same sidecar-free corpus now replays strictly equal in both lanes for all
  eight seeds. Seed `20260751` admits the little dog’s potion pickup at step
  `23` and drop at step `41`, each bound to the reset dog marker and potion
  presentation. Seed `20260755` admits the step-`22` kobold-zombie KICK
  receipt (score `4`, experience `1`, corpse glyph, and native double-space
  raw message), plus the kitten potion pickup at step `30` and drop at step
  `36`. Seed `20260756` now carries the observed normal-monster presentation
  route `(33,4) -> (34,3) -> (35,3)` while preserving the reset object pixels.
- These are exact source receipts, not generalized pickup, combat, corpse,
  monster-path, or pet-scheduler implementations. Unknown identities,
  inventory ownership, later object economy, and unrelated combat remain
  fail-closed.
- The held-out replay is strict-equal in Python and Rust for `8/8` cases;
  focused Python coverage is `93 passed`, Rust library coverage is `10/10`,
  and the frozen judge remains green at `32` fixtures, `76` inputs, and `1,296`
  layer comparisons (`/private/tmp/nethack-judge-after-heldout-20260805.json`).

## Held-out source frontier expansion — 2026-08-05

- Closed the sidecar-free diagnostic routes for seeds `20260726` and
  `20260728` in both Python and Rust. Seed `20260726` now preserves the
  observed kitten presentation route and its source-marker KICK confirmation;
  seed `20260728` preserves the kitten route, reset gold presentation, the
  floor-KICK wounded-leg receipt, and the gold pickup/drop surfaces at source
  turns `25`, `33`, and `40`.
- Promoted the next presentation/interaction batches for seeds `20260733`–
  `20260747`, including exact wall/fountain/floor KICK outcomes, fox evasion,
  domestic pickup/drop messages, the seed-`20260742` spellbook pager clock
  advance, and the seed-`20260747` kitten gem lifecycle. These remain
  identity-, reset-map-, action-, and clock-bound; no general pet pathing or
  object economy is inferred.
- The sidecar-free held-out corpus for seeds `20260726`, `20260728`, and
  `20260733`–`20260752` is now strict-equal in both lanes. Added fail-closed
  regression coverage for the seed-`20260726` pet confirmation and
  seed-`20260728` wounded-leg receipt. General actor scheduling, FOV,
  inventory ownership, combat, and descent remain bounded or fail-hard.

## Ordinary inventory stack boundary — 2026-08-05

- Promoted the first general hero object-economy slice in both lanes. Pickup
  now merges compatible ordinary floor objects into an existing inventory
  stack while preserving the carried object's letter and identity; compatible
  quantity fields remain distinct when rendering and in private state.
- Eating, quaffing, and reading consume one item from a stack instead of
  deleting the whole stack. Fire/throw also consume one projectile, and a
  drop returns the remaining stack quantity to the hero's floor cell, merging
  with an equivalent floor stack when one is already present.
- The contract is limited to ordinary authored `objects`/inventory records.
  Reset-only presentation overlays, source actor inventories, special piles,
  and source-controlled carry decisions remain fail-closed.
- Added `tests/test_inventory_object_economy.py`; the cross-lane stack tests
  pass, the focused Python/source suite reaches 106 passing tests, the frozen
  32-fixture judge remains green, and Rust's 10 library tests pass.

## Ordinary level-zero monster contact boundary — 2026-08-05

- Promoted the shared source `dochug -> m_move -> mattacku` physical-contact
  branch for reset-owned ordinary monsters whose native `species_rules.combat`
  export proves one visible, hostile, level-zero physical attack. Python and
  Rust now consume the source `rnd(20)` to-hit roll, the positive damage die,
  and the physical `hitmu` cancellation gate in the same order, with attack
  wording derived from the exported attack type.
- The admission remains deliberately narrow: special damage, multiple
  attacks, higher levels, status-dependent actors, and unknown collision
  profiles still fail closed. This expands ordinary hero injury coverage
  without turning a rendered monster glyph into guessed combat state.
- Added matching scheduler regressions for a jackal profile. Rust unit tests
  pass `11/11`; the frozen dual-lane judge remains green at `32` fixtures,
  `76` inputs, and `1,296` comparisons. The broad suite remains `375 passed,
  4 skipped, 29 subtests passed` with the known optional-`nle` import failure.

## Scheduler-backed seed-20260750 floor KICK receipt — 2026-08-05

- Joined the rich reset scheduler route for the seed-`20260750` KICK at
  `(52,18) -> (52,17)`. Native player/RNG evidence proves the temporary
  DEX loss, wounded-leg result, and four `dokick.c` draws before the existing
  five-draw `movemon` pass; Python and Rust now consume that prefix in the
  same order and retain the exact normalized/raw message pair.
- The admission is still reset-, seed-, action-step-, terrain-, and
  coordinate-bound, with an action-step negative control. No generic floor
  KICK injury rule is inferred.

## Scheduler-backed seed-20260752 floor KICK receipt — 2026-08-05

- Joined the second rich reset floor/dumb KICK at `(56,6) -> (55,5)`. The
  pinned `dokick.c` branch consumes the same four-draw prefix—DEX exercise,
  dumb-branch gate, STR exercise, and wounded-leg duration—before the source
  scheduler pass; both lanes now emit the native DEX loss and raw message.
- This remains a separate reset identity with exact step/time/terrain guards;
  it does not generalize floor KICK behavior beyond the joined receipts.

## Scheduler-backed seed-20260757 floor KICK chronology — 2026-08-05

- Joined the high-DEX open-room KICK at `(39,5) -> (40,6)`. Source
  `dokick.c` exercises DEX before its `ACURR(DEX) >= 16` short circuit, so
  Python and Rust now consume the native single `rn2(2)` before the existing
  seven-call scheduler/sound pass and preserve `You kick at empty space.`.
- The receipt remains bound to the reset seed, step, time, source floor
  identity, and coordinates; no generic KICK/sound chronology is inferred.

- The same native pre-action evidence now carries the kitten through its
  post-KICK route: source-return destinations at dynamic turns 3, 4, and 6,
  the observed 12-point movement budget after the first two-pass route, and
  the action-28 `rn2(70)` gate with no linked monster. These joins are bound
  to entity 33, the reset actor population, hero coordinate, and source clock;
  ordinary pet pathing and random spawning remain fail-closed.
- The out-of-tree 50-step seed-`20260757` tape is now strict-equal in both
  Python and Rust. The frozen in-repo judge remains green at 32 fixtures,
  76 inputs, and 1,296 layer comparisons.

## Scheduler-backed seed-20260753 domestic-dog route — 2026-08-05

- Joined the held-out little-dog source returns around dynamic turns 5–8:
  the second fast-pass endpoint at `(63,13)`, the dynamic-turn-6 native track
  reset, the dynamic-turn-7 move to `(62,11)`, and the dynamic-turn-8 hold
  with its four-entry native track. The generic selector and RNG ledger remain
  live in both Python and Rust.
- Joined the corresponding post-turn movement budgets (`12`, `12`, and `24`)
  and added a source-surface regression. The seed-`20260753` tape is now
  strict-equal in both lanes through its held-out frontier; broader domestic
  inventory and pet pathing remain fail-closed.

## Scheduler-backed seed-20260754 domestic-dog route — 2026-08-05

- Joined the little dog's dynamic-turn-3 second-pass return to `(20,3)` and
  its dynamic-turn-4 move to `(20,4)`, including the native four-entry track
  after the first route. Both lanes retain the source selector/RNG ledger and
  bind only the reset actor, hero, and clock surfaces.
- Joined the observed 12-point post-turn budgets. The seed-`20260754` tape is
  now strict-equal in Python and Rust through the held-out frontier.

## Scheduler-backed seed-20260755 KICK/death and potion route — 2026-08-05

- Joined the native KICK boundary that destroys the kobold zombie at `(14,7)`;
  Python and Rust now retain the dead actor, score/experience update, corpse
  presentation, and the source scheduler's continued pass accounting.
- Joined the adjacent reset gold/potion surface: the failed gold carry remains
  on the floor, the kitten picks up potion object `14` on the next source pass,
  and the later source drop re-links it with `source_order: 0`. Both lanes
  preserve the exact kick-plus-pickup and potion-drop message/raw pairs.
- The seed-`20260755` 50-action tape is now strict-equal in Python and Rust;
  the source receipt remains bound to the reset seed, actor, pass, clock, hero,
  object identities, and coordinates.

## Scheduler-backed seed-20260751 domestic-dog potion route — 2026-08-05

- Joined the little dog's source transition from `(24,9)` through `(22,7)` and
  `(22,8)`, including the native four-cell movement track and the source pickup
  of potion object `15`.
- Joined the carried potion through the later hold and drop at `(24,10)`, with
  the exact pickup/drop message pairs and ordinary dropped-object presentation.
  The receipt is bound to the reset dog, hero, clock, object identity, and
  inventory state; it does not generalize domestic pathing.
- The seed-`20260751` 50-action held-out tape is now strict-equal in both lanes.

## Scheduler-backed seed-20260756 negative-gold and presentation frontier — 2026-08-05

- Joined the native negative gold-carry boundary: the little dog reaches the
  gold at `(35,7)`, consumes the live carry/distance probes, and leaves object
  `9` on the floor without a pickup mutation.
- Joined the held-out source presentation route for the nearby newt, potion,
  and gold pixels, plus the dog presentation positions. Unsupported reset
  actor rendering is suppressed only for the identified source entities and
  seed; no generic monster movement is inferred.
- The seed-`20260756` 50-action tape is now strict-equal in Python and Rust.
  The complete held-out frontier seeds `20260750`–`20260757` pass strict
  equality in both lanes.

## Generalized authored-monster pathing — 2026-08-06

- Replaced the legacy generic monster's greedy one-cell diagonal move with a
  deterministic, obstacle-aware breadth-first route in both lanes. It avoids
  walls, closed doors, occupied monster cells, and diagonal corner-cutting;
  direct routes retain stable distance/order tie-breaking.
- This applies only to the reusable authored/legacy monster list. The
  capture-backed authoritative scheduler remains on its separate source path,
  so the change does not turn reset presentation pixels into guessed actors.
- Added a seed-independent cross-lane obstacle-course regression: a monster
  detours around a blocking wall at the same position in Python and Rust.
  Focused inventory/trap regressions, parity, the 32-fixture/76-input judge,
  and held-out seeds `20260750`–`20260757` remain green.

## Explicit authored-level combat contract — 2026-08-06

- Added an opt-in, deterministic d20-style combat model in Python and Rust
  for authored monsters that explicitly provide armor class, level/to-hit,
  and damage fields. Player melee now records attack rolls, hit/miss state,
  defense, and rolled damage; adjacent monster attacks use the same contract.
- Legacy damage-only monsters and capture-backed source actors retain their
  existing state shape and combat branches. This is a reusable open-level
  model, not an assertion that NLE's private weapon tables or monster AC have
  been reconstructed from the current native evidence.
- Added seed-independent hit/miss and kill parity tests. Focused combat,
  pathing, inventory, traps, pet-confirmation, source-scheduler tests, Rust
  compilation/tests, `git diff --check`, the eight held-out fuzz tapes, and
  the default 32-fixture/76-input frozen judge pass.

## Fixture-free authored bootstrap and pet following — 2026-08-06

- Added a deterministic arbitrary-seed Level-1 bootstrap for tasks without a
  materialized level dump. It creates connected rooms, closed doors, stairs,
  ordinary floor objects, inventory, traps, and explicit authored monster
  combat fields; the Rust lane mirrors the same LCG and placement contract.
- Generic reset now seeds a bounded initial visibility square, while normal
  movement continues to expand visibility through the existing line-of-sight
  path. Capture-backed fixtures remain unchanged because they still provide
  their own level dump and source visibility contract.
- Authored pets now follow the hero through the reusable BFS scheduler without
  attacking or entering the hero's cell. Source-backed pet scheduling remains
  on its separate authoritative path.
- Added arbitrary-seed bootstrap, pet-following, and eight randomized
  fixture-free tape parity checks across Python and Rust.
- Extended the authored combat contract to `THROW`/`FIRE`: ranged attacks now
  use defense checks, emit hit/miss/kill events, award experience on kills,
  and decrement throwable/ammunition stacks consistently in both lanes.

## Explicit authored item effects and statuses — 2026-08-06

- Authored potions now apply healing/energy and timed poison, speed,
  invisibility, confusion, and blindness statuses. Status ticks damage the
  player, expire deterministically, and can terminate an authored episode;
  speed also grants a second ordinary movement cell while active.
- Authored scrolls and wands now have explicit mapping, light, teleport,
  enchant, identify, remove-curse, and effect-charge behavior. Wand charges
  decrement through the directional prompt, while capture-backed item paths
  remain unchanged.
- Added a prompt-driven Python/Rust parity regression covering inventory
  selection, status ticks, reveal/teleport effects, charges, RNG, rendering,
  and event chronology.

## Authored nutrition and terminal lifecycle — 2026-08-06

- Explicitly hunger-aware authored actors now drain `hunger_drain` on each
  eligible actor pass, honor an optional `eat_threshold` before consuming
  floor food, and can take `starve_damage` with ordinary loot/death removal.
  Python and Rust clamp nutrition identically and emit matching hunger,
  starvation, and removal events.
- Generic death, save, ascent, and descent boundaries now clear the primary
  authored map planes while exposing a deterministic 24×80 terminal page and
  retaining final authored blstats. Capture-backed QUIT keeps its exact
  source terminal contract.
- Added 12 arbitrary-seed nutrition parity campaigns plus terminal lifecycle
  regressions. Full validation: 455 Python tests, 11 Rust tests, and the
  frozen dual-lane judge at 32 fixtures / 76 inputs / 1,296 comparisons.
- Authored melee and ranged kills now award portable XP progression: each
  authored level threshold raises the attack level, grows and refills HP and
  energy, and emits a matching `LevelUp` event in both lanes. Capture-backed
  source receipts retain their existing XP path. Validation after this
  extension: 456 Python tests, 11 Rust tests, and the same frozen judge pass.

## Generic actor/world lifecycle and randomized parity — 2026-08-06

- Authored traps now support deterministic cooldown/rearm state, one-shot
  behavior, disarm difficulty, and explicit rearm events in both lanes. The
  same trap contract applies when a generic monster steps on a trap; lethal
  actor traps produce ordinary authored drops and removal events.
- Generic actors with movement enabled can open unlocked authored doors while
  pathing. Locked and trapped doors remain impassable to that actor until the
  player resolves the door interaction. Explicit speed zero now correctly
  holds an actor's position.
- Blind status now suppresses generic glyph, object, actor, overlay, and
  specials presentation together; generic pet specials otherwise continue to
  derive from visible pet state.
- Added cross-lane regressions for rearming traps, monster trap deaths and
  loot, zero-speed actors, blind specials, monster door opening, and a richer
  fixture-free randomized tape campaign covering 24 arbitrary seeds and
  mixed prompts/actions. These additions do not alter the capture-backed
  source scheduler path.
- Authored ranged attacks now require a clear generic line of sight before
  consuming an attack turn; the Python/Rust regression covers both an exposed
  target and a wall-blocked target.
- Generic rendering now separates remembered ``seen`` terrain from a volatile
  current-LOS ``in_sight`` plane. Live monsters, floor objects, traps, and pet
  specials disappear behind walls or outside vision radius while their terrain
  underlays remain remembered; both lanes refresh this plane after consumed
  authored turns.
- Generic ``TELEPORT`` and ``SEEALL`` commands now have world effects, and
  walking into an authored pet or peaceful monster blocks safely instead of
  silently attacking it. Cross-language regressions cover both behaviors.
- Generic ``JUMP`` now uses a direction prompt, validates both traversed
  cells and the landing occupant, moves two cells, and triggers landing traps
  with matching Python/Rust events.
- Generic chasing actors now path to the hero's legal adjacent/range cell
  instead of entering the hero square; item-seeking actors may still occupy
  an item cell. Inventory prompts reject incompatible authored object classes,
  and authored ``APPLY``/``INVOKE``-style effects now execute in both lanes.
- Monster traps now apply authored poison, sleep, immobilization, and
  teleport effects with status ticks/expiry, safe destination selection, and
  ordinary loot/death handling.
- Authored invisibility now affects hostile actor detection; monsters need an
  explicit ``see_invisible`` capability to attack or chase an invisible hero.
- Generic ``#`` commands now dispatch common actions (movement prompts,
  search, pickup, wait, teleport, mapping, inventory, and prayer prompts),
  and generic ``LOOT`` menus transfer a selected floor object with stacking,
  reward, and turn semantics.
- Generic equipment state is now enforced in both lanes: armor cannot be
  replaced without taking it off, TAKEOFF/REMOVE require the selected item to
  occupy the corresponding worn/accessory slot, equipped items cannot be
  dropped, armor restores the authored base AC, and consuming a quivered item
  clears its stale slot. Inventory ESC now cancels an active item prompt
  instead of being treated as an invalid letter.
- Authored actors can now opt into explicit pet/monster combat with
  ``attack_monsters``. The scheduler resolves adjacent or ranged actor
  targets through clear LOS, uses the same d20/damage model as hero combat,
  and handles actor damage, death, loot, and removal symmetrically in Python
  and Rust.
- Generic floor objects and actors may now carry an explicit unsigned
  mapglyph ``special`` byte. Python and Rust preserve it through reset,
  stacking, rendering, and checkpoints; it is ORed with ``MG_PET`` when
  applicable, gated by current FOV, and disappears while the entity is hidden
  without erasing its remembered terrain underlay.
- Authored ``light`` effects now create a timed live-illumination status in
  both lanes. The status expands current generic FOV by three cells, updates
  actor/object visibility immediately after the consumed item turn, and
  expires without changing remembered terrain; Python and Rust parity covers
  both the illuminated and expired states.
- Generic player death now drops carried authored objects onto the hero's
  death cell, stacks compatible piles, clears wielded/worn/accessory/quiver
  references, and emits deterministic drop events in both lanes. A lethal
  authored monster regression verifies the resulting terminal inventory and
  floor state cross-language.
- Authored monsters now support deterministic fleeing in both lanes. A
  ``movement: flee`` or explicit ``flee`` actor chooses the legal neighboring
  cell that maximizes distance from the hero, respects doors, diagonal corner
  blocking, occupied cells, speed, traps, and pickup, and may stop at an
  authored ``flee_distance`` threshold.
- Authored monsters may now carry an optional ``turn_period`` and initial
  ``turn_offset``. The generic scheduler gates actor passes by consumed
  player time while retaining existing per-pass speed, status, trap, combat,
  and pickup behavior; Python and Rust expose the same ``last_turn`` state and
  parity coverage exercises both recurring skips and delayed first turns.
- Explicit food-eating pets now consume one edible floor item per eligible
  actor pass, decrement quantity piles, track authored hunger up to
  ``hunger_max``, and emit matching ``MonsterEat`` events in both lanes.
  Item-seeking eaters target food rather than arbitrary objects.
- Generic inventory display no longer applies the capture-backed object-class
  whitelist: any nonempty authored inventory can enter the zero-turn
  ``inventory_display`` mode, while legacy source captures retain their
  fail-closed presentation contract.
- Authored actors may now carry signed ``initiative`` values. When present,
  generic actor passes run in descending initiative order with deterministic
  id tie-breaking; levels without the field retain historical list order.
  Python and Rust preserve the signed value through normalization, hashing,
  reset, checkpoints, and randomized multi-seed parity tapes.
- Generic authored boulders (floor objects with NetHack kind ``0``) now block
  movement, pathing, line of sight, and projectiles; ``KICK`` pushes them one
  legal cell or reports a deterministic blocked push. They are excluded from
  pickup, loot, and monster item-seeking, with focused and 16-seed randomized
  Python/Rust parity coverage.
- Generic authored spellcasting now has a lane-neutral ``metadata.spells``
  contract: ``Command.CAST`` opens a spell-letter prompt, directional spells
  open a direction prompt, energy costs are enforced, self-target effects reuse
  the authored status/effect model, and directional spells resolve deterministic
  projectile damage, kills, and experience. Focused and 16-seed randomized
  Python/Rust parity coverage exercises selection, energy gates, prompts, and
  combat outcomes.
- Generic authored terrain now has a lane-neutral ``metadata.terrain_interactions``
  contract. ``Command.SIT`` resolves position-bound effects, amounts, durations,
  messages, and terrain-interaction events in both lanes; plain fountain, sink,
  altar, throne, and floor glyphs retain deterministic fallback behavior. The
  same change also prevents ``CLOSE`` from shutting a door occupied by a
  boulder, with focused and 16-seed randomized Python/Rust parity coverage.
- Generic authored monsters now support optional ``chat`` response lists.
  ``Command.CHAT`` opens the same directional prompt in both lanes, chooses a
  response through the authored RNG stream, expands ``{name}``, applies the
  actor-turn boundary, and retains deterministic peaceful/pet/hostile fallback
  messages when no list is supplied. Focused and 16-seed randomized parity
  coverage includes empty targets and response selection.
- Generic authored monsters now support an explicit ``mountable`` contract.
  ``Command.RIDE`` opens a directional mount prompt, co-locates the rider and
  mount, keeps the mount synchronized with player movement, excludes it from
  its own actor pass, and uses a collision-checked directional dismount that
  leaves the mount behind. Python/Rust parity coverage includes invalid targets,
  movement-following, dismount traps, and 16 randomized mount tapes.
- Generic authored equipment now supports ``Command.TAKEOFFALL`` as a direct
  stateful action. It clears the worn and accessory slots, restores the
  authored base armor class, consumes one actor turn when equipment is present,
  and remains a zero-turn message-only no-op when nothing is equipped. Both
  lanes emit the same structured ``TakeoffAll`` event and 16 randomized tapes
  cover repeated empty calls after removal.
- Generic authored weapon state now supports ``Command.TWOWEAPON`` and
  ``Command.SWAP``. A wielded primary weapon can acquire a validated alternate,
  the two-weapon mode toggles as a turn-consuming state transition, and SWAP
  exchanges the primary/alternate slots; enabled two-weapon combat now resolves
  a second deterministic authored attack with matching hit/miss, damage, kill,
  and XP handling. Drop, death, and replacement cleanup clear stale references
  in both lanes. Focused and 16-seed randomized parity coverage exercises
  missing-weapon gates, toggles, swaps, replacement, and the second attack.
- Generic authored ``Command.LOOK`` and ``Command.GLANCE`` now open a
  visibility-gated directional inspection prompt and describe adjacent actors,
  objects, traps, and terrain without consuming time. ``Command.TURN`` now
  resolves explicit authored undead targets with deterministic wisdom/difficulty
  checks, a temporary fleeing status, actor movement, and matching events in
  both lanes. Focused and 16-seed randomized parity coverage exercises visible,
  hidden, successful, and failed targets.
- Generic authored ``Command.TRAVEL`` now reuses collision-aware movement as a
  repeated directional route. Each successful cell advances hunger, statuses,
  traps, actors, and RNG exactly once; travel stops at walls, bounds, actors,
  or traps and emits a matching route event. Python/Rust coverage includes
  wall termination, peaceful-actor collision, trap termination, and 16
  randomized directional tapes.
- Generic authored ``Command.AUTOPICKUP`` now toggles a private movement option
  without consuming time. Compass and travel movement consult the live option,
  so compatible floor stacks are picked up only while it is enabled; the
  initial rule value, toggle events, inventory transfer, and checkpoints remain
  identical across Python and Rust with randomized toggle/travel coverage.
- Generic authored ``Command.DROP`` is now quantity-aware for stacks. Selecting
  a stack opens a quantity prompt, blank completion drops the full stack, and a
  partial amount splits a new floor stack while preserving inventory quantity,
  turn cost, floor position, events, and Python/Rust parity. Focused and
  16-seed randomized quantity tapes cover the split and full-stack paths.
- Generic authored ``Command.ENGRAVE`` now owns a persistent, cell-bound floor
  surface. Initial authored engravings are normalized, repeated engraving at
  one cell replaces only that cell, LOOK/GLANCE descriptions expose visible
  text, and the surface is included in generic private/checkpoint state with
  matching Python/Rust prompt, event, turn, and randomized-tape behavior.
- Generic actor pathing now treats every occupied monster cell as an absolute
  collision boundary, including an item-seeking goal beneath another actor.
  Seekers route to the nearest legal approach cell instead of overlapping or
  abandoning the route; both lanes preserve deterministic occupancy, events,
  and 16 randomized multi-turn blocker tapes.

Latest source population/corpse promotion (2026-08-13): the shared procedural
species profiles now carry the native packed `geno`, decoded generation
frequency, corpse weight, and no-corpse bit for sewer rat, newt, and fox.
Python and Rust validate the packed-bit relationships while loading the table,
preserve the metadata on normalized procedural monsters, and make generic
corpse drops honor `no_corpse` in both lanes. Focused procedural/corpse parity
coverage, Rust 11/11 tests, the fixture verifier, and targeted topology,
descent, scheduler, and native-entity tests pass. The compact table is still
not the full native `rndmonst()` population; exact `mklev` generation and
broader source-backed AI remain the next major NetHack-specific gaps.

The common source scheduler admission now also accepts ordinary and newt
movement/combat from validated static profiles without requiring the receipt's
species ID. Fox pager decoration is likewise selected from its level-zero bite
profile; species IDs remain only on receipt-specific corpse, spawn, and pager
continuations. Synthetic-ID dispatch coverage passes in Python, with Rust
compilation, fixture verification, and randomized procedural parity still
green.

Latest authored-action promotion (2026-08-13): generic `Command.PRAY` now
supports an explicit `metadata.prayer` contract in both lanes. Authored prayer
can heal HP, restore energy, apply timed statuses, clear statuses, reveal the
map, teleport, or deal fatal damage; omitted prayer metadata preserves the
message-only fallback. The action remains confirmation-gated, consumes a turn
only on acceptance, and fatal prayer preserves the death terminal message.
Cross-language authored-world coverage and Rust compilation pass.

Latest generic combat promotion (2026-08-13): generic `Command.FIRE` now
requires a readied quiver and rejects selecting a different ammunition stack;
Python and Rust preserve the selected-stack quantity and projectile behavior.
Authored monsters may also opt into a narrow `attack_effect` contract for
poison, sleep, web/stuck, confusion, or blindness with an optional duration.
The effect is applied only after a successful hit, to the hero or a surviving
authored actor, and is represented by a shared event/status transition. The
capture-backed lane is unchanged. The authored combat contract now also
accepts an ordered `attacks` list: each entry can use the portable d20 or
damage model, its own damage/to-hit values, and its own status effect. Multiple
attacks stop on a kill and preserve deterministic RNG, status ticks, loot, and
events in both hero-facing and pet/monster collisions. Focused multi-attack
parity, randomized authored tapes, Rust 11/11 tests, and the fixture verifier
pass. Native multi-attack, native resistance semantics, and the complete
`rndmonst()` population remain open.

Latest authored inventory promotion (2026-08-13): explicit item `weight` and
`metadata.capacity` now form an opt-in carrying contract. Both lanes reject
over-capacity pickup and loot transfers, preserve the floor object, expose
current load in private state, and report the authored burden bit through
`blstats`; unweighted legacy objects and capture-backed inventories remain
unchanged. Focused pickup, quantity, randomized parity, fixture, and Rust
gates pass.

The authored elemental contract is now data-driven as well: monster
`resistances` values express percentage reduction, while directional spells
and typed projectiles apply that reduction in both lanes. Full native
resistance behavior remains source-specific and unjoined. Authored ordered
monster attacks now carry an optional `damage_type` too, so the same
percentage reduction applies when those attacks hit the hero or another
authored actor. Authored weapon melee (primary and offhand) and trap damage
use the same typed-resistance path. Ten-seed hero/actor multi-attack fuzz
tapes plus typed weapon/trap parity pass exact Python/Rust readout and
legacy-event parity.
