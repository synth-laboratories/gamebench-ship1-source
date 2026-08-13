#!/usr/bin/env bash
set -u

task_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cases="${1:-10}"
steps="${2:-32}"
campaign="${3:-navigation-v0}"
run_dir="/tmp/nethack-fuzz-$(date -u +%Y%m%dT%H%M%SZ)"
reuse_run_json="${NETHACK_FUZZ_RUN_JSON:-}"
if [[ -n "$reuse_run_json" ]]; then
  run_dir="$(cd "$(dirname "$reuse_run_json")" && pwd)"
fi
oracle_python="${NLE_PYTHON:-$task_dir/.venv/bin/python}"
output_dir="${NETHACK_FUZZ_OUTPUT_DIR:-/Users/joshuapurtell/Documents/Codex/2026-07-30/gamebench-nethack-netherite/outputs}"
report="$output_dir/nethack-progress-$(date +%Y%m%d-%H%M%S)-$$.json"

cd "$task_dir"

for dependency in python3 jq column; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    echo "missing required command: $dependency" >&2
    exit 2
  fi
done

if ! "$oracle_python" -c "import nle" >/dev/null 2>&1; then
  if [[ -n "${NLE_PYTHON:-}" ]]; then
    echo "NLE_PYTHON does not point to a Python environment containing nle." >&2
    exit 2
  fi
  if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required to bootstrap the task-local NLE environment." >&2
    exit 2
  fi
  echo "Bootstrapping task-local NLE oracle environment..." >&2
  uv venv --python 3.10 .venv >/dev/null 2>&1
  uv pip install --python .venv/bin/python cmake >/dev/null 2>&1
  PATH="$task_dir/.venv/bin:$PATH" CMAKE_POLICY_VERSION_MINIMUM=3.5 \
    uv pip install --python .venv/bin/python -r requirements-nle-fuzz.txt >/dev/null 2>&1
fi

mkdir -p "$output_dir"
judge_report="${NETHACK_FUZZ_JUDGE_JSON:-$run_dir.frozen-judge.json}"
if [[ -z "${NETHACK_FUZZ_JUDGE_JSON:-}" ]]; then
  python3 scripts/judge_nle_tapes.py --lane both --report "$judge_report" >/dev/null || {
    echo "frozen tape contract failed; inspect $judge_report" >&2
    exit 2
  }
fi

if [[ -z "$reuse_run_json" ]]; then
  fuzzer_stdout="$run_dir.fuzzer.stdout"
  fuzzer_stderr="$run_dir.fuzzer.stderr"
  PYTHONWARNINGS=ignore "$oracle_python" scripts/fuzz_nle_differential.py \
    --cases "$cases" \
    --steps "$steps" \
    --seed 20260725 \
    --lane both \
    --campaign "$campaign" \
    --output "$run_dir" >"$fuzzer_stdout" 2>"$fuzzer_stderr" || fuzz_status=$?
else
  fuzz_status=0
fi

run_json="${reuse_run_json:-$run_dir/run.json}"
if [[ ! -f "$run_json" ]]; then
  echo "Fuzzer did not produce $run_json (exit ${fuzz_status:-0})." >&2
  if [[ -f "${fuzzer_stderr:-}" ]]; then sed -n '1,120p' "$fuzzer_stderr" >&2; fi
  exit "${fuzz_status:-1}"
fi

python3 - "$judge_report" "$run_json" "$report" <<'PY'
import collections
import json
import pathlib
import sys

from scripts.progress_scoring import source_behavior_result, source_trace_metrics
from scripts.scheduler_fov_validity import require_equal_lane_denominators

judge = json.load(open(sys.argv[1]))
run = json.load(open(sys.argv[2]))
report_path = pathlib.Path(sys.argv[3])
coverage = run["coverage"]
action_ids = coverage["action_ids"]

errors = collections.defaultdict(list)
malformed_contracts = []
action_counts = {
    case["fixture_id"]: len([
        line for line in
        (pathlib.Path(case["artifact"]) / "actions.jsonl").read_text().splitlines()
        if line.strip()
    ])
    for case in run["reports"]
}


