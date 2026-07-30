#!/usr/bin/env bash
# Reference solution: install a strong pre-built candidate for verifier smoke.
set -euo pipefail

SUBDIR="${CANDIDATE_SUBDIR:-tictactoe}"
DEST="/workspace/candidates/${SUBDIR}/candidate_reference"
mkdir -p "$DEST"

REFERENCE="/task/solution/references/${GAMEBENCH_TASK:-tictactoe-singleplayer}/heuristic_policy.py"
if [[ ! -f "$REFERENCE" && "${GAMEBENCH_TASK:-tictactoe-singleplayer}" == "tictactoe-singleplayer" ]]; then
  REFERENCE="/task/solution/reference_heuristic_policy.py"
fi
if [[ ! -f "$REFERENCE" ]]; then
  echo "missing bundled reference policy for task ${GAMEBENCH_TASK:-unknown}: $REFERENCE" >&2
  exit 1
fi
cp "$REFERENCE" "$DEST/heuristic_policy.py"
