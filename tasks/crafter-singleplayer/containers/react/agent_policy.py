"""DeepSeek / OpenAI-compatible Crafter ReAct policy."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_SYSTEM_PROMPT = (
    "You are playing Crafter. Output ONLY one JSON object with an actions array "
    'of 3 to 10 legal moves, for example {"actions":["move_right","do","move_down"]}. '
    "Plan a short action sequence; no explanation."
)

ACTION_WORDS = (
    "noop",
    "move_up",
    "move_down",
    "move_left",
    "move_right",
    "do",
    "sleep",
    "place_stone",
    "place_table",
    "place_furnace",
    "place_plant",
    "make_wood_pickaxe",
    "make_stone_pickaxe",
    "make_iron_pickaxe",
    "make_wood_sword",
    "make_stone_sword",
    "make_iron_sword",
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
    min_actions: int = 3
    max_actions: int = 10
    max_llm_turns: int = 6
    provider: str = "deepseek"

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AgentPolicyConfig":
        api_key = (
            str(raw.get("api_key", "")).strip()
            or os.environ.get(str(raw.get("api_key_env", "DEEPSEEK_API_KEY")), "").strip()
            or os.environ.get("DEEPSEEK_API_KEY", "").strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
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
            min_actions=max(int(raw.get("min_actions", 3)), 1),
            max_actions=max(int(raw.get("max_actions", 10)), 1),
            max_llm_turns=max(int(raw.get("max_llm_turns", 6)), 1),
            provider=provider,
        )


@dataclass
class AgentTurnResult:
    planned_actions: list[str]
    assistant_text: str
    invalid_parse: bool
    repaired: bool
    usage: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    error: str | None = None
    model: str | None = None


def repair_action(action: str, valid_actions: list[str]) -> tuple[str, bool]:
    valid = set(valid_actions)
    if action in valid:
        return action, False
    fallback = "noop" if "noop" in valid else next(iter(valid), "noop")
    return fallback, True


def parse_action_list(
    raw_text: str,
    valid_actions: list[str],
    *,
    min_actions: int,
    max_actions: int,
) -> tuple[list[str], int]:
    text = str(raw_text or "").strip()
    valid = set(valid_actions)
    ordered: list[str] = []

    def append_candidate(candidate: str) -> None:
        if candidate not in valid or len(ordered) >= max_actions:
            return
        ordered.append(candidate)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            value = parsed.get("actions")
            if value is None:
                value = parsed.get("action")
            if isinstance(value, list):
                for item in value:
                    append_candidate(str(item))
            elif value is not None:
                append_candidate(str(value))
        elif isinstance(parsed, list):
            for item in parsed:
                append_candidate(str(item))
    except json.JSONDecodeError:
        pass

    if not ordered:
        hits: list[tuple[int, str]] = []
        for word in ACTION_WORDS:
            for match in re.finditer(rf"\b{re.escape(word)}\b", text.lower()):
                if word in valid:
                    hits.append((match.start(), word))
        for _, word in sorted(hits, key=lambda item: item[0]):
            append_candidate(word)
            if len(ordered) >= max_actions:
                break

    repairs = 0
    repaired_actions: list[str] = []
    for action in ordered[:max_actions]:
        repaired_action, repaired = repair_action(action, valid_actions)
        if repaired:
            repairs += 1
        repaired_actions.append(repaired_action)

    if not repaired_actions:
        fallback, repaired = repair_action("noop", valid_actions)
        repaired_actions = [fallback]
        if repaired:
            repairs += 1

    while len(repaired_actions) < min_actions and len(repaired_actions) < max_actions:
        fallback, repaired = repair_action("noop", valid_actions)
        repaired_actions.append(fallback)
        if repaired:
            repairs += 1

    return repaired_actions[:max_actions], repairs


def batch_size_prompt(*, min_actions: int, max_actions: int, steps_remaining: int, llm_calls_remaining: int) -> str:
    upper = min(max_actions, steps_remaining)
    lower = min(min_actions, upper)
    if upper <= 0:
        return "Episode complete."
    target = upper if lower == upper else f"{lower}-{upper}"
    return (
        f"Return a JSON object with an actions array of {target} legal moves "
        f"({llm_calls_remaining} planner calls left, {steps_remaining} steps left). "
        'Example: {"actions":["move_right","do","move_down"]}.'
    )


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
    ACTOR = "crafter_agent"

    def __init__(self, config: AgentPolicyConfig) -> None:
        self.config = config

    async def plan_actions(
        self,
        *,
        observation_text: str,
        valid_actions: list[str],
        action_history: list[str],
        steps_remaining: int,
        llm_calls_remaining: int,
    ) -> AgentTurnResult:
        prompt = "\n".join(
            [
                observation_text,
                f"last_actions={json.dumps(action_history[-16:])}",
                batch_size_prompt(
                    min_actions=self.config.min_actions,
                    max_actions=min(self.config.max_actions, steps_remaining),
                    steps_remaining=steps_remaining,
                    llm_calls_remaining=llm_calls_remaining,
                ),
            ]
        )
        if not self.config.use_lm:
            raise RuntimeError("crafter react policy requires use_lm=true for GELO validation")
        if not self.config.api_key:
            raise RuntimeError(
                f"missing_api_key provider={self.config.provider} policy_id={self.config.policy_id}"
            )
        inference = await chat_completion(self.config, prompt)
        planned, repairs = parse_action_list(
            inference["assistant_text"],
            valid_actions,
            min_actions=self.config.min_actions,
            max_actions=min(self.config.max_actions, steps_remaining),
        )
        return AgentTurnResult(
            planned_actions=planned,
            assistant_text=inference["assistant_text"],
            invalid_parse=not inference["assistant_text"].strip(),
            repaired=repairs > 0,
            usage=dict(inference.get("usage", {})),
            request_id=inference.get("request_id"),
            model=self.config.model,
        )
