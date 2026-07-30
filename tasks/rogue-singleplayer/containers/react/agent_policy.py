"""DeepSeek / OpenAI-compatible Rogue ReAct policy."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from gold_python.agent_io import format_agent_observation, parse_action_text

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_SYSTEM_PROMPT = (
    "You are playing Rogue on GameBench rust gold. Explore the dungeon, collect useful items, "
    "reach stairs (%), then descend with >. Reply with JSON only, for example {\"action\":\"l\"}."
)


@dataclass
class AgentPolicyConfig:
    policy_id: str = "react_deepseek_v1"
    inference_url: str = DEFAULT_URL
    api_key: str = ""
    model: str = DEFAULT_MODEL
    temperature: float = 0.0
    max_tokens: int = 512
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    use_lm: bool = True
    provider: str = "deepseek"

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AgentPolicyConfig":
        api_key = (
            str(raw.get("api_key", "")).strip()
            or os.environ.get(str(raw.get("api_key_env", "DEEPSEEK_API_KEY")), "").strip()
            or os.environ.get("DEEPSEEK_API_KEY", "").strip()
            or os.environ.get("OPENAI_API_KEY", "").strip()
        )
        provider = str(raw.get("provider", "deepseek")).strip().lower()
        default_url = DEFAULT_URL
        if provider == "groq":
            default_url = "https://api.groq.com/openai/v1/chat/completions"
        elif provider == "gemini":
            default_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        elif provider == "openai":
            default_url = "https://api.openai.com/v1/chat/completions"
        inference_url = str(raw.get("inference_url", default_url))
        default_model = DEFAULT_MODEL
        if provider == "gemini":
            default_model = "gemini-3.1-flash-lite"
        elif provider != "deepseek":
            default_model = str(raw.get("model", DEFAULT_MODEL))
        return cls(
            policy_id=str(raw.get("policy_id", "react_deepseek_v1")),
            inference_url=inference_url,
            api_key=api_key,
            model=str(raw.get("model", default_model)),
            temperature=float(raw.get("temperature", 0.0)),
            max_tokens=max(int(raw.get("max_tokens", 512)), 32),
            system_prompt=str(raw.get("system_prompt", DEFAULT_SYSTEM_PROMPT)),
            use_lm=bool(raw.get("use_lm", True)),
            provider=provider,
        )


@dataclass
class AgentTurnResult:
    action: str
    assistant_text: str
    invalid_parse: bool
    repaired: bool
    usage: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    model: str | None = None


async def chat_completion(config: AgentPolicyConfig, prompt: str) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config.api_key}"}
    body: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    if config.provider == "deepseek":
        body["thinking"] = {"type": "disabled"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(config.inference_url, headers=headers, json=body)
        response.raise_for_status()
        payload = response.json()
    content = payload["choices"][0]["message"].get("content", "")
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return {"assistant_text": str(content), "usage": payload.get("usage", {}), "request_id": payload.get("id")}


class AgentPolicy:
    ACTOR = "rogue_agent"

    def __init__(self, config: AgentPolicyConfig) -> None:
        self.config = config

    async def choose_action(
        self,
        *,
        readout: dict[str, Any],
        objective: str,
        action_history: list[str],
        steps_remaining: int,
        llm_calls_remaining: int,
    ) -> AgentTurnResult:
        if steps_remaining <= 0 or llm_calls_remaining <= 0:
            raise RuntimeError("rogue policy called with no remaining steps or llm calls")
        observation = format_agent_observation(readout, objective=objective)
        valid_actions = list(observation.get("valid_actions") or readout.get("valid_actions") or [])
        if not valid_actions:
            raise RuntimeError("rogue readout missing valid_actions")
        prompt = "\n".join(
            [
                str(observation.get("observation_text", "")),
                f"last_actions={json.dumps(action_history[-16:])}",
                f"steps_remaining={steps_remaining}",
                f"llm_calls_remaining={llm_calls_remaining}",
                'Reply with JSON only, for example {"action":"l"}.',
            ]
        )
        if not self.config.use_lm:
            raise RuntimeError("rogue react policy requires use_lm=true for GELO validation")
        if not self.config.api_key:
            raise RuntimeError(
                f"missing_api_key provider={self.config.provider} env={self.config.policy_id}"
            )
        inference = await chat_completion(self.config, prompt)
        parsed = parse_action_text(inference["assistant_text"], valid_actions)
        return AgentTurnResult(
            action=parsed.action,
            assistant_text=inference["assistant_text"],
            invalid_parse=parsed.invalid_parse,
            repaired=parsed.repaired,
            usage=dict(inference.get("usage", {})),
            request_id=inference.get("request_id"),
            model=self.config.model,
        )
