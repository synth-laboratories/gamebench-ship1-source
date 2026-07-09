# Porting brief — Python → Rust (the agent's task)

You are handed a **working Python codebase** (a GameBench gold engine) and must
produce a **Rust port** of it. This brief is modeled on how Bun was rewritten in
Rust ([bun-in-rust](https://bun.com/blog/bun-in-rust)): the acceptance criterion
is a **language-independent test oracle**, not code style.

## The acceptance criterion (the only thing scored)

A frozen **NEV eventlog** oracle records, for every scenario, the exact sequence
of events the Python gold emits. Your Rust port must reproduce that sequence
**byte-for-byte** for every scenario. Score = fraction of scenarios that match;
the target is **1.0**. Nothing else is graded — not idiom, not structure, not
performance. (Bun's rule: *0 tests skipped or deleted*, identical oracle
execution is the bar.)

## The contract your crate must satisfy

Your Rust crate MUST expose a binary named `scenario`:

- **stdin**: one scenario entry as JSON (fields: `scenario_id`, `seed`, `board`,
  `rules`, `actions` — the same entries in `fixtures/gold/scenarios/scenarios.json`).
- **stdout**: `{"events": [ ...NEV event strings... ]}`.

An event string looks like `TaskResolved(classic_01_valid_submit,dd048d068ce616ca)`
or `FrogPlaced(0,1)`. Match the Python gold's format and ordering exactly. The
reference `gold_rust/src/bin/scenario.rs` is a known-good implementation of this
contract (it scores 1.0) — you do not see it during the task, but it proves the
port is achievable.

## Method (mirrors the bun rewrite)

1. **Mechanical port, not a redesign.** Reproduce the Python engine's control
   flow and data model in Rust. Defer idiomatic refactors — parity first.
2. **Map before you write.** Read every module of `gold_python/` (`engine.py`,
   `state.py`, `scenarios.py`, `render.py`, `core/`) and note the type/lifetime
   mapping — the equivalent of bun's `PORTING.md` / `LIFETIMES.tsv`.
3. **The oracle is language-independent.** Drive your Rust from the same scenario
   entries; diff your events against the frozen eventlogs. A mismatch is a port
   bug, never an oracle bug.
4. **Stage it.** Get the crate compiling first (empty `scenario` bin), then make
   scenarios pass one at a time. Do not delete or weaken a scenario to make it
   pass — that is silent behavioral drift.
5. **Assume you're wrong.** The mismatch report names the first differing event
   (`index`, `expected`, `actual`); trace that event back to the Python line that
   produces it.

## Model requirement — single-shot output budget

The porter emits the **entire Rust crate as one JSON object**. A non-trivial port
(tictactoe: 14 Python files) exceeds **8192 output tokens**, so any model whose
single-reply output caps at 8192 (`deepseek-chat` / `deepseek-v4-pro-direct`) hits
`finish_reason: length` and returns a truncated, unparseable object — the run fails
with "model reply was not a JSON object". This is a model output ceiling, not a
proxy or task bug (DeepSeek delivers valid JSON well under the cap; it just can't
fit a whole crate). Use a large-output model: `gemini/gemini-3.1-pro-preview`
(native `json_schema`, ample output) ports tictactoe end-to-end at **0.75 parity**.
`gpt-5.x` via codex-native also has the headroom. Staging the port across multiple
turns/files would let smaller-output models participate — a future workflow variant.

## How you're run and scored

- The jesterky workflow (`dev_port_to_rust.json`) hands you the Python source and
  the contract, and collects your Rust crate as `{files: [{path, content}], porting_notes}`.
- `score_port.py --from-manifest <run.json> --source-task <task>` materializes
  your crate, `cargo build`s the `scenario` bin, runs every scenario, and diffs
  the events against the oracle → the parity score.
