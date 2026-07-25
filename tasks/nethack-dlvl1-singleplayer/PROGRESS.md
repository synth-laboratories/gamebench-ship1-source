# NetHack dlvl-1 coverage ledger

The canonical corpus currently has **12 / 33** required strict NLE tapes
(36.4%). Every listed tape compares the complete captured public observation
in both own lanes: chars, glyphs, colors, blstats, fixed-width raw message,
and inventory planes. This is evidence coverage, not a claim of general
NetHack parity.

| Subsystem | Current own-engine support | Frozen NLE evidence | Status |
| --- | --- | --- | --- |
| Action surface | All pinned `nle.nethack.ACTIONS` ids are accepted with canonical names and raw adapter keys | 12 / 33 tapes across movement, prompts, pickup, search, and doors | adapter breadth is not parity by itself |
| Level input | Capture-backed 21×79 terrain/glyph/color dump, hero, objects, monsters, traps, and unseen planes | 12 / 33 tapes | raw reset planes, blstats, messages, and inventory baselines are checked exactly |
| Pixel parity gate | Strict comparator checks characters, glyphs, colors, blstats, messages, and inventory at every snapshot | 12 / 33 tapes | no partial-plane pass is accepted for promotion |
| Live NLE fuzz | NLE and Rust consume the same action IDs from the same reset; strict baseline comparison is the default | diagnostic only | every discrepancy is retained out of tree and logged before it is minimized or fixed |
| Property invariants | Hypothesis constrained fixtures, public observation integrity, determinism, checkpoints, and Python/Rust trace properties | N/A | own-engine consistency only; not NLE evidence |
| Geography | Main Dungeon dlvl 1 only; `>` terminalizes as `descended`; branch/dlvl-2 dumps rejected | 0 / 33 descent tapes | descent route is captured but blocked on room/corridor visibility and pet motion |
| FOW / memory | Capture-specific unseen planes plus gold-owned LOS refresh after movement and door state changes | navigation and door tapes | ordinary room/corridor visibility remains a known strict-fuzz gap |
| Movement / doors | 8-way walk, long movement, direction prompts, glyph-backed open/closed doors, kick | east movement; door open in both orientations; closed/no-door close; kick | open-door resistance and broader terrain/LOS behavior remain unproven |
| Inventory / food | Letter assignment, pickup, empty-stair response, food prompt/cancel, empty/non-applicable apply handling | pickup, stair pickup, eat cancel | broader item semantics remain unproven |
| Combat | Deterministic melee, death, XP, and gold basics | 0 / 33 tapes | clean lichen kill capture awaits score calibration; monster timing is a fuzz gap |
| Traps / pets | Fixture-declared traps and basic occupancy | 0 / 33 tapes | raw pet/monster motion and trap projection remain unproven |
| Shops / branches / dlvl2 | No shop model; deeper play hard-stops | N/A | deliberately outside geography |

## Current strict corpus

- `val-east-seed-20260725`: one raw east move.
- `val-east-pickup-seed-20260725`: movement followed by pickup.
- `val-stair-pickup-seed-10`: return to a revealed stair and fixed-stair pickup.
- `val-search-seed-20260725`: empty search turn.
- `val-eat-cancel-seed-20260725`: food prompt then cancel.
- `val-open-cancel-seed-20260725`: open prompt then cancel.
- `val-open-empty-east-seed-20260725`: failed open after a direction response.
- `val-door-kick-seed-20261040`: failed kick against a closed door.
- `val-door-close-seed-20260061`: close against an already-closed door.
- `val-close-empty-east-seed-20260725`: close against a non-door.
- `val-door-open-horizontal-seed-20260316`: `2374` closed door opens to `-`/`2372`.
- `val-door-open-vertical-seed-20260315`: `2375` closed door opens to `|`/`2373`.

## Active discrepancy backlog

- Implement room/corridor visibility that matches NLE exactly; this is the
  prerequisite for the captured dlvl-1 descent route.
- Model raw pet/monster scheduling and overlays; current fuzz finds static
  entity projections where NLE moves an entity.
- Calibrate combat score/XP and promote the clean one-action lichen kill only
  after every changed blstats slot matches.
- Resolve static terrain hidden under the hero without smuggling future state
  into a level dump; fixed-stair pickup fuzz currently exposes this gap.
- Extend strict tapes toward and past 33 only with novel minimized behavior
  signatures. Diagnostic fuzz artifacts never enter `fixtures/nle_oracle/`.
