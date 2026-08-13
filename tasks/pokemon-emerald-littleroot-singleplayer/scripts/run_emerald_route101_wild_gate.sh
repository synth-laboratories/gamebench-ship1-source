#!/usr/bin/env bash
set -uo pipefail

task_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
rom=${EMERALD_ORACLE_ROM:-/Users/joshuapurtell/Downloads/Pokemon - Emerald Version (USA, Europe).gba}
state=${EMERALD_ROUTE101_WILD_STATE:-/Users/joshuapurtell/Documents/Codex/2026-07-30/emerald-gamebench-audit/work/emerald_oracle/v8_route101_wild_battle/route101_wild_battle.state}
output_dir=${EMERALD_FUZZ_OUTPUT_DIR:-/Users/joshuapurtell/Documents/Codex/2026-07-30/emerald-gamebench-audit/outputs}
timestamp=$(date +%Y%m%d-%H%M%S)
report="$output_dir/route101-wild-gate-$timestamp-$$.json"

cd "$task_dir"
cargo build --quiet --release --manifest-path gold_rust/Cargo.toml
python3 scripts/fuzz_emerald_differential.py \
  --mode both --segment route101_wild_battle --random-cases 0 --steps 64 \
  --oracle-rom "$rom" --oracle-state "$state" \
  --oracle-checkpoint route101_wild_battle \
  --oracle-command "scripts/run_mgba_jsonl_oracle.sh '$rom' '$state' route101_wild_battle" \
  --output "$report"
fuzz_status=$?
python3 scripts/emerald_route101_wild_gate.py --input "$report"
gate_status=$?
printf 'report: %s\n' "$report"
if [[ "$fuzz_status" -gt 1 || "$gate_status" -gt 1 ]]; then exit 2; fi
if [[ "$gate_status" -ne 0 ]]; then exit 1; fi
exit "$fuzz_status"
