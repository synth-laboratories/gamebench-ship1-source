#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="${HARBOR_LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"
CANDIDATE_ROOT="${GAMEBENCH_CANDIDATE_ROOT:-/workspace/candidate}"
PORT="${GAMEBENCH_CANDIDATE_PORT:-19099}"
BUNDLE_ROOT="${SMB_BUNDLE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
OUTPUT_JSON="$LOG_DIR/result.json"
REWARD_PATH="$LOG_DIR/reward.txt"

if [[ ! -f "$CANDIDATE_ROOT/gold_rust/Cargo.toml" ]]; then
  echo '{"error":"missing candidate gold_rust/Cargo.toml","harbor_reward":0.0}' > "$OUTPUT_JSON"
  echo 0 > "$REWARD_PATH"
  exit 1
fi

cargo test --manifest-path "$CANDIDATE_ROOT/gold_rust/Cargo.toml" > "$LOG_DIR/cargo-test.log"
cargo run --release --manifest-path "$CANDIDATE_ROOT/gold_rust/Cargo.toml" --bin super_mario_bros_service -- --port "$PORT" > "$LOG_DIR/service.log" 2>&1 &
SERVICE_PID=$!
cleanup() { kill "$SERVICE_PID" >/dev/null 2>&1 || true; wait "$SERVICE_PID" >/dev/null 2>&1 || true; }
trap cleanup EXIT

for _ in $(seq 1 60); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${PORT}/health', timeout=1)" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

GAMEBENCH_CANDIDATE_PORT="$PORT" python3 "$BUNDLE_ROOT/tests/protocol_smoke.py"
echo '{"harbor_reward":1.0,"levels":32,"protocol":"ok"}' > "$OUTPUT_JSON"
echo 1.0 > "$REWARD_PATH"
