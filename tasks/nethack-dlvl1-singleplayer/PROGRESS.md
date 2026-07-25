# NetHack dlvl-1 coverage ledger

This ledger records what the own gold engines model today.  A listed action is
not automatically an NLE-parity claim: the claim becomes green only when a
frozen NLE tape exercises it in both lanes.

| Subsystem | Current own-engine support | Frozen NLE evidence | Status |
| --- | --- | --- | --- |
| Action surface | All pinned `nle.nethack.ACTIONS` ids accepted; canonical names and raw adapter keys accepted | 1 / 33 tapes (`CompassDirection.E`) | one action strictly replayed; broad surface remains plumbing |
| Level input | Capture-backed 21×79 terrain/glyph/color dump, hero, objects, monsters, traps, memory | 1 / 33 tapes | raw reset planes, blstats, message and inventory baselines calibrated for the first tape |
| Live NLE fuzz | Seedable navigation/prompt-probe campaigns, out-of-tree capture artifacts, coverage JSON, strict and bootstrap-masked transition diagnostics | 1 / 33 tapes promoted from a minimized navigation probe | diagnostic tooling complete; broader canonical coverage remains pending |
| Property invariants | Constrained Hypothesis lab fixtures, observation/state integrity, determinism, checkpoint, and Python/Rust trace properties | N/A | own-engine consistency coverage; not NLE parity |
| Geography | Main Dungeon dlvl 1 only; `>` on down stair terminalizes as `descended`; branch dumps rejected | 1 / 33 tapes | first tape is Main Dungeon dlvl 1; descent remains unproven |
| FOW / memory | Capture-specific unseen planes plus gold-owned LOS refresh after movement/terrain change | 1 / 33 tapes | reset and one east-step disclosure strictly calibrated |
| Movement / doors | 8-way walk, long movement, open/close/kick direction modes, walls and stairs | 1 / 33 tapes (`E` walk) | one empty east move strictly replayed; doors/stairs remain unproven |
| Combat | Deterministic dlvl-1 monster melee, death, XP/gold basics | 0 / 33 tapes | modeled, needs NLE tapes |
| Hunger / food | Turn clock, hunger bands, food inventory prompt and nutrition | 0 / 33 tapes | modeled, needs NLE tapes |
| Inventory | Letter assignment, pickup/drop, wield/wear/takeoff/puton/remove/quiver | 0 / 33 tapes | modeled, needs NLE tapes |
| Consumables | Eat, quaff, read, apply prompt paths with declared fixture effects | 0 / 33 tapes | modeled, needs NLE tapes |
| Traps / pets | Fixture-declared traps and basic pet occupancy | 0 / 33 tapes | modeled, needs NLE tapes |
| Prayer / engraving / magic | Prompt-aware accepted command path and fixture-defined outcomes | 0 / 33 tapes | accepted/stubbed pending captures |
| Shops / branches / dlvl2 | No shop model; Mines-bearing capture rejected; deeper play hard-stops | N/A | deliberately out of geography |

## Capture backlog

- [ ] ≥20 short NLE tapes: navigation, door, jackal, eat, pickup, wear, descend.
- [ ] ≥10 medium tapes: hunger, combat death, multi-prompt inventory, prayer/engraving.
- [ ] ≥3 adversarial tapes: trap, mimic-door, or scroll use.
- [ ] Pin NLE installation in a reproducible dev-extra lockfile note and materialize
      `fixtures/nle_oracle/<fixture-id>/` from raw action IDs.
- [ ] Promote a strict-green canonical minimum of 33 tapes, then expand only by
      novel minimized behavior signatures toward the focused 60–100+ corpus.

## First strict NLE result

The optional CPython 3.10 NLE 0.9.0 environment produced a deterministic
Main Dungeon dlvl-1 navigation capture for seed `20260725`:
`val-east-seed-20260725`.  Its reset and one `CompassDirection.E` transition
strictly replay in both own lanes.  The calibration fixed the initially found
FOW discrepancy: after the east move, NLE exposes `chars[15][33] == "."`;
the frozen dump now preserves hidden raw planes and captured static underlay,
while the gold-owned LOS refresh exposes it only after the hero moves.  It also
preserves the reset's 27-slot blstats, fixed-width message buffer, and 55-slot
inventory arrays.

This is **1 / 33** required tapes (about 3.0%), not a general navigation or
NetHack-fidelity claim.  The original live-fuzz artifacts remain diagnostic
under `/tmp`; only the minimized strict-green capture was promoted.

The current prompt-probe reaches seven distinct NLE-stepped action IDs and
now matches the captured food-letter prompt and empty-stair pickup response in
both lanes.  Its next reported discrepancy is intentionally retained as a
diagnostic data gap: a player glyph can hide its static underfoot tile until a
movement tape exposes it, so this prompt-only tape cannot yet prove the stair
underlay without adding unsupported future-state data.

## Open limitation

The foundation was built before this host had an NLE environment.  A
task-specific CPython 3.10 oracle environment now supports live diagnostic
fuzzing and one authentic capture has landed, but no candidate output is
promoted automatically.  The next evidence must extend beyond this one empty
movement transition—especially doors, combat, inventory prompts, hunger, and
the descent boundary—while keeping the corpus strict-green in both lanes.
