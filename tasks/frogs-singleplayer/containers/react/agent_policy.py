"""OpenAI-compatible ReAct policy with deterministic fallback for FrogsGame."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from gold_python.agent_io import parse_action_text
from policies.registry import choose_action


DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_SYSTEM_PROMPT = (
    "You are playing FrogsGame. Think privately, then reply with exactly one JSON action such as "
    "{\"kind\":\"place_frog\",\"row\":0,\"col\":1} or {\"kind\":\"submit\"}."
)


@dataclass
class AgentPolicyConfig:
    policy_id: str = "solver_v1"
    inference_url: str = DEFAULT_URL
    api_key: str = ""
    model: str = DEFAULT_MODEL
    temperature: float = 0.0
    max_tokens: int = 128
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    use_lm: bool = False

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AgentPolicyConfig":
        api_key = str(raw.get("api_key", "")).strip() or os.environ.get("GROQ_API_KEY", "").strip() or os.environ.get("OPENAI_API_KEY", "").strip()
        use_lm = bool(raw.get("use_lm", False)) or bool(api_key and raw.get("inference_url"))
        return cls(
            policy_id=str(raw.get("policy_id", "solver_v1")),
            inference_url=str(raw.get("inference_url", os.environ.get("GROQ_URL", DEFAULT_URL))),
            api_key=api_key,
            model=str(raw.get("model", os.environ.get("GROQ_MODEL", DEFAULT_MODEL))),
            temperature=float(raw.get("temperature", 0.0)),
            max_tokens=max(int(raw.get("max_tokens", 128)), 16),
            system_prompt=str(raw.get("system_prompt", DEFAULT_SYSTEM_PROMPT)),
            use_lm=use_lm,
        )


@dataclass
class AgentTurnResult:
    raw_action: dict[str, Any]
    assistant_text: str
    invalid_parse: bool
    repaired: bool
    usage: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    error: str | None = None
    model: str | None = None


class AgentPolicy:
    ACTOR = "frogs_agent"

    def __init__(self, config: AgentPolicyConfig) -> None:
        self.config = config

    async def choose(self, observation: dict[str, Any], action_history: list[dict[str, Any]], seed: int, ply: int) -> AgentTurnResult:
        if self.config.use_lm and self.config.api_key:
            try:
                inference = await _chat_completion(self.config, _prompt(observation, action_history))
                parsed = parse_action_text(inference["assistant_text"], observation["valid_actions"])
                return AgentTurnResult(
                    raw_action=parsed.action,
                    assistant_text=inference["assistant_text"],
                    invalid_parse=parsed.invalid_parse,
                    repaired=parsed.repaired,
                    usage=dict(inference.get("usage", {})),
                    request_id=inference.get("request_id"),
                    model=self.config.model,
                )
            except Exception as exc:
                fallback = choose_action(self.config.policy_id, observation, seed=seed, ply=ply)
                parsed = parse_action_text(fallback, observation["valid_actions"])
                return AgentTurnResult(
                    raw_action=parsed.action,
                    assistant_text="",
                    invalid_parse=True,
                    repaired=True,
                    error=str(exc),
                    model=self.config.model,
                )
        fallback = choose_action(self.config.policy_id, observation, seed=seed, ply=ply)
        parsed = parse_action_text(fallback, observation["valid_actions"])
        return AgentTurnResult(
            raw_action=parsed.action,
            assistant_text=json.dumps(parsed.action),
            invalid_parse=parsed.invalid_parse,
            repaired=parsed.repaired,
            model=self.config.policy_id,
        )


def _prompt(observation: dict[str, Any], action_history: list[dict[str, Any]]) -> str:
    return "\n".join([observation["observation_text"], "", f"Prior actions: {json.dumps(action_history)}"])


async def _chat_completion(config: AgentPolicyConfig, prompt: str) -> dict[str, Any]:
    import httpx

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config.api_key}"}
    body = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(config.inference_url, headers=headers, json=body)
        response.raise_for_status()
        payload = response.json()
    content = payload["choices"][0]["message"].get("content", "")
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return {"assistant_text": str(content), "usage": payload.get("usage", {}), "request_id": payload.get("id")}
