"""GameBench Crafter single-player ReAct container (rust gold HTTP)."""

from __future__ import annotations

import base64
import json
import os
import sys
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from containers.react.agent_policy import AgentPolicy, AgentPolicyConfig, repair_action
from containers.react.crafter_rust_client import CrafterGoldRequestError, CrafterRustGoldClient

TASK_DIR = Path(__file__).resolve().parents[2]
TASK_FAMILY = "crafter_singleplayer_agent"
app = FastAPI(title="gamebench-crafter-singleplayer-container", version="0.1.0")
ASYNC_ROLLOUTS: dict[str, dict[str, Any]] = {}
CHECKPOINTS: dict[str, dict[str, Any]] = {}
GOLD = CrafterRustGoldClient()


class RolloutEnvSpec(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None


class RolloutPolicySpec(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class RolloutRequest(BaseModel):
    trace_correlation_id: str
    trial_id: str | None = None
    env: RolloutEnvSpec = Field(default_factory=RolloutEnvSpec)
    policy: RolloutPolicySpec = Field(default_factory=RolloutPolicySpec)


def _load_task(env_config: dict[str, Any]) -> dict[str, Any]:
    if isinstance(env_config.get("task"), dict):
        return dict(env_config["task"])
    task_path = str(env_config.get("task_path", "tasks/gc_collect_sapling.json"))
    path = TASK_DIR / task_path
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"unknown_task_path:{task_path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _achievements_from_state(state: dict[str, Any]) -> set[str]:
    private = state.get("private") if isinstance(state.get("private"), dict) else {}
    raw = private.get("achievements")
    if isinstance(raw, list):
        return {str(item) for item in raw}
    if isinstance(raw, dict):
        return {str(key) for key, value in raw.items() if int(value) > 0}
    return set()


def _objective_labels(state: dict[str, Any], task: dict[str, Any]) -> list[str]:
    labels = sorted(f"achievement:{item}" for item in _achievements_from_state(state))
    objective = str(task.get("objective") or "").strip()
    if objective and objective in _achievements_from_state(state):
        labels.append(objective)
        labels.append(f"objective:{objective}")
    reward = float(state.get("reward") or state.get("total_reward") or 0.0)
    if reward >= 1.0 and objective:
        labels.append("goal_complete")
    return sorted(set(labels))


def _reward_from_state(state: dict[str, Any], task: dict[str, Any]) -> float:
    objective = str(task.get("objective") or "").strip()
    if task.get("reward_mode") == "goal_binary" and objective:
        return 1.0 if objective in _achievements_from_state(state) else 0.0
    return float(state.get("reward") or state.get("total_reward") or 0.0)


def _raise_gold_error(exc: Exception) -> None:
    if isinstance(exc, CrafterGoldRequestError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, httpx.HTTPError):
        raise HTTPException(status_code=502, detail=f"crafter_gold_http_error:{exc}") from exc
    raise exc


@app.get("/health")
async def health() -> dict[str, Any]:
    try:
        gold = await GOLD.health()
    except Exception as exc:
        _raise_gold_error(exc)
    return {
        "status": "ok",
        "service": "gamebench_crafter_singleplayer_container",
        "gold_lane": gold.get("lane", "rust"),
        "supports_many_live_seeds": True,
    }


@app.get("/metadata")
async def metadata() -> dict[str, Any]:
    return {
        "status": "ok",
        "runtime_id": "gamebench.crafter_singleplayer.react",
        "name": "GameBench Crafter single-player ReAct container",
        "task_family": TASK_FAMILY,
        "go_ex": {"async_rollouts": True},
        "capabilities": {
            "go_ex": {"async_rollouts": True},
            "async_rollout": True,
            "checkpoint_resume": True,
            "scheduled_checkpoints": True,
        },
        "features": ["async_rollout", "checkpoint_resume", "scheduled_checkpoints"],
    }


@app.get("/task_info")
async def task_info(
    seed: int = 101,
    seeds: list[int] = Query(default=[]),
    task_path: str = "tasks/gc_collect_sapling.json",
) -> dict[str, Any] | list[dict[str, Any]]:
    task = _load_task({"task_path": task_path})
    seed_list = seeds if seeds else [seed]
    payloads = [
        {
            "seed": item,
            "task_family": TASK_FAMILY,
            "task_id": task.get("task_id"),
            "objective": task.get("objective"),
            "reward_mode": task.get("reward_mode"),
        }
        for item in seed_list
    ]
    return payloads[0] if len(payloads) == 1 else payloads


@app.post("/rollout")
async def rollout(request: Request) -> dict[str, Any]:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="rollout_request_must_be_object")
    if payload.get("submission_mode") == "async" or payload.get("schema_version") == "goex_rollout_request.v1":
        record = await _execute_goex_rollout(payload)
        rollout_id = str(record["rollout_id"])
        ASYNC_ROLLOUTS[rollout_id] = record
        return {"rollout_id": rollout_id, "status": "submitted", "submission_mode": "async"}
    parsed = RolloutRequest.model_validate(payload)
    env_config = dict(parsed.env.config)
    seed = int(parsed.env.seed or env_config.get("seed") or 101)
    env_config["seed"] = seed
    record = await _execute_goex_rollout(
        {
            "env": {"config": env_config, "seed": seed},
            "policy": {"config": dict(parsed.policy.config)},
            "trace_correlation_id": parsed.trace_correlation_id,
            "trial_id": parsed.trial_id,
        }
    )
    ASYNC_ROLLOUTS[str(record["rollout_id"])] = record
    return record


@app.post("/rollouts")
async def rollouts(request: Request) -> dict[str, Any]:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="rollout_request_must_be_object")
    record = await _execute_goex_rollout(payload)
    rollout_id = str(record["rollout_id"])
    ASYNC_ROLLOUTS[rollout_id] = record
    return {"rollout_id": rollout_id, "status": "submitted", "submission_mode": "async"}


