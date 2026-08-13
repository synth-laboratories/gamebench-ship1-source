#!/usr/bin/env bash
set -uo pipefail

task_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
rom=${EMERALD_ORACLE_ROM:-/Users/joshuapurtell/Downloads/Pokemon - Emerald Version (USA, Europe).gba}
state=${EMERALD_ORACLE_STATE:-/Users/joshuapurtell/Documents/Codex/2026-07-30/emerald-gamebench-audit/work/emerald_oracle/02_starter.state}
output_dir=${EMERALD_FUZZ_OUTPUT_DIR:-/Users/joshuapurtell/Documents/Codex/2026-07-30/emerald-gamebench-audit/outputs}
random_cases=${EMERALD_MAYS_RANDOM_CASES:-16}
steps=${EMERALD_MAYS_RANDOM_STEPS:-64}
timestamp=$(date +%Y%m%d-%H%M%S)
report="$output_dir/mays-house-progress-$timestamp-$$.json"

for dependency in cargo python3 docker jq column; do
  command -v "$dependency" >/dev/null 2>&1 || {
    echo "missing required command: $dependency" >&2
    exit 2
  }
done
[[ -f "$rom" ]] || { echo "ROM not found: $rom" >&2; exit 2; }
[[ -f "$state" ]] || { echo "checkpoint not found: $state" >&2; exit 2; }

cd "$task_dir"
cargo build --quiet --release --manifest-path gold_rust/Cargo.toml
python3 scripts/fuzz_emerald_differential.py \
  --mode both \
  --segment mays_house_exit \
  --random-cases "$random_cases" \
  --steps "$steps" \
  --oracle-rom "$rom" \
  --oracle-state "$state" \
  --oracle-checkpoint bedroom_idle \
  --oracle-command "scripts/run_mgba_jsonl_oracle.sh '$rom' '$state' bedroom_idle" \
  --output "$report"
fuzz_status=$?
[[ -f "$report" ]] || { echo "fuzzer did not write $report" >&2; exit 2; }

jq -r '
  def pct($good; $total): if $total == 0 then "—" else (((($good * 10000 / $total) | floor) / 100) | tostring) + "%" end;
  (.lanes[] | select(.lane == "rust_transport_contract")) as $transport |
  (.lanes[] | select(.lane == "source_behavior_oracle")) as $source |
  ([ $source.cases[].proof_tape[] | select(.semantic_comparable == true) ] | length) as $states |
  ($source.compared_source_frames - $source.pixel_mismatch_frames) as $exact_frames |
  ($states - $source.semantic_boundary_mismatches) as $exact_states |
  [
    ["headline", "current"],
    ["segment", ($source.coverage_segment // "mays_house_exit")],
    ["authenticated checkpoint", $source.oracle_checkpoint],
    ["fully exact tapes", (($source.case_count - $source.divergence_count)|tostring)+"/"+($source.case_count|tostring)+" ("+pct(($source.case_count-$source.divergence_count);$source.case_count)+")"],
    ["pixel-perfect VBlanks", ($exact_frames|tostring)+"/"+($source.compared_source_frames|tostring)+" ("+pct($exact_frames;$source.compared_source_frames)+")"],
    ["exact state checks", ($exact_states|tostring)+"/"+($states|tostring)+" ("+pct($exact_states;$states)+")"],
    ["transport contracts", (($transport.case_count-$transport.violation_count)|tostring)+"/"+($transport.case_count|tostring)+" ("+pct(($transport.case_count-$transport.violation_count);$transport.case_count)+")"],
    ["mandatory tapes", (($source.cases | map(select(.origin != "deterministic random fuzz" and .result == "exact")) | length)|tostring)+"/"+(($source.cases | map(select(.origin != "deterministic random fuzz")) | length)|tostring)],
    ["random tapes", (($source.cases | map(select(.origin == "deterministic random fuzz" and .result == "exact")) | length)|tostring)+"/"+(($source.cases | map(select(.origin == "deterministic random fuzz")) | length)|tostring)]
  ][] | @tsv
' "$report" | column -t -s $'\t'
printf 'report: %s\n' "$report"

# Keep this segment's corpus and authenticated identity fixed.  The fuzzer
# reports exactness, while this reader prevents a future corpus reduction or
# checkpoint/segment substitution from turning into a false green run.
gate_status=0
python3 scripts/emerald_mays_house_gate.py --input "$report" || gate_status=$?

if [[ "$fuzz_status" -gt 1 ]]; then
  exit 2
fi
if [[ "$gate_status" -gt 1 ]]; then
  exit 2
fi
if [[ "$gate_status" -ne 0 ]]; then
  exit 1
fi
exit "$fuzz_status"
