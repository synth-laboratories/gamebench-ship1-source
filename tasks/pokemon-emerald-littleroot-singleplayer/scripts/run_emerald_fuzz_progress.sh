#!/usr/bin/env bash
set -uo pipefail

task_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
rom=${EMERALD_ORACLE_ROM:-/Users/joshuapurtell/Downloads/Pokemon - Emerald Version (USA, Europe).gba}
state=${EMERALD_ORACLE_STATE:-/Users/joshuapurtell/Documents/Codex/2026-07-30/emerald-gamebench-audit/work/emerald_oracle/02_starter.state}
oracle_checkpoint=${EMERALD_ORACLE_CHECKPOINT:-bedroom_idle}
output_dir=${EMERALD_FUZZ_OUTPUT_DIR:-/Users/joshuapurtell/Documents/Codex/2026-07-30/emerald-gamebench-audit/outputs}
random_cases=${EMERALD_FUZZ_RANDOM_CASES:-16}
steps=${EMERALD_FUZZ_STEPS:-64}
verbose=${EMERALD_FUZZ_VERBOSE:-0}
minimize=${EMERALD_FUZZ_MINIMIZE:-none}
minimize_limit=${EMERALD_FUZZ_MINIMIZE_LIMIT:-3}
minimize_max_replays=${EMERALD_FUZZ_MINIMIZE_MAX_REPLAYS:-64}
timestamp=$(date +%Y%m%d-%H%M%S)
report="$output_dir/emerald-progress-$timestamp-$$.json"
history="$output_dir/emerald-progress-history.tsv"
run_started=$(date +%s)

if [[ -t 1 ]]; then
  heading=$'\033[1;36m'
  success=$'\033[1;32m'
  warning=$'\033[1;33m'
  reset=$'\033[0m'
else
  heading=
  success=
  warning=
  reset=
fi

section() {
  printf '\n%s%s%s\n' "$heading" "$1" "$reset"
}

for dependency in cargo python3 docker jq column; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    echo "missing required command: $dependency" >&2
    exit 2
  fi
done
if [[ ! -f "$rom" ]]; then
  echo "ROM not found: $rom" >&2
  exit 2
fi
if [[ ! -f "$state" ]]; then
  echo "checkpoint not found: $state" >&2
  exit 2
fi

mkdir -p "$output_dir"
previous_report=$(ls -1t "$output_dir"/emerald-progress-*.json 2>/dev/null | head -n 1 || true)

cd "$task_dir"
git_revision=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
dirty_entries=$(git status --porcelain -- . 2>/dev/null | wc -l | tr -d ' ')

section "Build"
build_started=$(date +%s)
if ! cargo build --quiet --release --manifest-path gold_rust/Cargo.toml; then
  echo "Rust release build failed" >&2
  exit 2
fi
build_elapsed=$(( $(date +%s) - build_started ))
printf '%s✓%s release binary ready in %ss\n' "$success" "$reset" "$build_elapsed"

section "Differential fuzz"
fuzz_args=(
  --mode both
  --random-cases "$random_cases"
  --steps "$steps"
  --oracle-rom "$rom"
  --oracle-state "$state"
  --oracle-checkpoint "$oracle_checkpoint"
  --oracle-command "scripts/run_mgba_jsonl_oracle.sh '$rom' '$state' '$oracle_checkpoint'"
  --output "$report"
)
if [[ "$minimize" != "none" ]]; then
  fuzz_args+=(--minimize-mismatches "$minimize" --minimize-limit "$minimize_limit" --minimize-max-replays "$minimize_max_replays")
fi
python3 scripts/fuzz_emerald_differential.py "${fuzz_args[@]}"
fuzz_status=$?
run_elapsed=$(( $(date +%s) - run_started ))

if [[ $fuzz_status -gt 1 || ! -f "$report" ]]; then
  echo "fuzzer setup/protocol failure; inspect $report" >&2
  exit 2
fi

