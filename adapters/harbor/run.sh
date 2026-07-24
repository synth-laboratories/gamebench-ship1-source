#!/usr/bin/env bash
# Unified Harbor adapter — all four GameBench eval families.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$SCRIPT_DIR/scripts"
source "$SCRIPTS/_lib.sh"

usage() {
  cat <<'EOF'
Usage: ./adapters/harbor/run.sh <family> <command> <task_id> [options]

Families:
  dev                 Engine rebuild / NEV gold spectrum
  code-policy         Code policy DEO hillclimb
  puzzle              Policy puzzle diagnosis
  cybernetic          Token-budget cybernetic uplift

Commands (per family):
  verify <task_id>              Reference solution passes verifier (no agent)
  codex <task_id>               Codex Harbor agent + verifier
  pi <task_id>                  Host Pi agent + verifier (code-policy)
  cursor <task_id>              Host cursor-agent + verifier (code-policy)
  list                          List task_ids for this family

Legacy shortcuts (still supported):
  list                          All task_ids
  verify <task_id>              dev reference verify
  codex <task_id>               dev codex (or legacy per-env script)
  puzzle verify|codex             code_policy_puzzles on tictactoe default puzzle
  smoke crafter-singleplayer      Crafter dev smoke

Environment:
  GAMEBENCH_EVALS_ROOT          evals repo (default: ~/Documents/GitHub/evals)
  GAMEBENCH_HARBOR_MODEL        agent model (default: openai/gpt-5.4-mini)
  GAMEBENCH_HARBOR_EFFORT       reasoning effort (default: low)
  GAMEBENCH_HARBOR_AGENT        codex|pi|cursor (set by subcommand)
  GAMEBENCH_HARBOR_OUT          output dir for runs (use per-lane for parallel)
  PUZZLE_ID                     puzzle id for puzzle family
  GAMEBENCH_CYBERNETICS_MOCK    default 1 for cybernetic reference verify

Examples:
  ./adapters/harbor/run.sh dev verify sokoban-singleplayer
  ./adapters/harbor/run.sh dev codex crafter-singleplayer
  ./adapters/harbor/run.sh code-policy codex tictactoe-singleplayer
  ./adapters/harbor/run.sh code-policy pi rogue-singleplayer
  ./adapters/harbor/run.sh code-policy cursor craftax-singleplayer
  ./adapters/harbor/run.sh puzzle codex crafter-singleplayer --puzzle-id puzzle_front_only_v1
  ./adapters/harbor/run.sh cybernetic verify craftax-singleplayer
  ./adapters/harbor/run.sh code-policy list
EOF
}

verify_script_for() {
  case "$1" in
    tictactoe-singleplayer) echo run_reference_verify.sh ;;
    sokoban-singleplayer) echo run_sokoban_reference_verify.sh ;;
    crafter-singleplayer) echo run_crafter_reference_verify.sh ;;
    craftax-singleplayer) echo run_craftax_reference_verify.sh ;;
    minihack-singleplayer) echo run_minihack_reference_verify.sh ;;
    frogs-singleplayer) echo run_frogs_reference_verify.sh ;;
    rogue-singleplayer) echo run_rogue_reference_verify.sh ;;
    overcooked-v2-multiplayer) echo run_overcooked_v2_reference_verify.sh ;;
    dungeongrid-multiplayer) echo run_dungeongrid_reference_verify.sh ;;
    *) return 1 ;;
  esac
}

legacy_codex_script_for() {
  case "$1" in
    tictactoe-singleplayer) echo run_local_codex.sh ;;
    crafter-singleplayer) echo run_local_codex_crafter.sh ;;
    *) return 1 ;;
  esac
}

run_family_verify() {
  local family="$1"
  local task_id="$2"
  shift 2
  case "$family" in
    dev)
      local script
      script="$(verify_script_for "$task_id")" || {
        echo "No Harbor dev verify adapter for task_id=$task_id" >&2
        exit 1
      }
      exec bash "$SCRIPTS/$script"
      ;;
    code-policy|code_policy|code_policy_opt)
      exec bash "$SCRIPTS/_run_harbor_reference_verify.sh" code_policy_opt "$task_id" "$@"
      ;;
    puzzle|puzzles|code_policy_puzzles)
      exec bash "$SCRIPTS/_run_harbor_reference_verify.sh" code_policy_puzzles "$task_id" "$@"
      ;;
    cybernetic|cybernetic_opt)
      exec bash "$SCRIPTS/_run_harbor_reference_verify.sh" cybernetic_opt "$task_id" "$@"
      ;;
    *)
      echo "Unknown family: $family" >&2
      usage >&2
      exit 1
      ;;
  esac
}

