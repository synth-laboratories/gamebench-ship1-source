#!/usr/bin/env bash
# GameBench dev-port task: hand an agent a working Python engine, have it port to
# Rust, score by NEV parity. Drives the port through the jesterky engine's codex
# actor — DeepSeek/Gemini go via jesterky's native Responses↔chat proxy.
#
# Runs a MODEL MATRIX and records a score for EVERY model, including failures: a
# model that can't produce a compilable crate is a legitimate 0.0 data point, not
# an abort. DeepSeek truncates a whole-crate reply at its 8192-token output cap
# (see PORTING.md) → 0.0; Gemini has the headroom → real parity.
#
#   ./run.sh                                                    # matrix, source = frogs
#   SOURCE_TASK=tictactoe-singleplayer ./run.sh
#   MODELS="gemini/gemini-3.1-pro-preview" SOURCE_TASK=sokoban-singleplayer ./run.sh
set -uo pipefail   # NOT -e: a failing model must not abort the matrix.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEC="$HERE/dev_port_to_rust.json"
SOURCE_TASK="${SOURCE_TASK:-frogs-singleplayer}"
MODELS="${MODELS:-deepseek/deepseek-v4-pro-direct gemini/gemini-3.1-pro-preview}"
ENV_FILE="${ENV_FILE:-$HOME/Documents/GitHub/synth-ai/.env}"

key_for() {  # export the provider key the jesterky proxy needs (gpt-* needs none)
  case "$1" in
    deepseek/*) [ -z "${DEEPSEEK_API_KEY:-}" ] && [ -f "$ENV_FILE" ] && export DEEPSEEK_API_KEY="$(awk -F= '/^DEEPSEEK_API_KEY=/{print $2; exit}' "$ENV_FILE")" ;;
    gemini/*|gemini-*) [ -z "${GEMINI_API_KEY:-}" ] && [ -f "$ENV_FILE" ] && export GEMINI_API_KEY="$(awk -F= '/^GEMINI_API_KEY=/{print $2; exit}' "$ENV_FILE")" ;;
  esac
}

echo "== bundling $SOURCE_TASK python source → port job =="
python3 "$HERE/bundle_job.py" --source-task "$SOURCE_TASK" --out "$HERE/job.json"

for MODEL in $MODELS; do
  key_for "$MODEL"
  SLUG="$(echo "$MODEL" | tr '/' '_')"
  MANIFEST="$HERE/port.$SLUG.json"
  SCORE="$HERE/score.$SLUG.json"
  echo
  echo "== porting to Rust: $MODEL (via codex/jesterky) =="
  # Non-fatal: a truncated/failed reply leaves a status=failed manifest; we still score it.
  jesterky run "$SPEC" --actor codex --model "$MODEL" \
    --args-file "$HERE/job.json" --out "$MANIFEST" --run-id "dev-port-$SOURCE_TASK" || true
  echo "== scoring $MODEL against the NEV oracle =="
  python3 "$HERE/score_port.py" --from-manifest "$MANIFEST" --source-task "$SOURCE_TASK" --out "$SCORE" || true
done

echo
echo "== partial-results table ($SOURCE_TASK) =="
python3 - "$HERE" "$SOURCE_TASK" $MODELS <<'PY'
import json, sys
from pathlib import Path
here, task, *models = sys.argv[1], sys.argv[2], *sys.argv[3:]
print(f"{'model':<38} {'score':>6} {'pass':>7} {'files':>5}  detail")
for m in models:
    p = Path(here) / f"score.{m.replace('/', '_')}.json"
    if not p.is_file():
        print(f"{m:<38} {'—':>6} {'—':>7} {'—':>5}  no score written"); continue
    d = json.loads(p.read_text())
    passed, total = d.get("passed", 0), d.get("total", 0)
    detail = "ok" if d.get("build_ok") else (d.get("build_detail", "") or "").splitlines()[0][:44]
    print(f"{m:<38} {d.get('score', 0.0):>6} {f'{passed}/{total}':>7} {d.get('crate_files', 0):>5}  {detail}")
PY