section "Headline numbers"
jq -r '
  def pct($good; $total):
    if $total == 0 then "—"
    else (((($good * 10000 / $total) | floor) / 100) | tostring) + "%"
    end;
  (.lanes[] | select(.lane == "rust_transport_contract")) as $rust |
  (.lanes[] | select(.lane == "source_behavior_oracle")) as $source |
  ($source.cases[] | select(.name == "published_bedroom_explorer_seed1")) as $published |
  ($source.cases | map(select(.origin == "deterministic random fuzz"))) as $random |
  ([ $source.cases[].proof_tape[]
     | select(.semantic_comparable == true) ] | length) as $state_checks |
  ($source.compared_source_frames - $source.pixel_mismatch_frames) as $exact_frames |
  ($state_checks - $source.semantic_boundary_mismatches) as $exact_states |
  (((($published.proof_tape | length) - 1) - $published.pixel_mismatch_frames)) as $published_exact |
  [
    ["headline","current"],
    ["fully exact tapes",
      (($source.case_count-$source.divergence_count)|tostring)+"/"+($source.case_count|tostring)+
      " ("+pct(($source.case_count-$source.divergence_count);$source.case_count)+")"],
    ["pixel-perfect frames",
      ($exact_frames|tostring)+"/"+($source.compared_source_frames|tostring)+
      " ("+pct($exact_frames;$source.compared_source_frames)+")"],
    ["exact state checks",
      ($exact_states|tostring)+"/"+($state_checks|tostring)+
      " ("+pct($exact_states;$state_checks)+")"],
    ["transport contracts",
      (($rust.case_count-$rust.violation_count)|tostring)+"/"+($rust.case_count|tostring)+
      " ("+pct(($rust.case_count-$rust.violation_count);$rust.case_count)+")"],
    ["published rollout frames",
      ($published_exact|tostring)+"/"+(((($published.proof_tape|length)-1))|tostring)+
      " exact; endpoint "+(if $published.final_comparison.classification=="exact" then "exact" else "wrong" end)],
    ["random tapes",
      (($random|map(select(.result=="exact"))|length)|tostring)+"/"+(($random|length)|tostring)+" exact"]
  ][] | @tsv
' "$report" | column -t -s $'\t'

if [[ -n "$previous_report" && -f "$previous_report" ]]; then
  jq -r --slurpfile previous "$previous_report" '
    def source($run): $run.lanes[] | select(.lane == "source_behavior_oracle");
    source($previous[0]) as $old |
    source(.) as $new |
    ($new.divergence_count-$old.divergence_count) as $tapes |
    ($new.pixel_mismatch_frames-$old.pixel_mismatch_frames) as $pixels |
    ($new.semantic_boundary_mismatches-$old.semantic_boundary_mismatches) as $states |
    "trend vs previous: tapes \($tapes), pixel errors \($pixels), state errors \($states)"
  ' "$report"
else
  printf 'trend: baseline run\n'
fi
printf 'run: %ss · revision %s · %s random tapes\n' "$run_elapsed" "$git_revision" "$random_cases"

if [[ "$minimize" != "none" ]]; then
  section "Minimized proofs"
  jq -r '
    (.lanes[] | select(.lane == "source_behavior_oracle").minimization.proofs) as $proofs |
    if ($proofs | length) == 0 then "no selected divergences were minimized"
    else
      ["case","kind","VBlanks","surface","proof"],
      ($proofs[] | [
        .case,.selected,
        ((.original_vblanks|tostring)+"→"+(.minimized_vblanks|tostring)),
        .attribution.surface,.proof_path
      ]) | @tsv
    end
  ' "$report" | column -t -s $'\t'
fi