def display_value(value, limit=120):
    text = repr(value).replace("\t", " ").replace("\n", "\\n")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def contract_metrics(contract_key, error_kind):
    comparisons = 0
    unjudgeable = 0
    failed_cases = 0
    failed_comparisons = 0
    error_count = 0
    malformed = []
    for case in run["reports"]:
        case_errors = set()
        try:
            case_comparisons = require_equal_lane_denominators(case["lanes"], contract_key)
        except ValueError as exc:
            # Keep the fail-hard validity rule, but materialize the failure in
            # the progress artifact so a malformed dual-lane run still prints
            # a useful table instead of dying before a report is written.
            malformed.append({"case": case["fixture_id"], "error": str(exc)})
            continue
        case_unjudgeable = set()
        for lane in case["lanes"]:
            contract = lane[contract_key]
            case_unjudgeable.add(int(contract.get("unjudgeable_surface_record_count", 0)))
            for error in contract["errors"]:
                case_errors.add(
                    (
                        int(error.get("step", -1)),
                        str(error.get("path", "")),
                        display_value(error.get("expected")),
                        display_value(error.get("actual")),
                    )
                )
        if len(case_unjudgeable) != 1:
            malformed.append(
                {
                    "case": case["fixture_id"],
                    "error": f"{case['fixture_id']}: {contract_key} unjudgeable counts differ across gold lanes",
                }
            )
            continue
        comparisons += case_comparisons
        unjudgeable += case_unjudgeable.pop()
        error_count += len(case_errors)
        failed_steps = {error[0] for error in case_errors}
        failed_comparisons += len(failed_steps)
        failed_cases += int(bool(case_errors))
    malformed_contracts.extend({"contract": contract_key, **item} for item in malformed)
    if malformed:
        result = "malformed"
    elif comparisons == 0:
        result = "not_exercised"
    elif failed_cases:
        result = "errors_found"
    elif unjudgeable:
        result = "partially_unjudgeable"
    else:
        result = "pass"
    return {
        "failed_cases": failed_cases,
        "turns": comparisons,
        "unjudgeable_turns": unjudgeable,
        "pixel_errors": error_count if error_kind == "pixel" else 0,
        "state_errors": error_count if error_kind == "state" else 0,
        "score": round(100.0 * max(0, comparisons - failed_comparisons) / comparisons, 1) if comparisons and not malformed else None,
        "result": result,
        "malformed_count": len(malformed),
    }


def specials_metrics():
    totals = collections.Counter()
    failed_cases = 0
    errors_count = 0
    malformed = []
    for case in run["reports"]:
        lane_metrics = []
        case_errors = set()
        for lane in case["lanes"]:
            contract = lane["specials_oracle_v1"]
            metrics = tuple(
                int(contract[key])
                for key in (
                    "zero_comparisons",
                    "pet_comparisons",
                    "unjudgeable_cells",
                    "unsupported_source_cells",
                    "unmaterialized_pet_cells",
                )
            )
            lane_metrics.append(metrics)
            for error in contract["errors"]:
                case_errors.add(
                    (
                        int(error.get("step", -1)),
                        str(error.get("path", "")),
                        display_value(error.get("expected")),
                        display_value(error.get("actual")),
                    )
                )
        if len(set(lane_metrics)) != 1:
            malformed.append(
                {
                    "case": case["fixture_id"],
                    "error": f"{case['fixture_id']}: specials denominators differ across gold lanes",
                }
            )
            continue
        zero, pets, unknown, unsupported, unmaterialized = lane_metrics[0]
        totals.update(
            zero_comparisons=zero,
            pet_comparisons=pets,
            unjudgeable_cells=unknown,
            unsupported_source_cells=unsupported,
            unmaterialized_pet_cells=unmaterialized,
        )
        failed_cases += int(bool(case_errors))
        errors_count += len(case_errors)
    pet_denominator = totals["pet_comparisons"] + totals["unmaterialized_pet_cells"]
    malformed_contracts.extend({"contract": "specials_oracle_v1", **item} for item in malformed)
    if malformed:
        result = "malformed"
    elif failed_cases:
        result = "errors_found"
    elif totals["unjudgeable_cells"]:
        result = "partially_unjudgeable"
    elif totals["zero_comparisons"] or totals["pet_comparisons"]:
        result = "pass"
    else:
        result = "not_exercised"
    return {
        "failed_cases": failed_cases,
        "turns": pet_denominator,
        "unjudgeable_turns": totals["unjudgeable_cells"],
        "pixel_errors": 0,
        "state_errors": errors_count,
        # Score positive pet semantics only. Millions of zero cells remain
        # explicit negative-control coverage but cannot dilute this score.
        "score": round(100.0 * totals["pet_comparisons"] / pet_denominator, 1) if pet_denominator and not malformed else None,
        "result": result,
        "malformed_count": len(malformed),
        **dict(totals),
    }


