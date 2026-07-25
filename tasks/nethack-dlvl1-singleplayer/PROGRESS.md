# NetHack dlvl-1 coverage ledger

This ledger records what the own gold engines model today.  A listed action is
not automatically an NLE-parity claim: the claim becomes green only when a
frozen NLE tape exercises it in both lanes.

| Subsystem | Current own-engine support | Frozen NLE evidence | Status |
| --- | --- | --- | --- |
| Action surface | All pinned `nle.nethack.ACTIONS` ids accepted; canonical names and raw adapter keys accepted | 0 / 33 tapes | plumbing complete |
| Level input | Capture-backed 21×79 terrain/glyph/color dump, hero, objects, monsters, traps, memory | 0 / 33 tapes | plumbing complete |
| Geography | Main Dungeon dlvl 1 only; `>` on down stair terminalizes as `descended`; branch dumps rejected | 0 / 33 tapes | modeled |
| FOW / memory | Seen-cell memory and local visibility refresh | 0 / 33 tapes | modeled, needs NLE calibration |
| Movement / doors | 8-way walk, long movement, open/close/kick direction modes, walls and stairs | 0 / 33 tapes | modeled, needs NLE tapes |
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

## Open limitation

The local host did not have `nle` installed while this foundation was built.
That is recorded as a GameBench papercut; capture is purposefully not faked from
gold output.  `compare_nle_discrepancies.py` therefore supports an empty corpus
by default, but `--require-fixtures` fails until authentic captures land.
