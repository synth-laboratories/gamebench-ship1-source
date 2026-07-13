"""Shared HTTP rollout, action-tape, and reporting support for Craftax-Coop."""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

ACTION_TAPE_SCHEMA = "gamebench.craftax_coop.action_tape.v1"
ROLLOUT_SCHEMA = "gamebench.craftax_coop.http_rollout.v1"


def http_json(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} returned HTTP {error.code}: {detail}") from error


def normalize_joint_action(value: dict[str, Any], agent_ids: list[str]) -> dict[str, dict[str, str]]:
    missing = sorted(set(agent_ids) - set(value))
    extra = sorted(set(value) - set(agent_ids))
    if missing or extra:
        raise ValueError(f"joint action agents differ: missing={missing}, extra={extra}")
    normalized: dict[str, dict[str, str]] = {}
    for agent in agent_ids:
        raw = value[agent]
        action = raw if isinstance(raw, str) else raw.get("kind") if isinstance(raw, dict) else None
        if not isinstance(action, str) or not action:
            raise ValueError(f"invalid action for {agent}: {raw!r}")
        normalized[agent] = {"kind": action}
    return normalized


def read_action_tape(path: Path) -> dict[str, Any]:
    tape = json.loads(path.read_text())
    if tape.get("schema_version") != ACTION_TAPE_SCHEMA:
        raise ValueError(f"unsupported action tape schema: {tape.get('schema_version')!r}")
    if not isinstance(tape.get("actions"), list):
        raise ValueError("action tape must contain an actions list")
    return tape


def write_action_tape(
    path: Path,
    *,
    seed: int,
    agent_ids: list[str],
    actions: list[dict[str, dict[str, str]]],
    policy_kind: str,
    policy_metadata: dict[str, Any],
) -> None:
    payload = {
        "schema_version": ACTION_TAPE_SCHEMA,
        "env_family": "craftax-multiplayer",
        "seed": seed,
        "agent_ids": agent_ids,
        "policy_kind": policy_kind,
        "policy_metadata": policy_metadata,
        "actions": actions,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _observation_snapshot(observations: dict[str, Any]) -> dict[str, Any]:
    return {
        agent: {
            "role": observation.get("role"),
            "level": observation.get("level"),
            "self": observation.get("self"),
            "teammate_dashboard": observation.get("teammate_dashboard"),
            "last_joint_event": observation.get("last_joint_event"),
        }
        for agent, observation in sorted(observations.items())
    }


def run_http_rollout(
    *,
    base_url: str,
    runtime: str,
    seed: int,
    max_steps: int,
    policy_kind: str,
    choose_action: Callable[[dict[str, Any], int], tuple[dict[str, Any], dict[str, Any]]] | None,
    replay_tape: dict[str, Any] | None = None,
    policy_metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, dict[str, str]]]]:
    health = http_json(base_url, "GET", "/health")
    actual_runtime = health.get("runtime")
    if actual_runtime != runtime:
        raise ValueError(f"runtime mismatch: requested {runtime!r}, service reports {actual_runtime!r}")
    reset = http_json(base_url, "POST", "/reset", {"seed": seed})
    observations = reset["observations"]
    agent_ids = sorted(observations)

    replay_actions: list[dict[str, Any]] | None = None
    if replay_tape is not None:
        tape_seed = int(replay_tape["seed"])
        if tape_seed != seed:
            raise ValueError(f"replay seed mismatch: tape={tape_seed}, requested={seed}")
        if list(replay_tape.get("agent_ids", [])) != agent_ids:
            raise ValueError("replay action tape agent_ids do not match the service")
        replay_actions = replay_tape["actions"]

    captured_actions: list[dict[str, dict[str, str]]] = []
    steps: list[dict[str, Any]] = []
    total_reward = 0.0
    terminal_reason = None
    for step_index in range(max_steps):
        decision: dict[str, Any] = {}
        if replay_actions is not None:
            if step_index >= len(replay_actions):
                break
            raw_joint = replay_actions[step_index]
            action_source = "replay"
        else:
            if choose_action is None:
                raise ValueError("choose_action is required when no replay tape is supplied")
            raw_joint, decision = choose_action(observations, step_index)
            action_source = "policy"
        joint_action = normalize_joint_action(raw_joint, agent_ids)
        captured_actions.append(joint_action)
        result = http_json(base_url, "POST", "/step", {"joint_action": joint_action})
        observations = result["observations"]
        reward = float(result["rewards"][agent_ids[0]])
        total_reward += reward
        info = result.get("info", {})
        terminal_reason = info.get("termination_reason")
        steps.append(
            {
                "step": step_index + 1,
                "action_source": action_source,
                "joint_action": joint_action,
                "decision": decision,
                "shared_reward": reward,
                "cumulative_shared_reward": total_reward,
                "dones": result["dones"],
                "termination_reason": terminal_reason,
                "events": info.get("events", []),
                "observations": _observation_snapshot(observations),
            }
        )
        if result["dones"].get("__all__"):
            break

    nev = http_json(base_url, "GET", "/nev")
    checkpoint = http_json(base_url, "GET", "/checkpoint")
    checkpoint_hash = hashlib.sha256(
        json.dumps(checkpoint, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    action_hash = hashlib.sha256(
        json.dumps(captured_actions, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    first = observations[agent_ids[0]]
    shared = first.get("shared", {})
    achievements = sorted(name for name, earned in shared.get("achievements", {}).items() if earned)
    report = {
        "schema_version": ROLLOUT_SCHEMA,
        "env_family": health.get("env_family"),
        "lane": f"{runtime}_http",
        "runtime": runtime,
        "policy_kind": policy_kind,
        "policy_metadata": policy_metadata or {},
        "action_source": "replay" if replay_actions is not None else "policy",
        "seed": seed,
        "step_limit": max_steps,
        "steps": len(steps),
        "shared_reward": total_reward,
        "achievements": achievements,
        "trades": shared.get("trade_count", 0),
        "terminated": bool(steps and steps[-1]["dones"].get("__all__")),
        "termination_reason": terminal_reason,
        "checkpoint_sha256": checkpoint_hash,
        "structured_event_count": len(nev.get("structured", [])),
        "legacy_event_count": len(nev.get("legacy", [])),
        "agent_ids": agent_ids,
        "action_count": len(captured_actions),
        "action_sha256": action_hash,
        "trace": steps,
    }
    return report, captured_actions


def write_report(path: Path | None, report: dict[str, Any]) -> str:
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded + "\n")
    return encoded
