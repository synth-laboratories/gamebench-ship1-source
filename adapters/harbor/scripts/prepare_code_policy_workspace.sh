#!/usr/bin/env bash
# Seed a Harbor code-policy workspace after docker extract.
set -euo pipefail

WORKSPACE="$1"
TASK_ID="$2"
CANDIDATE_SUBDIR="${3:-}"
BUNDLE_ROOT="$4"
BASELINE_REL="${5:-containers/codepolicy/heuristic_policy.py}"

if [[ -z "$CANDIDATE_SUBDIR" ]]; then
  # craftax-singleplayer -> craftax; never silently fall back to tictactoe.
  CANDIDATE_SUBDIR="${TASK_ID%-singleplayer}"
  CANDIDATE_SUBDIR="${CANDIDATE_SUBDIR%-multiplayer}"
fi
if [[ -z "$CANDIDATE_SUBDIR" || "$CANDIDATE_SUBDIR" == "$TASK_ID" ]]; then
  echo "prepare_code_policy_workspace: cannot derive candidate subdir from task=$TASK_ID" >&2
  exit 2
fi

mkdir -p "$WORKSPACE/candidates/$CANDIDATE_SUBDIR" "$WORKSPACE/workspace"

cp "$BUNDLE_ROOT/files/run_gamebench_hillclimb_task.py" "$WORKSPACE/workspace/"

BASELINE="$WORKSPACE/gamebench/tasks/$TASK_ID/$BASELINE_REL"
if [[ ! -f "$BASELINE" ]]; then
  echo "prepare_code_policy_workspace: baseline missing at $BASELINE" >&2
  exit 2
fi

cat > "$WORKSPACE/AGENTS.md" <<EOF
# Harbor code-policy workspace

- Task: \`$TASK_ID\`
- Candidate dir: \`candidates/$CANDIDATE_SUBDIR/<candidate_id>/heuristic_policy.py\`
- Baseline: \`gamebench/tasks/$TASK_ID/$BASELINE_REL\`

Run before finishing:

\`\`\`bash
python3 workspace/run_gamebench_hillclimb_task.py run --output-root . --candidate-root candidates
python3 workspace/run_gamebench_hillclimb_task.py score --output-root .
\`\`\`
EOF

# Host agents (pi/cursor) prefer instruction.md over AGENTS.md. Stage a
# task-specific copy so a stale bundle prompt (e.g. rogue gen4) cannot hijack
# craftax / other lanes.
cat > "$WORKSPACE/instruction.md" <<EOF
# GameBench code policy hillclimb — \`$TASK_ID\`

Your **cwd is this workspace root**. \`AGENTS.md\` matches this lane.

## Objective

Improve the \`$TASK_ID\` code policy. Write candidates only under
\`candidates/$CANDIDATE_SUBDIR/<candidate_id>/heuristic_policy.py\`.
The verifier passes only when best non-baseline uplift is **≥ +0.01**.

## Do this

1. Study \`gamebench/tasks/$TASK_ID/$BASELINE_REL\`.
2. Add new candidate(s) under \`candidates/$CANDIDATE_SUBDIR/\` only.
   Do not create \`candidates/rogue/\`, \`candidates/tictactoe/\`, or any other
   family unless that is the subdir above.
3. Do not modify or delete existing candidate directories; only add new ones.
4. Run sequentially:

\`\`\`bash
python3 workspace/run_gamebench_hillclimb_task.py run --output-root . --candidate-root candidates
python3 workspace/run_gamebench_hillclimb_task.py score --output-root .
\`\`\`

5. If uplift is below +0.01, iterate with another candidate. Do not stop after a
   sub-threshold lift.
6. Do not edit files under \`gamebench/tasks/\`.
EOF
