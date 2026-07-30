#!/usr/bin/env bash
set -euo pipefail

TASKS_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${GAMEBENCH_TTT_MP_IMAGE:-gamebench-tictactoe-multiplayer-groq}"
PORT="${PORT:-8093}"

docker build -t "$IMAGE" -f "$ROOT/container/Dockerfile" "$TASKS_ROOT"

if [[ -z "${GROQ_API_KEY:-}" ]]; then
  if [[ -f "$HOME/Documents/GitHub/synth-ai/.env" ]]; then
    export GROQ_API_KEY="$(awk -F= '/^GROQ_API_KEY=/{print $2; exit}' "$HOME/Documents/GitHub/synth-ai/.env")"
  fi
fi

if [[ -z "${GROQ_API_KEY:-}" ]]; then
  echo "GROQ_API_KEY is required (export it or add to synth-ai/.env)" >&2
  exit 1
fi

docker rm -f gamebench-ttt-mp-groq 2>/dev/null || true
docker run --name gamebench-ttt-mp-groq \
  -p "${PORT}:8091" \
  -e GROQ_API_KEY \
  -e GROQ_AGENT_0_MODEL="${GROQ_AGENT_0_MODEL:-llama-3.3-70b-versatile}" \
  -e GROQ_AGENT_1_MODEL="${GROQ_AGENT_1_MODEL:-llama-3.1-8b-instant}" \
  "$IMAGE"
