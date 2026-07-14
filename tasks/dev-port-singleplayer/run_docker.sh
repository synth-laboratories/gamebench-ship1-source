#!/usr/bin/env bash
# GameBench dev-port, DOCKER sandbox: codex runs INSIDE the jesterky-devport
# container (image toolchain, isolated), seeded workspace bind-mounted, host
# ~/.codex/auth.json mounted as the in-container CODEX_HOME. Same task + scoring
# as run_sandboxed.sh; the only difference is where the agent executes.
#
#   docker build -f Dockerfile.agentic -t jesterky-devport:latest .   # once
#   ./run_docker.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEC="$HERE/dev_port_to_rust.docker.json"
SOURCE_TASK="${SOURCE_TASK:-tictactoe-singleplayer}"
MODEL="${MODEL:-gpt-5.5}"
TRAIN="${TRAIN:-4}"

echo "== bundling $SOURCE_TASK → sandbox workspace job (train=$TRAIN) =="
python3 "$HERE/bundle_sandbox_job.py" --source-task "$SOURCE_TASK" --train "$TRAIN" --out "$HERE/job.sandbox.json"

MANIFEST="$HERE/port.docker.$(echo "$MODEL" | tr '/' '_').json"
echo "== porting in a DOCKER sandbox ($MODEL runs codex in-container) =="
jesterky run "$SPEC" --actor codex --model "$MODEL" \
  --args-file "$HERE/job.sandbox.json" --out "$MANIFEST" --run-id "dev-port-docker-$SOURCE_TASK" || true

echo "== scoring the captured crate against the full NEV oracle =="
python3 "$HERE/score_port.py" --from-manifest "$MANIFEST" --source-task "$SOURCE_TASK" \
  --out "$HERE/score.docker.$(echo "$MODEL" | tr '/' '_').json" || true