source = source_trace_metrics(run["reports"], action_counts, lanes_key="lanes")
heldout = source_trace_metrics(run["reports"], action_counts, lanes_key="heldout_lanes")
prompt_mode = contract_metrics("prompt_mode_oracle_v1", "state")
turn_consumption = contract_metrics("turn_consumption_oracle_v1", "state")
terminal_ui = contract_metrics("terminal_ui_oracle_v1", "pixel")
specials = specials_metrics()
terminal_boundary = contract_metrics("terminal_boundary_oracle_v1", "state")
seeded_outcome = contract_metrics("seeded_outcome_oracle_v1", "state")
visibility_entity = contract_metrics("visibility_entity_transition_oracle_v1", "state")

repeatability_failed = sum(case["oracle_repeatability"]["status"] != "pass" for case in run["reports"])
repeatability_steps = sum(int(case["oracle_repeatability"]["comparison_steps"]) for case in run["reports"])
checkpoint_failed = sum(case["checkpoint_replay_contract"]["status"] != "pass" for case in run["reports"])
checkpoint_comparisons = sum(int(case["checkpoint_replay_contract"]["comparisons"]) for case in run["reports"])
checkpoint_errors = sum(int(case["checkpoint_replay_contract"]["error_count"]) for case in run["reports"])

prefix_score = source["score"]
coverage_score = 100.0 * action_ids["nle_stepped_count"] / action_ids["pinned_count"]

for case in run["reports"]:
    for lane in case["lanes"]:
        difference = lane["strict_snapshot_v1"].get("first_difference")
        if not difference:
            continue
        action = difference.get("action") or {}
        key = (
            case["fixture_id"],
            difference["step"],
            action.get("action_name", ""),
            difference["path"],
            repr(difference.get("expected")),
            repr(difference.get("actual")),
        )
        errors[key].append(lane["lane"])

error_rows = []
for key, lanes in sorted(errors.items()):
    case_id, step, action, path, expected, actual = key
    error_rows.append(
        {
            "case": case_id.removeprefix("fuzz-case-"),
            "lanes": ",".join(sorted(lanes)),
            "step": step,
            "action": action,
            "field": path,
            "oracle": expected,
            "gold": actual,
        }
    )

contract_error_rows = []
contract_keys = (
    "prompt_mode_oracle_v1",
    "turn_consumption_oracle_v1",
    "terminal_ui_oracle_v1",
    "specials_oracle_v1",
    "terminal_boundary_oracle_v1",
    "seeded_outcome_oracle_v1",
    "visibility_entity_transition_oracle_v1",
)
for case in run["reports"]:
    short_case = case["fixture_id"].removeprefix("fuzz-case-")
    for contract_key in contract_keys:
        grouped = collections.defaultdict(list)
        for lane in case["lanes"]:
            for error in lane[contract_key]["errors"]:
                key = (
                    int(error.get("step", -1)),
                    str(error.get("path", contract_key)),
                    display_value(error.get("expected")),
                    display_value(error.get("actual")),
                )
                grouped[key].append(lane["lane"])
        if grouped:
            (step, field, expected, actual), lanes = sorted(grouped.items())[0]
            contract_error_rows.append(
                {
                    "lane": contract_key.removesuffix("_v1"),
                    "case": short_case,
                    "gold_lane": ",".join(sorted(lanes)),
                    "step": step,
                    "field": field,
                    "oracle": expected,
                    "gold": actual,
                }
            )
    heldout_differences = [
        (lane["lane"], lane["strict_snapshot_v1"].get("first_difference"))
        for lane in case["heldout_lanes"]
        if lane["strict_snapshot_v1"].get("first_difference")
    ]
    if heldout_differences:
        lane_name, difference = heldout_differences[0]
        contract_error_rows.append(
            {
                "lane": "heldout_state_oracle",
                "case": short_case,
                "gold_lane": lane_name,
                "step": difference["step"],
                "field": difference["path"],
                "oracle": display_value(difference.get("expected")),
                "gold": display_value(difference.get("actual")),
            }
        )
    repeat_difference = case["oracle_repeatability"].get("first_difference")
    if repeat_difference:
        contract_error_rows.append(
            {
                "lane": "oracle_repeatability",
                "case": short_case,
                "gold_lane": "nle",
                "step": -1,
                "field": repeat_difference["path"],
                "oracle": display_value(repeat_difference.get("expected")),
                "gold": display_value(repeat_difference.get("actual")),
            }
        )
    checkpoint_errors_for_case = case["checkpoint_replay_contract"]["errors"]
    if checkpoint_errors_for_case:
        error = checkpoint_errors_for_case[0]
        contract_error_rows.append(
            {
                "lane": "checkpoint_replay_contract",
                "case": short_case,
                "gold_lane": error.get("lane", "unknown"),
                "step": case["checkpoint_replay_contract"]["cut"],
                "field": error.get("path", "checkpoint_replay_contract"),
                "oracle": display_value(error.get("expected")),
                "gold": display_value(error.get("actual")),
            }
        )