if [[ "$verbose" == "1" ]]; then
section "Run identity"
jq -r \
  --arg revision "$git_revision" \
  --arg dirty "$dirty_entries task-local worktree entries" \
  --arg elapsed "${run_elapsed}s" \
  --arg corpus "$random_cases random × $steps VBlanks" '
  (.lanes[] | select(.lane == "source_behavior_oracle")) as $source |
  [
    ["field","value"],
    ["revision",$revision],
    ["worktree",$dirty],
    ["corpus",$corpus],
    ["elapsed",$elapsed],
    ["emulator",$source.emulator.version],
    ["image",($source.emulator_config.container_image_id | sub("^sha256:";"") | .[0:16])],
    ["ROM",($source.rom_sha256 | .[0:16])],
    ["checkpoint",($source.state_sha256 | .[0:16])]
  ][] | @tsv
' "$report" | column -t -s $'\t'

section "Health dashboard"
jq -r '
  def pct($good; $total):
    if $total == 0 then "—"
    else (((($good * 10000 / $total) | floor) / 100) | tostring) + "%"
    end;
  (.lanes[] | select(.lane == "rust_transport_contract")) as $rust |
  (.lanes[] | select(.lane == "source_behavior_oracle")) as $source |
  ([ $source.cases[].proof_tape[]
     | select(.semantic_comparable == true) ] | length) as $state_checks |
  ($source.compared_source_frames - $source.pixel_mismatch_frames) as $exact_frames |
  ($state_checks - $source.semantic_boundary_mismatches) as $exact_states |
  [
    ["gate","passed","total","rate","errors"],
    ["transport contracts",($rust.case_count-$rust.violation_count),$rust.case_count,
      pct(($rust.case_count-$rust.violation_count);$rust.case_count),$rust.violation_count],
    ["exact tapes",($source.case_count-$source.divergence_count),$source.case_count,
      pct(($source.case_count-$source.divergence_count);$source.case_count),$source.divergence_count],
    ["exact VBlanks",$exact_frames,$source.compared_source_frames,
      pct($exact_frames;$source.compared_source_frames),$source.pixel_mismatch_frames],
    ["exact state checks",$exact_states,$state_checks,
      pct($exact_states;$state_checks),$source.semantic_boundary_mismatches]
  ][] | @tsv
' "$report" | column -t -s $'\t'

section "Lane summary"
jq -r '
  ["lane","cases","failed","frames","pixel_errors","state_errors","result"],
  (.lanes[] |
    if .lane == "rust_transport_contract" then
      [.lane,.case_count,.violation_count,"—","—","—",.result]
    else
      [.lane,.case_count,.divergence_count,.compared_source_frames,
       .pixel_mismatch_frames,.semantic_boundary_mismatches,.result]
    end
  ) | @tsv
' "$report" | column -t -s $'\t'

if [[ -n "$previous_report" && -f "$previous_report" ]]; then
  section "Change from previous run"
  jq -r --slurpfile previous "$previous_report" '
    def source($run): $run.lanes[] | select(.lane == "source_behavior_oracle");
    def change($old; $new; $lower_is_better):
      ($new - $old) as $delta |
      if $delta == 0 then "0 →"
      elif ($lower_is_better and $delta < 0) or
           (($lower_is_better | not) and $delta > 0)
      then (($delta | tostring) + " ✓")
      else ((if $delta > 0 then "+" else "" end) + ($delta | tostring) + " !")
      end;
    source($previous[0]) as $old |
    source(.) as $new |
    [
      ["metric","previous","current","change"],
      ["failed tapes",$old.divergence_count,$new.divergence_count,
        change($old.divergence_count;$new.divergence_count;true)],
      ["pixel errors",$old.pixel_mismatch_frames,$new.pixel_mismatch_frames,
        change($old.pixel_mismatch_frames;$new.pixel_mismatch_frames;true)],
      ["state errors",$old.semantic_boundary_mismatches,$new.semantic_boundary_mismatches,
        change($old.semantic_boundary_mismatches;$new.semantic_boundary_mismatches;true)]
    ][] | @tsv
  ' "$report" | column -t -s $'\t'
  printf 'Compared with: %s\n' "$previous_report"
else
  section "Change from previous run"
  printf '%sNo earlier emerald-progress report found; this run is the baseline.%s\n' "$warning" "$reset"
