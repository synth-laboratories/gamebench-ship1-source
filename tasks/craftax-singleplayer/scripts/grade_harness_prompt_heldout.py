"""Paired gold_python heldout grading for Craftax harness+prompt candidates.

Schema family: ``factorybench.craftax_harness_prompt.v1`` (candidate inputs),
``gamebench.craftax.gold_python_harness_prompt_paired_grade.v1`` (scorecard).

The benchmark fixes the environment (pure-Python ``gold_python`` engine, no
JAX, no Rust) and the heldout seeds. A candidate may change only the system
prompt and the bounded harness knobs; it cannot improve its score by switching
the provider/model route, credentials, environment, or scorer.

Invocation contract
-------------------
The evals FactoryBench lane loads this file via ``importlib`` from
``$GAMEBENCH_CRAFTAX_ROOT/scripts/grade_harness_prompt_heldout.py`` and calls::

    await grade_pair(
        baseline=<baseline candidate mapping>,
        candidate=<champion candidate mapping>,
        seeds=[11, 17, 23, 29],          # cost_bounds.heldout_seeds
        max_steps=24,                     # cost_bounds.max_steps
        max_llm_turns=6,                  # cost_bounds.max_llm_turns
        task_path="tasks/policy_dev_template.json",
        provider_defaults={...},          # optional fallback provider/model/system_prompt
    )

A CLI wrapper is also provided::

    python scripts/grade_harness_prompt_heldout.py \
        --baseline baseline.json --candidate candidate.json [--out scorecard.json]

Seeds / max_steps / max_llm_turns default to the candidate's ``cost_bounds``.

Environment: ``GROQ_API_KEY`` is required for live grading (the only network
egress is the LLM provider); ``GAMEBENCH_SOURCE_SHA`` optionally overrides the
``gamebench_source_sha`` recorded in the scorecard (otherwise it is read from
the local git checkout, with no network access).

Offline testability: ``grade_pair`` and ``AgentPolicy`` accept an injectable
async ``completer`` with the ``chat_completion`` signature, so grading logic is
testable without any live LLM call (see
``scripts/test_grade_harness_prompt_heldout.py``).

Harness knob reconciliation (ALLOWED_HARNESS_FIELDS)
----------------------------------------------------
Every advertised knob below is honored by ``containers/react/agent_policy.py``:

- ``max_actions_per_call`` / ``min_actions_per_call``: action batch bounds.
- ``context_window``: number of trailing actions shown verbatim in the prompt.
- ``enable_compact_history`` + ``compact_after_turns``: older actions beyond
  the context window are folded into an ``earlier_action_counts`` summary once
  the history exceeds ``compact_after_turns``; disabled means they are dropped.
- ``enable_todo`` / ``enable_scratch`` / ``enable_rules_search``: local
  ``todo_list`` / ``scratch`` / ``search_game_rules`` tools (deterministic, no
  environment access; state persists across decisions within an episode).
- ``max_tool_turns_per_decision``: how many ``{"tool": ...}`` replies are
  honored per decision before an actions reply is required. Tool sub-calls do
  not consume extra entries of the ``max_llm_turns`` decision budget, but their
  token usage is fully accounted.

Excluded knobs: none. ``reasoning_effort`` (a rust-lane candidate field) is
deliberately NOT accepted here — the python contract does not include it and
the gold_python ReAct policy does not honor it, so it is refused as an unknown
candidate field.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

TASK_ROOT = Path(__file__).resolve().parents[1]
for _extra in (TASK_ROOT, TASK_ROOT / "gold_python", TASK_ROOT / "shared"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from engine import CraftaxEngine

from containers.react.agent_policy import (
    AgentPolicy,
    AgentPolicyConfig,
)

SCHEMA_VERSION = "gamebench.craftax.gold_python_harness_prompt_paired_grade.v1"
CANDIDATE_SCHEMA_VERSION = "factorybench.craftax_harness_prompt.v1"
EXECUTION_CONTRACT_VERSION = "factorybench.craftax_harness_prompt.v1"
ENTRYPOINT = "containers/react/agent_policy.py"
ENVIRONMENT = "gamebench/craftax-singleplayer/gold_python"
DEFAULT_TASK_PATH = "tasks/policy_dev_template.json"
DEFAULT_OBJECTIVE = "collect resources, craft tools, and unlock Craftax achievements"
MINIMUM_ACCEPTED_LIFT = 0.05
# Conservative allow-list of (provider, model) routes. The lane's seeded
# baseline and candidate both declare groq + openai/gpt-oss-120b; anything
# else is refused with a typed candidate_provider_drift/candidate_model_drift
# error so a candidate cannot buy lift by switching routes.
ALLOWED_PROVIDER_MODELS = frozenset(
    {
        ("groq", "openai/gpt-oss-120b"),
    }
)
ALLOWED_CANDIDATE_FIELDS = frozenset(
    {
        "schema_version",
        "candidate_id",
        "entrypoint",
        "execution_contract_version",
        "git_remote",
        "system_prompt",
        "provider",
        "model",
        "temperature",
        "max_tokens",
        "harness",
        "cost_bounds",
        "notes",
    }
)
ALLOWED_HARNESS_FIELDS = frozenset(
    {
        "context_window",
        "compact_after_turns",
        "enable_todo",
        "enable_scratch",
        "enable_rules_search",
        "enable_compact_history",
        "max_actions_per_call",
        "min_actions_per_call",
        "max_tool_turns_per_decision",
    }
)
_HARNESS_BOOL_FIELDS = (
    "enable_todo",
    "enable_scratch",
    "enable_rules_search",
    "enable_compact_history",
)


def _sha256_of_mapping(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _source_sha() -> str:
    override = os.environ.get("GAMEBENCH_SOURCE_SHA", "").strip()
    if override:
        return override
    try:
        result = subprocess.run(
            ["git", "-C", str(TASK_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return "unknown"
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else "unknown"


def _validated_candidate(
    raw: Mapping[str, Any], *, baseline: Mapping[str, Any]
) -> dict[str, Any]:
    candidate = {str(key): value for key, value in raw.items()}
    unknown = sorted(set(candidate) - ALLOWED_CANDIDATE_FIELDS)
    if unknown:
        raise ValueError(f"candidate_unknown_fields:{','.join(unknown)}")
    if candidate.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        raise ValueError("candidate_schema_version_invalid")
    if not str(candidate.get("candidate_id") or "").strip():
        raise ValueError("candidate_id_missing")
    if not str(candidate.get("system_prompt") or "").strip():
        raise ValueError("candidate_system_prompt_missing")
    if "entrypoint" in candidate and candidate["entrypoint"] != ENTRYPOINT:
        raise ValueError(f"candidate_entrypoint_invalid:{candidate['entrypoint']}")
    if (
        "execution_contract_version" in candidate
        and candidate["execution_contract_version"] != EXECUTION_CONTRACT_VERSION
    ):
        raise ValueError("candidate_execution_contract_invalid")
    provider = str(candidate.get("provider", baseline.get("provider")) or "").strip()
    model = str(candidate.get("model", baseline.get("model")) or "").strip()
    baseline_provider = str(baseline.get("provider") or provider).strip()
    baseline_model = str(baseline.get("model") or model).strip()
    if (provider, model) not in ALLOWED_PROVIDER_MODELS or provider != baseline_provider:
        raise ValueError(f"candidate_provider_drift:{provider}/{model}")
    if model != baseline_model:
        raise ValueError(f"candidate_model_drift:{model}")
    candidate["provider"] = provider
    candidate["model"] = model
    temperature = float(candidate.get("temperature", 0.0))
    if not 0.0 <= temperature <= 1.0:
        raise ValueError("candidate_temperature_bounds_invalid")
    candidate["temperature"] = temperature
    max_tokens = int(candidate.get("max_tokens", 384))
    if not 64 <= max_tokens <= 2048:
        raise ValueError("candidate_max_tokens_bounds_invalid")
    candidate["max_tokens"] = max_tokens
    harness = candidate.get("harness") or {}
    if not isinstance(harness, Mapping):
        raise TypeError("candidate_harness_invalid")
    unknown_harness = sorted(set(harness) - ALLOWED_HARNESS_FIELDS)
    if unknown_harness:
        raise ValueError(
            f"candidate_harness_unknown_fields:{','.join(unknown_harness)}"
        )
    for flag in _HARNESS_BOOL_FIELDS:
        value = harness.get(flag, False)
        if not isinstance(value, bool):
            raise ValueError(f"candidate_harness_flag_invalid:{flag}")
        candidate[flag] = value
    context_window = int(harness.get("context_window", 16))
    if not 1 <= context_window <= 64:
        raise ValueError("candidate_context_window_bounds_invalid")
    candidate["context_window"] = context_window
    compact_after_turns = int(harness.get("compact_after_turns", 8))
    if not 1 <= compact_after_turns <= 999:
        raise ValueError("candidate_compact_after_turns_bounds_invalid")
    candidate["compact_after_turns"] = compact_after_turns
    max_actions = int(harness.get("max_actions_per_call", 8))
    min_actions = int(harness.get("min_actions_per_call", 1))
    if not 1 <= min_actions <= max_actions <= 16:
        raise ValueError("candidate_action_batch_bounds_invalid")
    candidate["max_actions_per_call"] = max_actions
    candidate["min_actions_per_call"] = min_actions
    max_tool_turns = int(harness.get("max_tool_turns_per_decision", 0))
    if not 0 <= max_tool_turns <= 4:
        raise ValueError("candidate_tool_turns_bounds_invalid")
    candidate["max_tool_turns_per_decision"] = max_tool_turns
    return candidate


def _policy_config(validated: Mapping[str, Any]) -> AgentPolicyConfig:
    return AgentPolicyConfig.from_mapping(
        {
            "policy_id": str(validated["candidate_id"]),
            "provider": validated["provider"],
            "model": validated["model"],
            "temperature": validated["temperature"],
            "max_tokens": validated["max_tokens"],
            "system_prompt": validated["system_prompt"],
            "context_window": validated["context_window"],
            "compact_after_turns": validated["compact_after_turns"],
            "enable_todo": validated["enable_todo"],
            "enable_scratch": validated["enable_scratch"],
            "enable_rules_search": validated["enable_rules_search"],
            "enable_compact_history": validated["enable_compact_history"],
            "max_actions_per_call": validated["max_actions_per_call"],
            "min_actions_per_call": validated["min_actions_per_call"],
            "max_tool_turns_per_decision": validated["max_tool_turns_per_decision"],
        }
    )


def _load_task(task_path: str, *, max_steps: int) -> tuple[dict[str, Any], str]:
    path = (TASK_ROOT / task_path).resolve()
    if not path.is_file():
        raise ValueError(f"unknown_task_path:{task_path}")
    raw_bytes = path.read_bytes()
    task = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(task, dict):
        raise ValueError(f"task_fixture_invalid:{task_path}")
    task["max_steps"] = max_steps
    world = task.get("world")
    if isinstance(world, dict):
        world["max_steps"] = max_steps
    return task, hashlib.sha256(raw_bytes).hexdigest()


def _private(readout: Mapping[str, Any]) -> dict[str, Any]:
    private = readout.get("private")
    if not isinstance(private, Mapping):
        raise RuntimeError("craftax_readout_private_missing")
    return dict(private)


async def _run_episode(
    *,
    validated: Mapping[str, Any],
    seed: int,
    max_steps: int,
    max_llm_turns: int,
    task: Mapping[str, Any],
    completer: Any | None,
) -> dict[str, Any]:
    engine = CraftaxEngine()
    engine.reset_from_task(json.loads(json.dumps(dict(task))), seed_override=seed)
    policy = AgentPolicy(_policy_config(validated), completer=completer)
    readout = engine.symbolic_readout()
    action_history: list[str] = []
    step = 0
    llm_calls = 0
    tool_sub_calls = 0
    invalid_parse_count = 0
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    while step < max_steps and llm_calls < max_llm_turns:
        private = _private(readout)
        if private["terminated"] or private["truncated"]:
            break
        turn = await policy.choose_action(
            readout=dict(readout),
            objective=DEFAULT_OBJECTIVE,
            action_history=action_history,
            steps_remaining=max_steps - step,
            llm_calls_remaining=max_llm_turns - llm_calls,
            llm_call=llm_calls + 1,
        )
        llm_calls += 1
        tool_sub_calls += int(turn.tool_turns)
        if turn.invalid_parse or turn.repaired:
            invalid_parse_count += 1
        usage["prompt_tokens"] += int(turn.usage.get("prompt_tokens") or 0)
        usage["completion_tokens"] += int(turn.usage.get("completion_tokens") or 0)
        planned = [str(action) for action in turn.actions if str(action)] or ["noop"]
        for action in planned[: max_steps - step]:
            readout = engine.step(action)
            action_history.append(action)
            step += 1
            private = _private(readout)
            if private["terminated"] or private["truncated"]:
                break
        if private["terminated"] or private["truncated"]:
            break
    private = _private(readout)
    return {
        "seed": int(seed),
        "reward": float(private.get("total_reward") or 0.0),
        "achievements": sorted(str(item) for item in private.get("achievements") or []),
        "steps": step,
        "llm_calls": llm_calls,
        "tool_sub_calls": tool_sub_calls,
        "invalid_parse_count": invalid_parse_count,
        "input_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
    }


async def grade_pair(
    *,
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    seeds: Sequence[int],
    max_steps: int,
    max_llm_turns: int,
    task_path: str = DEFAULT_TASK_PATH,
    provider_defaults: Mapping[str, Any] | None = None,
    completer: Any | None = None,
) -> dict[str, Any]:
    """Grade candidate vs baseline on the heldout seeds; returns the scorecard.

    ``completer`` (optional) replaces the live LLM call for offline testing;
    it must match the ``containers.react.agent_policy.chat_completion``
    signature.
    """
    if not seeds or len({int(seed) for seed in seeds}) != len(seeds):
        raise ValueError("heldout_seeds_invalid")
    if int(max_steps) < 1 or int(max_llm_turns) < 1:
        raise ValueError("cost_bounds_invalid")
    baseline_raw = dict(baseline)
    candidate_raw = dict(candidate)
    if provider_defaults:
        for key in ("provider", "model", "system_prompt"):
            if key in provider_defaults:
                baseline_raw.setdefault(key, provider_defaults[key])
                candidate_raw.setdefault(key, provider_defaults[key])
    baseline_config = _validated_candidate(baseline_raw, baseline=baseline_raw)
    candidate_config = _validated_candidate(candidate_raw, baseline=baseline_config)
    task, task_fixture_sha256 = _load_task(task_path, max_steps=int(max_steps))

    baseline_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    # Interleave the paired arms by seed. The model route and scorer are
    # fixed, so temporal provider drift cannot systematically favor one arm.
    for seed_value in (int(seed) for seed in seeds):
        for validated, rows in (
            (baseline_config, baseline_rows),
            (candidate_config, candidate_rows),
        ):
            rows.append(
                await _run_episode(
                    validated=validated,
                    seed=seed_value,
                    max_steps=int(max_steps),
                    max_llm_turns=int(max_llm_turns),
                    task=task,
                    completer=completer,
                )
            )

    baseline_scores = [float(row["reward"]) for row in baseline_rows]
    candidate_scores = [float(row["reward"]) for row in candidate_rows]
    paired_lifts = [
        candidate_score - baseline_score
        for baseline_score, candidate_score in zip(
            baseline_scores, candidate_scores, strict=True
        )
    ]
    baseline_mean = statistics.mean(baseline_scores)
    champion_mean = statistics.mean(candidate_scores)
    lift = statistics.mean(paired_lifts)
    standard_error = (
        statistics.stdev(paired_lifts) / math.sqrt(len(paired_lifts))
        if len(paired_lifts) > 1
        else 0.0
    )
    confidence_low = lift - 1.96 * standard_error
    accepted = lift >= MINIMUM_ACCEPTED_LIFT and confidence_low > 0.0
    all_rows = (*baseline_rows, *candidate_rows)
    llm_calls = sum(int(row["llm_calls"]) for row in all_rows)
    total_tokens = sum(
        int(row["input_tokens"]) + int(row["completion_tokens"]) for row in all_rows
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "environment": ENVIRONMENT,
        "provider": candidate_config["provider"],
        "model": candidate_config["model"],
        "auth_mode": "api_key",
        "candidate_id": candidate_config["candidate_id"],
        "baseline_id": baseline_config["candidate_id"],
        "accepted": accepted,
        "baseline_mean": baseline_mean,
        "champion_mean": champion_mean,
        "baseline_score": baseline_mean,
        "held_out_score": champion_mean,
        "paired_mean_lift": lift,
        "paired_standard_error": standard_error,
        "paired_confidence_95_low": confidence_low,
        "minimum_accepted_lift": MINIMUM_ACCEPTED_LIFT,
        "lift_verdict": "accepted" if accepted else "rejected",
        "rollout_count": len(all_rows),
        "llm_calls": llm_calls,
        "total_tokens": total_tokens,
        "max_steps": int(max_steps),
        "max_llm_turns": int(max_llm_turns),
        "heldout_seed_count": len(seeds),
        # The heldout seeds ship inside the candidate's own cost_bounds, so
        # unlike the rust nano lane they are disclosed by construction and the
        # per-seed records may be published with the scorecard.
        "heldout_values_disclosed": True,
        "task_path": task_path,
        "task_fixture_sha256": task_fixture_sha256,
        "baseline_sha256": _sha256_of_mapping(baseline),
        "candidate_sha256": _sha256_of_mapping(candidate),
        "gamebench_source_sha": _source_sha(),
        "records": {"baseline": baseline_rows, "candidate": candidate_rows},
    }


def _load_json_file(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"candidate_file_not_object:{path}")
    return data


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", required=True, help="baseline candidate JSON")
    parser.add_argument("--candidate", required=True, help="champion candidate JSON")
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--max-llm-turns", type=int, default=None)
    parser.add_argument("--task-path", default=DEFAULT_TASK_PATH)
    parser.add_argument("--out", default=None, help="write scorecard JSON here")
    args = parser.parse_args(argv)
    baseline = _load_json_file(args.baseline)
    candidate = _load_json_file(args.candidate)
    cost_bounds = candidate.get("cost_bounds")
    cost_bounds = dict(cost_bounds) if isinstance(cost_bounds, Mapping) else {}
    seeds = args.seeds or [int(seed) for seed in cost_bounds.get("heldout_seeds") or []]
    max_steps = args.max_steps or int(cost_bounds.get("max_steps") or 24)
    max_llm_turns = args.max_llm_turns or int(cost_bounds.get("max_llm_turns") or 6)
    scorecard = asyncio.run(
        grade_pair(
            baseline=baseline,
            candidate=candidate,
            seeds=seeds,
            max_steps=max_steps,
            max_llm_turns=max_llm_turns,
            task_path=args.task_path,
        )
    )
    rendered = json.dumps(scorecard, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


__all__ = [
    "ALLOWED_CANDIDATE_FIELDS",
    "ALLOWED_HARNESS_FIELDS",
    "ALLOWED_PROVIDER_MODELS",
    "CANDIDATE_SCHEMA_VERSION",
    "MINIMUM_ACCEPTED_LIFT",
    "SCHEMA_VERSION",
    "grade_pair",
]


if __name__ == "__main__":
    raise SystemExit(main())