payload = {
    "schema": "gamebench.nethack.progress.v1",
    "campaign": run["campaign"],
    "artifact_root": str(pathlib.Path(sys.argv[2]).parent),
    "scores": {
        "exact_prefix_percent": prefix_score,
        "action_coverage_percent": coverage_score,
    },
    "lanes": [
        {
            "lane": "frozen_tape_contract",
            "case_count": judge["counts"]["fixtures"],
            "failure_count": len(judge["failures"]),
            "turns": None,
            "pixel_errors": None,
            "state_errors": None,
            "score": 100.0 if not judge["failures"] else 0.0,
            "result": judge["status"],
        },
        {
            "lane": "source_behavior_oracle",
            "case_count": run["cases"],
            "failure_count": source["failed_cases"],
            "turns": source["turns"],
            "pixel_errors": source["pixel_errors"],
            "state_errors": source["state_errors"],
            "score": prefix_score,
            "result": source_behavior_result(source),
            "unjudgeable_turns": source["unjudgeable_turns"],
            "malformed_count": 0,
        },
        {
            "lane": "source_state_eligibility",
            "case_count": run["cases"],
            "failure_count": 0,
            "turns": source["turns"],
            "unjudgeable_turns": source["unjudgeable_turns"],
            "pixel_errors": 0,
            "state_errors": source["unjudgeable_turns"],
            "score": round(100.0 * source["turns"] / (source["turns"] + source["unjudgeable_turns"]), 1) if source["turns"] + source["unjudgeable_turns"] else None,
            "result": "eligible" if source["unjudgeable_turns"] == 0 else "unjudgeable",
            "malformed_count": 0,
        },
        {
            "lane": "prompt_mode_oracle",
            "case_count": run["cases"],
            "failure_count": prompt_mode["failed_cases"],
            **{key: prompt_mode[key] for key in ("turns", "pixel_errors", "state_errors", "score", "result", "malformed_count")},
        },
        {
            "lane": "turn_consumption_oracle",
            "case_count": run["cases"],
            "failure_count": turn_consumption["failed_cases"],
            **{key: turn_consumption[key] for key in ("turns", "pixel_errors", "state_errors", "score", "result", "malformed_count")},
        },
        {
            "lane": "terminal_ui_oracle",
            "case_count": run["cases"],
            "failure_count": terminal_ui["failed_cases"],
            **{key: terminal_ui[key] for key in ("turns", "pixel_errors", "state_errors", "score", "result", "malformed_count")},
        },
        {
            "lane": "specials_oracle",
            "case_count": run["cases"],
            "failure_count": specials["failed_cases"],
            **{key: specials[key] for key in ("turns", "unjudgeable_turns", "pixel_errors", "state_errors", "score", "result", "malformed_count")},
            "zero_comparisons": specials["zero_comparisons"],
            "pet_comparisons": specials["pet_comparisons"],
            "unsupported_source_cells": specials["unsupported_source_cells"],
            "unmaterialized_pet_cells": specials["unmaterialized_pet_cells"],
        },
        {
            "lane": "terminal_boundary_oracle",
            "case_count": run["cases"],
            "failure_count": terminal_boundary["failed_cases"],
            **{key: terminal_boundary[key] for key in ("turns", "pixel_errors", "state_errors", "score", "result", "malformed_count")},
        },
        {
            "lane": "seeded_outcome_oracle",
            "case_count": run["cases"],
            "failure_count": seeded_outcome["failed_cases"],
            **{key: seeded_outcome[key] for key in ("turns", "pixel_errors", "state_errors", "score", "result", "malformed_count")},
        },
        {
            "lane": "visibility_entity_transition_oracle",
            "case_count": run["cases"],
            "failure_count": visibility_entity["failed_cases"],
            **{key: visibility_entity[key] for key in ("turns", "unjudgeable_turns", "pixel_errors", "state_errors", "score", "result", "malformed_count")},
        },
        {
            "lane": "oracle_repeatability",
            "case_count": run["cases"],
            "failure_count": repeatability_failed,
            "turns": repeatability_steps,
            "pixel_errors": 0,
            "state_errors": repeatability_failed,
            "score": round(100.0 * (run["cases"] - repeatability_failed) / run["cases"], 1),
            "result": "pass" if repeatability_failed == 0 else "errors_found",
            "malformed_count": 0,
        },
        {
            "lane": "heldout_state_oracle",
            "case_count": run["cases"],
            "failure_count": heldout["failed_cases"],
            "turns": heldout["turns"],
            "pixel_errors": heldout["pixel_errors"],
            "state_errors": heldout["state_errors"],
            "score": heldout["score"],
            "result": source_behavior_result(heldout),
            "malformed_count": 0,
        },
        {
            "lane": "checkpoint_replay_contract",
            "case_count": run["cases"],
            "failure_count": checkpoint_failed,
            "turns": checkpoint_comparisons,
            "pixel_errors": 0,
            "state_errors": checkpoint_errors,
            "score": round(100.0 * max(0, checkpoint_comparisons - checkpoint_errors) / checkpoint_comparisons, 1) if checkpoint_comparisons else None,
            "result": "pass" if checkpoint_failed == 0 else "errors_found",
            "malformed_count": 0,
        },
    ],
    "coverage": {
        "actions_exercised": action_ids["nle_stepped_count"],
        "actions_pinned": action_ids["pinned_count"],
        "score_percent": coverage_score,
        "novel_signatures": len(coverage["novelty_signatures"]),
    },
    "first_errors": error_rows,
    "contract_errors": contract_error_rows,
    "report_integrity_errors": malformed_contracts,
    "raw_fuzz_report": sys.argv[2],
    "frozen_judge_report": sys.argv[1],
}
report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(f"wrote {report_path}")
PY

