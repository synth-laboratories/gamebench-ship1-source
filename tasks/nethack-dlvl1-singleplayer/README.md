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
  27-slot NLE `blstats` (including condition and alignment), normalized message plus raw bytes, inventory arrays, and
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

## Live NLE differential fuzzing

The optional fuzzer runs live NLE and the own gold lanes from the same
capture-backed reset.  It is a diagnostic oracle tool: it never imports NLE
from gold code and it does not write candidate captures into the checked-in
corpus automatically.

On this macOS host, use CPython 3.10 for NLE 0.9.0.  Its bundled bindings do
not build on CPython 3.11, and CMake 4 needs the policy compatibility setting
during the NLE build:

```bash
uv venv --python 3.10 .venv
CMAKE_POLICY_VERSION_MINIMUM=3.5 uv pip install --python .venv/bin/python -r requirements-nle-fuzz.txt
.venv/bin/python scripts/fuzz_nle_differential.py --cases 10 --steps 32 --seed 20260725 --lane python --output /tmp/nethack-nle-fuzz
```

Use `--lane both` to include the Rust trace lane.  The output directory holds
reproducible, capture-shaped cases and structured discrepancy reports; inspect
or replay it without copying artifacts under `fixtures/nle_oracle/`:

```bash
python scripts/compare_nle_discrepancies.py --root /tmp/nethack-nle-fuzz --lane both
```

The default `navigation-v0` campaign generates visible navigation and explicit
`MORE` inputs.  `prompt-probe-v0` adds a bounded safe command family, resolves
direction and `MORE` prompts, and uses `ESC` to recover other raw prompts:

```bash
.venv/bin/python scripts/fuzz_nle_differential.py --cases 25 --steps 32 --seed 20260725 --lane both --campaign prompt-probe-v0 --output /tmp/nethack-nle-prompt-probe
```

Pass `--actions <jsonl>` to replay arbitrary pinned action IDs; a `DOWN` away
from a known stair is sent to NLE normally, while an actual descent is emitted
as a terminal pre-dlvl-2 boundary.  Risky host/episode-escaping commands remain
for explicit tapes rather than generated campaigns.

Every run writes `coverage.json` beside `run.json`.  It separates selected
action IDs from action IDs actually stepped in NLE (a protected pre-dlvl-2
descent is selected but intentionally not stepped), then records `(action,
inferred-input-mode)` contexts, action families, inferred prompt modes,
terminal reasons, observed public-plane/blstats deltas, lane discrepancy
signatures, and a per-case novelty hash.  These are diagnostic coverage
measurements, not a conformance percentage.

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
and capture/discrepancy plumbing.  It is not yet an assertion that the required
33 authentic NLE tapes have been captured; coverage and deliberate stubs are
tracked in [`PROGRESS.md`](PROGRESS.md).
