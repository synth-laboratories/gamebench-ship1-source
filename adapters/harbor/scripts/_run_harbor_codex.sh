#!/usr/bin/env bash
# Compatibility wrapper: Codex Harbor agent (default).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GAMEBENCH_HARBOR_AGENT="${GAMEBENCH_HARBOR_AGENT:-codex}"
exec bash "$SCRIPT_DIR/_run_harbor_agent.sh" "$@"