fi

section "Mandatory tapes"
jq -r '
  ["tape","VBlanks","pixel_errors","state_errors","first_bad","first_pixels","final"],
  ((.lanes[] | select(.lane == "source_behavior_oracle")).cases[]
    | select(.origin != "deterministic random fuzz")
    | [
        .name,
        ((.proof_tape | length) - 1),
        .pixel_mismatch_frames,
        .semantic_boundary_mismatches,
        (if .first_mismatch then .first_mismatch.vblank else "—" end),
        (if .first_mismatch then .first_mismatch.pixel_diff.changed_pixels else 0 end),
        (if .final_comparison.pixels_equal and
            (.final_comparison.semantic_equal != false)
         then "exact" else .final_comparison.classification end)
      ])
  | @tsv
' "$report" | column -t -s $'\t'

section "Random corpus"
jq -r '
  ((.lanes[] | select(.lane == "source_behavior_oracle")).cases
    | map(select(.origin == "deterministic random fuzz"))) as $random |
  [
    ["cases","failed","VBlanks","pixel_errors","state_errors","exact_cases"],
    [
      ($random | length),
      ($random | map(select(.result != "exact")) | length),
      ($random | map(.compared_source_frames) | add),
      ($random | map(.pixel_mismatch_frames) | add),
      ($random | map(.semantic_boundary_mismatches) | add),
      ($random | map(select(.result == "exact")) | length)
    ]
  ][] | @tsv
' "$report" | column -t -s $'\t'

section "Top five offenders"
jq -r '
  ["tape","pixel_errors","state_errors","first_bad","first_pixels","final"],
  (((.lanes[] | select(.lane == "source_behavior_oracle")).cases
    | sort_by(.pixel_mismatch_frames, .semantic_boundary_mismatches)
    | reverse | .[:5])[]
    | [
        .name,
        .pixel_mismatch_frames,
        .semantic_boundary_mismatches,
        (if .first_mismatch then .first_mismatch.vblank else "—" end),
        (if .first_mismatch then .first_mismatch.pixel_diff.changed_pixels else 0 end),
        .final_comparison.classification
      ])
  | @tsv
' "$report" | column -t -s $'\t'
fi

if [[ ! -f "$history" ]]; then
  printf 'timestamp\trevision\tcases\tfailed\tframes\tpixel_errors\tstate_errors\tresult\treport\n' > "$history"
fi
jq -r \
  --arg timestamp "$timestamp" \
  --arg revision "$git_revision" \
  --arg report "$report" '
  (.lanes[] | select(.lane == "source_behavior_oracle")) as $source |
  [
    $timestamp,$revision,$source.case_count,$source.divergence_count,
    $source.compared_source_frames,$source.pixel_mismatch_frames,
    $source.semantic_boundary_mismatches,$source.result,$report
  ] | @tsv
' "$report" >> "$history"

if [[ "$verbose" == "1" ]]; then
  section "Recent history"
  {
    head -n 1 "$history"
    tail -n +2 "$history" | tail -n 5
  } | column -t -s $'\t'
fi

# Bedroom is a frozen acceptance surface.  Keep this after the report has
# been written so a blocked run still leaves a complete forensic artifact.
# Other authenticated checkpoints use this runner for exploratory work and
# must not silently inherit bedroom's fixed corpus counts.
if [[ "$oracle_checkpoint" == "bedroom_idle" ]]; then
  section "Bedroom regression gate"
  if ! python3 scripts/emerald_bedroom_gate.py --input "$report"; then
    echo "bedroom regression gate blocked this run" >&2
    exit 1
  fi
fi

printf '\n%sReport:%s  %s\n' "$heading" "$reset" "$report"
printf '%sHistory:%s %s\n' "$heading" "$reset" "$history"
if [[ "$verbose" != "1" ]]; then
  printf 'Deep tables: EMERALD_FUZZ_VERBOSE=1 %s\n' "$0"
fi
exit "$fuzz_status"