jq -r '
  ["lane","cases","failed","turns","unjudgeable","pixel_errors","state_errors","score","malformed","result"],
  (.lanes[] |
    [.lane,.case_count,.failure_count,
     (.turns // "—"),(.unjudgeable_turns // "—"),(.pixel_errors // "—"),(.state_errors // "—"),
     (if .score == null then "—" else ((.score | tostring) + "%") end),(.malformed_count // 0),.result]
) | @tsv
' "$report" | column -t -s $'\t'

printf '\nfirst errors\n'
jq -r '
  ["case","lanes","step","action","field","oracle","gold"],
  (.first_errors[] | [.case,.lanes,.step,.action,.field,.oracle,.gold]) | @tsv
' "$report" | column -t -s $'\t'

if [[ $(jq '.contract_errors | length' "$report") -gt 0 ]]; then
  printf '\ncontract errors (first per lane/case)\n'
  jq -r '
    ["lane","case","gold_lane","step","field","oracle","gold"],
    (.contract_errors[] | [.lane,.case,.gold_lane,.step,.field,.oracle,.gold]) | @tsv
  ' "$report" | column -t -s $'\t'
fi

if [[ $(jq '.report_integrity_errors | length' "$report") -gt 0 ]]; then
  printf '\nreport integrity errors (fail-closed)\n'
  jq -r '
    ["contract","case","error"],
    (.report_integrity_errors[] | [.contract,.case,.error]) | @tsv
  ' "$report" | column -t -s $'\t'
fi

printf '\nReport: %s\n' "$report"
if [[ $(jq '.report_integrity_errors | length' "$report") -gt 0 ]]; then
  exit 2
fi
exit "${fuzz_status:-0}"