@app.post("/rollouts/{parent_rollout_id}/resume_async")
async def resume_async(parent_rollout_id: str, request: Request) -> dict[str, Any]:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="resume_request_must_be_object")
    overrides = payload.get("overrides")
    effective_payload = dict(overrides) if isinstance(overrides, dict) else dict(payload)
    checkpoint_id = str(
        payload.get("checkpoint_id")
        or effective_payload.get("checkpoint_id")
        or effective_payload.get("resume_from_checkpoint_id")
        or ""
    ).strip()
    if not checkpoint_id:
        raise HTTPException(status_code=400, detail="checkpoint_id_required")
    target_rollout_id = str(payload.get("target_rollout_id") or effective_payload.get("target_rollout_id") or "").strip()
    if target_rollout_id:
        effective_payload["rollout_id"] = target_rollout_id
    effective_payload.setdefault("checkpoint_id", checkpoint_id)
    effective_payload.setdefault("resume_from_checkpoint_id", checkpoint_id)
    record = await _execute_goex_rollout(
        effective_payload,
        parent_rollout_id=parent_rollout_id,
        checkpoint_id=checkpoint_id,
    )
    rollout_id = str(record["rollout_id"])
    ASYNC_ROLLOUTS[rollout_id] = record
    return {"rollout_id": rollout_id, "status": "submitted", "submission_mode": "async"}