run_family_agent() {
  local family="$1"
  local agent="$2"
  local task_id="$3"
  shift 3
  export GAMEBENCH_HARBOR_AGENT="$agent"
  case "$family" in
    code-policy|code_policy|code_policy_opt)
      exec bash "$SCRIPTS/_run_harbor_agent.sh" code_policy_opt "$task_id" "$@"
      ;;
    puzzle|puzzles|code_policy_puzzles)
      [[ "$agent" == "codex" ]] || {
        echo "puzzle family only supports codex (got agent=$agent)" >&2
        exit 2
      }
      exec bash "$SCRIPTS/_run_harbor_agent.sh" code_policy_puzzles "$task_id" "$@"
      ;;
    cybernetic|cybernetic_opt)
      [[ "$agent" == "codex" ]] || {
        echo "cybernetic family only supports codex (got agent=$agent)" >&2
        exit 2
      }
      exec bash "$SCRIPTS/_run_harbor_agent.sh" cybernetic_opt "$task_id" "$@"
      ;;
    *)
      echo "Unknown family for agent run: $family" >&2
      usage >&2
      exit 1
      ;;
  esac
}

run_family_codex() {
  local family="$1"
  local task_id="$2"
  shift 2
  case "$family" in
    dev)
      local legacy
      if legacy="$(legacy_codex_script_for "$task_id")"; then
        exec bash "$SCRIPTS/$legacy"
      fi
      exec bash "$SCRIPTS/_run_harbor_dev_codex.sh" "$task_id"
      ;;
    code-policy|code_policy|code_policy_opt|puzzle|puzzles|code_policy_puzzles|cybernetic|cybernetic_opt)
      run_family_agent "$family" "codex" "$task_id" "$@"
      ;;
    *)
      echo "Unknown family: $family" >&2
      usage >&2
      exit 1
      ;;
  esac
}

run_family_list() {
  local family="${1:-all}"
  case "$(normalize_family "$family")" in
    dev) eval_registry list-tasks ;;
    code_policy_opt|code_policy_puzzles|cybernetic_opt) eval_registry list-tasks ;;
    all)
      eval_registry list-tasks
      echo "policy-puzzle-diagnosis"
      ;;
    *)
      echo "Unknown family: $family" >&2
      exit 1
      ;;
  esac
}

cmd="${1:-}"
shift || true

case "$cmd" in
  dev|code-policy|code_policy|code_policy_opt|puzzle|puzzles|code_policy_puzzles|cybernetic|cybernetic_opt)
    family="$cmd"
    sub="${1:-}"
    shift || true
    case "$sub" in
      verify)
        task_id="${1:-}"
        shift || true
        [[ -n "$task_id" ]] || { usage >&2; exit 1; }
        run_family_verify "$family" "$task_id" "$@"
        ;;
      codex)
        task_id="${1:-}"
        shift || true
        [[ -n "$task_id" ]] || { usage >&2; exit 1; }
        run_family_codex "$family" "$task_id" "$@"
        ;;
      pi|cursor)
        task_id="${1:-}"
        shift || true
        [[ -n "$task_id" ]] || { usage >&2; exit 1; }
        case "$family" in
          code-policy|code_policy|code_policy_opt)
            run_family_agent "$family" "$sub" "$task_id" "$@"
            ;;
          *)
            echo "$sub agent is only wired for code-policy (got family=$family)" >&2
            exit 2
            ;;
        esac
        ;;
      list) run_family_list "$family" ;;
      *)
        usage >&2
        exit 1
        ;;
    esac
    ;;
  list) run_family_list "${1:-all}" ;;
  verify)
    task_id="${1:-}"
    [[ -n "$task_id" ]] || { usage >&2; exit 1; }
    run_family_verify dev "$task_id"
    ;;
  codex)
    task_id="${1:-}"
    [[ -n "$task_id" ]] || { usage >&2; exit 1; }
    run_family_codex dev "$task_id"
    ;;
  smoke)
    task_id="${1:-}"
    [[ "$task_id" == crafter-singleplayer ]] || {
      echo "Harbor smoke only wired for crafter-singleplayer" >&2
      exit 1
    }
    exec bash "$SCRIPTS/run_crafter_harbor_smoke.sh"
    ;;
  puzzle)
    sub="${1:-}"
    shift || true
    case "$sub" in
      verify) run_family_verify puzzle "${GAMEBENCH_TASK:-tictactoe-singleplayer}" "$@" ;;
      codex) run_family_codex puzzle "${GAMEBENCH_TASK:-tictactoe-singleplayer}" "$@" ;;
      *) usage >&2; exit 1 ;;
    esac
    ;;
  ""|-h|--help|help) usage ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
