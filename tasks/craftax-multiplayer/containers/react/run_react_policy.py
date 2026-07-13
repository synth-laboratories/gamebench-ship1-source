"""Run or replay independent Gemini ReAct policies through Craftax-Coop HTTP."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

TASK_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TASK_ROOT))

from containers.http_rollout import read_action_tape, run_http_rollout, write_action_tape, write_report

SYSTEM = """You control one member of a three-agent Craftax-Coop team. Coordinate through the teammate dashboard and request/give actions. Respect your Warrior, Forager, or Miner specialization. Return JSON only: {\"action\":\"one exact legal action\",\"reason\":\"short reason\"}."""


def _parse_response(text: str) -> tuple[dict[str, Any], bool]:
    candidate = text.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            return {}, False
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return {}, False
    return (value, True) if isinstance(value, dict) else ({}, False)


def _completion(api_key: str, model: str, observation: dict[str, Any]) -> dict[str, Any]:
    prompt = json.dumps(
        {
            "objective": "survive, trade across roles, descend nine levels, and defeat the boss",
            "observation": observation,
        },
        separators=(",", ":"),
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 160,
        }
    ).encode()
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = json.loads(response.read())
    assistant_text = raw["choices"][0]["message"]["content"]
    parsed, parse_ok = _parse_response(assistant_text)
    requested_action = parsed.get("action")
    legal = observation["legal_actions"]
    action_valid = isinstance(requested_action, str) and requested_action in legal
    action = requested_action if action_valid else "noop" if "noop" in legal else legal[0]
    return {
        "action": action,
        "requested_action": requested_action,
        "parse_ok": parse_ok,
        "action_valid": action_valid,
        "reason": parsed.get("reason"),
        "assistant_text": assistant_text,
        "usage": raw.get("usage", {}),
        "request_id": raw.get("id"),
    }


async def _decide_joint(
    api_key: str,
    model: str,
    observations: dict[str, Any],
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    agent_ids = sorted(observations)
    decisions = await asyncio.gather(
        *[
            asyncio.to_thread(_completion, api_key, model, observations[agent])
            for agent in agent_ids
        ]
    )
    joint = {agent: {"kind": decisions[index]["action"]} for index, agent in enumerate(agent_ids)}
    detail = {agent: decisions[index] for index, agent in enumerate(agent_ids)}
    return joint, detail


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Gemini or replay its captured actions through Python or Rust HTTP."
    )
    parser.add_argument("--base-url", required=True, help="Craftax-Coop service URL")
    parser.add_argument("--runtime", choices=("python", "rust"), required=True)
    parser.add_argument("--seed", type=int, help="Defaults to tape seed when replaying, otherwise 101")
    parser.add_argument("--steps", type=int, help="Defaults to tape length when replaying, otherwise 30")
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--capture-actions", type=Path, help="Write the executed joint-action tape")
    parser.add_argument("--replay-actions", type=Path, help="Replay without making model calls")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    tape = read_action_tape(args.replay_actions) if args.replay_actions else None
    seed = args.seed if args.seed is not None else int(tape["seed"]) if tape else 101
    max_steps = args.steps if args.steps is not None else len(tape["actions"]) if tape else 30
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if tape is None and not api_key:
        raise SystemExit("missing GEMINI_API_KEY (not required with --replay-actions)")
    policy_metadata = (
        {"provider": "gemini", "model": args.model}
        if tape is None
        else dict(tape.get("policy_metadata", {}))
    )

    def choose(
        observations: dict[str, Any],
        _: int,
    ) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
        return asyncio.run(_decide_joint(api_key, args.model, observations))

    report, actions = run_http_rollout(
        base_url=args.base_url,
        runtime=args.runtime,
        seed=seed,
        max_steps=max_steps,
        policy_kind="react",
        choose_action=choose if tape is None else None,
        replay_tape=tape,
        policy_metadata=policy_metadata,
    )
    if args.capture_actions:
        write_action_tape(
            args.capture_actions,
            seed=seed,
            agent_ids=report["agent_ids"],
            actions=actions,
            policy_kind="react",
            policy_metadata=policy_metadata,
        )
        report["action_tape"] = str(args.capture_actions)
    print(write_report(args.output, report))


if __name__ == "__main__":
    main()