@app.get("/rollouts/{rollout_id}/state")
async def rollout_state(rollout_id: str) -> dict[str, Any]:
    record = ASYNC_ROLLOUTS.get(rollout_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown_rollout:{rollout_id}")
    reward = float(record.get("reward_info", {}).get("outcome_reward", 0.0))
    return {
        "rollout_id": rollout_id,
        "status": record.get("status", "completed"),
        "reward": reward,
        "objective_labels": record.get("objective_labels", []),
        "scheduled_checkpoints": record.get("scheduled_checkpoints", []),
        "metadata": record.get("metadata", {}),
        "reward_info": record.get("reward_info", {}),
        "summary": record.get("summary", {}),
    }


@app.get("/rollouts/{rollout_id}/record")
async def rollout_record(rollout_id: str) -> dict[str, Any]:
    record = ASYNC_ROLLOUTS.get(rollout_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown_rollout:{rollout_id}")
    return record


@app.get("/rollouts/{rollout_id}")
async def get_rollout(rollout_id: str) -> dict[str, Any]:
    return await rollout_record(rollout_id)


@app.post("/rollouts/{rollout_id}/checkpoints")
async def create_checkpoint(rollout_id: str, request: Request) -> dict[str, Any]:
    record = ASYNC_ROLLOUTS.get(rollout_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown_rollout:{rollout_id}")
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="checkpoint_request_must_be_object")
    checkpoint_id = str(payload.get("checkpoint_id") or record.get("terminal_checkpoint_id") or "").strip()
    if not checkpoint_id:
        raise HTTPException(status_code=400, detail="checkpoint_id_required")
    terminal_id = str(record.get("terminal_checkpoint_id") or "")
    terminal_checkpoint = CHECKPOINTS.get(terminal_id)
    if terminal_checkpoint is None:
        raise HTTPException(status_code=409, detail="rollout_snapshot_unavailable")
    if checkpoint_id != terminal_id:
        checkpoint = {**terminal_checkpoint, "checkpoint_id": checkpoint_id}
        CHECKPOINTS[checkpoint_id] = checkpoint
    else:
        checkpoint = terminal_checkpoint
    return _public_checkpoint(checkpoint)


@app.get("/rollouts/{rollout_id}/checkpoints")
async def list_checkpoints(rollout_id: str) -> dict[str, Any]:
    record = ASYNC_ROLLOUTS.get(rollout_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown_rollout:{rollout_id}")
    checkpoint_ids = [str(item.get("checkpoint_id")) for item in record.get("scheduled_checkpoints", [])]
    terminal_id = record.get("terminal_checkpoint_id")
    if terminal_id:
        checkpoint_ids.append(str(terminal_id))
    checkpoints = [_public_checkpoint(CHECKPOINTS[item]) for item in checkpoint_ids if item in CHECKPOINTS]
    return {"rollout_id": rollout_id, "checkpoints": checkpoints}


@app.get("/rollouts/{rollout_id}/checkpoints/{checkpoint_id}")
async def get_checkpoint(rollout_id: str, checkpoint_id: str) -> dict[str, Any]:
    checkpoint = CHECKPOINTS.get(checkpoint_id)
    if checkpoint is None or checkpoint.get("rollout_id") != rollout_id:
        raise HTTPException(status_code=404, detail=f"unknown_checkpoint:{checkpoint_id}")
    return checkpoint


async def _execute_goex_rollout(
    request: dict[str, Any],
    *,
    parent_rollout_id: str | None = None,
    checkpoint_id: str | None = None,
) -> dict[str, Any]:
    try:
        return await _execute_goex_rollout_inner(
            request,
            parent_rollout_id=parent_rollout_id,
            checkpoint_id=checkpoint_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        _raise_gold_error(exc)
        raise


async def _execute_goex_rollout_inner(
    request: dict[str, Any],
    *,
    parent_rollout_id: str | None = None,
    checkpoint_id: str | None = None,
) -> dict[str, Any]:
    env_spec = request.get("env") if isinstance(request.get("env"), dict) else {}
    policy_spec = request.get("policy") if isinstance(request.get("policy"), dict) else {}
    env_config_raw = env_spec.get("config") if isinstance(env_spec.get("config"), dict) else {}
    policy_config_raw = policy_spec.get("config") if isinstance(policy_spec.get("config"), dict) else {}
    seed = int(env_spec.get("seed") or env_config_raw.get("seed") or request.get("seed") or 101)
    rollout_id = _requested_rollout_id(request) or f"crafter-goex-{uuid.uuid4()}"
    trace_correlation_id = str(request.get("trace_correlation_id") or rollout_id)
    task = _load_task(env_config_raw)
    max_steps = max(int(env_config_raw.get("max_steps", 120)), 1)
    agent = AgentPolicy(AgentPolicyConfig.from_mapping(policy_config_raw))
    checkpoint_schedule = request.get("checkpoint_schedule") if isinstance(request.get("checkpoint_schedule"), dict) else {}
    schedule_per_turn = checkpoint_schedule.get("mode") == "per_llm_call"
    checkpoint_prefix = str(checkpoint_schedule.get("checkpoint_id_prefix") or f"crafter-goex-midcp-{rollout_id}")

    created = await GOLD.create_rollout(task=task, seed=seed)
    gold_rollout_id = str(created.get("rollout_id") or created.get("episode_id") or "")
    if not gold_rollout_id:
        raise RuntimeError("crafter gold create_rollout missing rollout_id")

    if checkpoint_id:
        checkpoint = CHECKPOINTS.get(checkpoint_id)
        if checkpoint is None:
            raise HTTPException(status_code=404, detail=f"unknown_checkpoint:{checkpoint_id}")
        await GOLD.restore(gold_rollout_id, str(checkpoint["blob_b64"]))

    turns: list[dict[str, Any]] = []
    action_history: list[str] = []
    scheduled_checkpoints: list[dict[str, Any]] = []
    inference_errors = 0
    invalid_actions = 0
    step = 0
    llm_calls = 0

    while step < max_steps and llm_calls < agent.config.max_llm_turns:
        state = await GOLD.state(gold_rollout_id)
        if state.get("terminated") or state.get("truncated"):
            break
        readout = await GOLD.readout(gold_rollout_id)
        observation_text = str(readout.get("observation_text", ""))
        valid_actions = list(readout.get("valid_actions") or [])
        turn = await agent.plan_actions(
            observation_text=observation_text,
            valid_actions=valid_actions,
            action_history=action_history,
            steps_remaining=max_steps - step,
            llm_calls_remaining=agent.config.max_llm_turns - llm_calls,
        )
        if turn.error:
            inference_errors += 1
        if turn.invalid_parse:
            invalid_actions += 1
        llm_calls += 1
        executed: list[str] = []
        for planned_action in turn.planned_actions:
            if step >= max_steps:
                break
            readout = await GOLD.readout(gold_rollout_id)
            valid_actions = list(readout.get("valid_actions") or [])
            action, repaired = repair_action(planned_action, valid_actions)
            if repaired:
                invalid_actions += 1
            state = await GOLD.step(gold_rollout_id, action)
            action_history.append(action)
            executed.append(action)
            turns.append(
                {
                    "step": step,
                    "llm_call": llm_calls,
                    "action": action,
                    "planned_batch": turn.planned_actions,
                    "assistant_text": turn.assistant_text if len(executed) == 1 else "",
                    "invalid_parse": turn.invalid_parse,
                    "repaired": repaired,
                    "usage": turn.usage if len(executed) == 1 else {},
                    "request_id": turn.request_id if len(executed) == 1 else None,
                    "error": turn.error if len(executed) == 1 else None,
                    "model": turn.model,
                    "reward_total": _reward_from_state(state, task),
                }
            )
            step += 1
            if state.get("terminated") or state.get("truncated"):
                break
        if schedule_per_turn:
            cp_blob = await GOLD.checkpoint_with_blob(gold_rollout_id)
            cp_id = f"{checkpoint_prefix}_{llm_calls:04d}"
            checkpoint = _checkpoint_from_gold(cp_id, rollout_id, cp_blob, task, llm_calls)
            CHECKPOINTS[cp_id] = checkpoint
            scheduled_checkpoints.append(_public_checkpoint(checkpoint))

    final_state = await GOLD.state(gold_rollout_id)
    labels = _objective_labels(final_state, task)
    reward = _reward_from_state(final_state, task)
    outcome = "success" if final_state.get("terminated") else "truncated" if final_state.get("truncated") else "unfinished"
    terminal_checkpoint_id = f"{rollout_id}_terminal"
    terminal_blob = await GOLD.checkpoint_with_blob(gold_rollout_id)
    terminal_checkpoint = _checkpoint_from_gold(terminal_checkpoint_id, rollout_id, terminal_blob, task, llm_calls)
    CHECKPOINTS[terminal_checkpoint_id] = terminal_checkpoint
    return {
        "schema_version": "goex_rollout_response.v1",
        "rollout_id": rollout_id,
        "trace_correlation_id": trace_correlation_id,
        "trial_id": request.get("trial_id") or f"crafter-goex-{seed}",
        "status": "completed",
        "success_status": "success",
        "status_detail": outcome,
        "parent_rollout_id": parent_rollout_id,
        "parent_checkpoint_id": checkpoint_id,
        "terminal_checkpoint_id": terminal_checkpoint_id,
        "reward_info": {
            "outcome_reward": reward,
            "details": {
                "seed": seed,
                "task_id": task.get("task_id"),
                "objective": task.get("objective"),
                "outcome": outcome,
                "steps": step,
                "invalid_action_count": invalid_actions,
                "inference_error_count": inference_errors,
                "model": agent.config.model,
                "gold_rollout_id": gold_rollout_id,
            },
        },
        "summary": {"outcome": outcome, "reward": reward, "steps": step},
        "metadata": {
            **(request.get("metadata") if isinstance(request.get("metadata"), dict) else {}),
            "objective_labels": labels,
            "final_objective_labels": labels,
            "policy_llm_turns": llm_calls,
        },
        "objective_labels": labels,
        "final_objective_labels": labels,
        "state": final_state,
        "checkpoint": _public_checkpoint(terminal_checkpoint),
        "scheduled_checkpoints": scheduled_checkpoints,
        "artifact": [{"artifact_type": "turns", "turns": turns}],
        "artifacts": [{"artifact_type": "turns", "turns": turns}],
    }


def _checkpoint_from_gold(
    checkpoint_id: str,
    rollout_id: str,
    gold_payload: dict[str, Any],
    task: dict[str, Any],
    policy_index: int,
) -> dict[str, Any]:
    blob = str(gold_payload.get("blob") or gold_payload.get("blob_b64") or "")
    labels = []
    objective = str(task.get("objective") or "").strip()
    if objective:
        labels.append(f"objective:{objective}")
    return {
        "checkpoint_id": checkpoint_id,
        "rollout_id": rollout_id,
        "policy_llm_call_index": policy_index,
        "reward": float(gold_payload.get("reward") or 0.0),
        "objective_labels": labels,
        "metadata": {
            "rollout_id": rollout_id,
            "policy_llm_call_index": policy_index,
            "objective_labels": labels,
        },
        "blob_b64": blob,
    }


def _public_checkpoint(checkpoint: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in checkpoint.items() if key != "blob_b64"}


def _requested_rollout_id(request: Mapping[str, Any]) -> str | None:
    for key in ("rollout_id", "target_rollout_id", "trace_correlation_id"):
        value = str(request.get(key) or "").strip()
        if value and not value.startswith("$"):
            return value
    return None


def main() -> None:
    for path in (TASK_DIR, TASK_DIR / "gold_python", TASK_DIR / "shared"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8096"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
