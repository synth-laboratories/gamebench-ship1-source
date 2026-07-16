"""OpenAI-compatible Craftax ReAct policy."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

try:
    from parity import CRAFTAX_ACTIONS
except ImportError:
    CRAFTAX_ACTIONS = [
        "noop",
        "left",
        "right",
        "up",
        "down",
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
        "rest",
        "descend",
        "ascend",
    ]


ACTION_WORDS = tuple(str(action) for action in CRAFTAX_ACTIONS)
ACTION_RE = re.compile(
    r"\b(?:action|move|command)\s*[:=]\s*([A-Za-z0-9_\\-]+)", re.IGNORECASE
)
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_SYSTEM_PROMPT = (
    "You are playing GameBench Craftax rust gold. Each response must plan a short sequence of "
    "valid actions to execute in order before the next observation. Prioritize survival, collect "
    "wood and stone, craft basic tools, recover coal and iron, and make durable achievement progress. "
    'Reply with JSON only, for example {"actions":["do","right","do","left","do"]}.'
)
DEFAULT_MIN_ACTIONS_PER_CALL = 5
DEFAULT_MAX_ACTIONS_PER_CALL = 15


@dataclass
class AgentPolicyConfig:
    policy_id: str = "craftax_react_groq_v1"
    inference_url: str = DEFAULT_URL
    api_key: str = ""
    model: str = DEFAULT_MODEL
    temperature: float = 0.0
    max_tokens: int = 512
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    use_lm: bool = True
    provider: str = "groq"
    min_actions_per_call: int = DEFAULT_MIN_ACTIONS_PER_CALL
    max_actions_per_call: int = DEFAULT_MAX_ACTIONS_PER_CALL

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AgentPolicyConfig":
        provider = str(raw.get("provider", "groq")).strip().lower()
        default_url = DEFAULT_URL
        if provider == "deepseek":
            default_url = "https://api.deepseek.com/chat/completions"
        elif provider == "gemini":
            default_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        elif provider == "openai":
            default_url = "https://api.openai.com/v1/chat/completions"
        default_api_key_env = (
            "GROQ_API_KEY" if provider == "groq" else "DEEPSEEK_API_KEY"
        )
        if provider == "gemini":
            default_api_key_env = "GEMINI_API_KEY"
        elif provider == "openai":
            default_api_key_env = "OPENAI_API_KEY"
        api_key_env = str(raw.get("api_key_env", default_api_key_env))
        if provider == "gemini":
            api_key = (
                str(raw.get("api_key", "")).strip()
                or os.environ.get(api_key_env, "").strip()
                or os.environ.get("GEMINI_API_KEY", "").strip()
                or os.environ.get("GOOGLE_API_KEY", "").strip()
            )
        else:
            api_key = (
                str(raw.get("api_key", "")).strip()
                or os.environ.get(api_key_env, "").strip()
                or os.environ.get("GROQ_API_KEY", "").strip()
                or os.environ.get("DEEPSEEK_API_KEY", "").strip()
                or os.environ.get("OPENAI_API_KEY", "").strip()
            )
        default_model = DEFAULT_MODEL
        if provider == "deepseek":
            default_model = "deepseek-v4-flash"
        elif provider == "gemini":
            default_model = "gemini-3.1-flash-lite"
        return cls(
            policy_id=str(raw.get("policy_id", "craftax_react_groq_v1")),
            inference_url=str(
                raw.get("inference_url", raw.get("base_url", default_url))
            ),
            api_key=api_key,
            model=str(raw.get("model", default_model)),
            temperature=float(raw.get("temperature", 0.0)),
            max_tokens=max(int(raw.get("max_tokens", 512)), 32),
            system_prompt=str(raw.get("system_prompt", DEFAULT_SYSTEM_PROMPT)),
            use_lm=bool(raw.get("use_lm", True)),
            provider=provider,
            min_actions_per_call=max(
                int(raw.get("min_actions_per_call", DEFAULT_MIN_ACTIONS_PER_CALL)), 1
            ),
            max_actions_per_call=max(
                int(raw.get("max_actions_per_call", DEFAULT_MAX_ACTIONS_PER_CALL)), 1
            ),
        )


@dataclass
class AgentTurnResult:
    actions: list[str]
    assistant_text: str
    invalid_parse: bool
    repaired: bool
    usage: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    model: str | None = None

    @property
    def action(self) -> str:
        return self.actions[0] if self.actions else "noop"


@dataclass(frozen=True)
class ParsedActions:
    actions: list[str]
    invalid_parse: bool
    repaired: bool
    error: str | None = None


def _clean_action_token(raw: Any) -> str:
    return str(raw or "").strip().strip("\"'`.,;")


def _resolve_action(candidate: str, valid: list[str]) -> tuple[str, bool, bool]:
    cleaned = _clean_action_token(candidate)
    if cleaned in valid:
        return cleaned, False, False
    if cleaned in ACTION_WORDS:
        return valid[0], True, True
    return "", False, False


def parse_actions_text(
    raw_text: Any,
    valid_actions: list[str] | None = None,
    *,
    min_actions: int = DEFAULT_MIN_ACTIONS_PER_CALL,
    max_actions: int = DEFAULT_MAX_ACTIONS_PER_CALL,
    steps_remaining: int = DEFAULT_MAX_ACTIONS_PER_CALL,
) -> ParsedActions:
    """Parse a batched action plan from LLM JSON (code-policy shape: {"actions": [...]})."""
    valid = [
        action
        for action in ACTION_WORDS
        if not valid_actions or action in valid_actions
    ]
    if not valid:
        return ParsedActions([], True, False, "no_valid_actions")
    batch_cap = max(1, min(max_actions, steps_remaining))
    batch_floor = max(1, min(min_actions, batch_cap))
    text = str(raw_text or "").strip()
    parsed_actions: list[str] = []
    invalid_parse = False
    repaired = False
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            raw_list = parsed.get("actions")
            if isinstance(raw_list, list):
                for item in raw_list:
                    action, bad, fixed = _resolve_action(item, valid)
                    if not action:
                        continue
                    invalid_parse = invalid_parse or bad
                    repaired = repaired or fixed
                    parsed_actions.append(action)
            if not parsed_actions:
                single = parsed.get("action", parsed.get("move", parsed.get("command")))
                if single is not None:
                    action, bad, fixed = _resolve_action(str(single), valid)
                    if action:
                        parsed_actions.append(action)
                        invalid_parse = bad
                        repaired = fixed
        elif isinstance(parsed, list):
            for item in parsed:
                action, bad, fixed = _resolve_action(item, valid)
                if action:
                    parsed_actions.append(action)
                    invalid_parse = invalid_parse or bad
                    repaired = repaired or fixed
    except json.JSONDecodeError:
        pass
    if not parsed_actions:
        single = parse_action_text(raw_text, valid_actions)
        parsed_actions = [single.action] if single.action else [valid[0]]
        invalid_parse = single.invalid_parse
        repaired = single.repaired
    if len(parsed_actions) > batch_cap:
        parsed_actions = parsed_actions[:batch_cap]
    if len(parsed_actions) < batch_floor and parsed_actions:
        # Keep the plan the model gave; do not pad with synthetic repeats.
        pass
    if not parsed_actions:
        return ParsedActions([valid[0]], True, True, "no_action_found")
    return ParsedActions(parsed_actions, invalid_parse, repaired)


@dataclass(frozen=True)
class ParsedAction:
    action: str
    invalid_parse: bool
    repaired: bool
    error: str | None = None


def parse_action_text(
    raw_text: Any, valid_actions: list[str] | None = None
) -> ParsedAction:
    valid = [
        action
        for action in ACTION_WORDS
        if not valid_actions or action in valid_actions
    ]
    if not valid:
        return ParsedAction("", True, False, "no_valid_actions")
    text = str(raw_text or "").strip()
    candidates: list[str] = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            value = parsed.get("action", parsed.get("move", parsed.get("command")))
            if value is not None:
                candidates.append(str(value).strip())
        elif isinstance(parsed, str):
            candidates.append(parsed.strip())
    except json.JSONDecodeError:
        pass
    match = ACTION_RE.search(text)
    if match:
        candidates.append(match.group(1).strip())
    if text in ACTION_WORDS:
        candidates.append(text)
    for candidate in candidates:
        cleaned = candidate.strip().strip("\"'`.,;")
        if cleaned in valid:
            return ParsedAction(cleaned, False, False)
        if cleaned in ACTION_WORDS:
            return ParsedAction(valid[0], True, True, f"invalid_action:{cleaned}")
    return ParsedAction(valid[0], True, True, "no_action_found")


async def chat_completion(config: AgentPolicyConfig, prompt: str) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.api_key}",
    }
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
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return {
        "assistant_text": str(content),
        "usage": payload.get("usage", {}),
        "request_id": payload.get("id"),
    }


class AgentPolicy:
    ACTOR = "craftax_agent"

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
            raise RuntimeError(
                "craftax policy called with no remaining steps or llm calls"
            )
        valid_actions = list(readout.get("valid_actions") or ACTION_WORDS)
        batch_cap = max(1, min(self.config.max_actions_per_call, steps_remaining))
        batch_floor = max(1, min(self.config.min_actions_per_call, batch_cap))
        observation_text = str(readout.get("observation_text") or "")
        prompt = "\n".join(
            [
                objective,
                "",
                observation_text,
                "",
                f"last_actions={json.dumps(action_history[-16:])}",
                f"steps_remaining={steps_remaining}",
                f"llm_calls_remaining={llm_calls_remaining}",
                f"valid_actions={', '.join(valid_actions)}",
                f"Plan {batch_floor}-{batch_cap} valid actions to execute sequentially before the next observation.",
                'Reply with JSON only, for example {"actions":["do","right","do","left","do"]}.',
            ]
        )
        if not self.config.use_lm:
            raise RuntimeError(
                "craftax react policy requires use_lm=true for GELO validation"
            )
        if not self.config.api_key:
            raise RuntimeError(
                f"missing_api_key provider={self.config.provider} policy={self.config.policy_id}"
            )
        inference = await chat_completion(self.config, prompt)
        parsed = parse_actions_text(
            inference["assistant_text"],
            valid_actions,
            min_actions=batch_floor,
            max_actions=batch_cap,
            steps_remaining=steps_remaining,
        )
        return AgentTurnResult(
            actions=list(parsed.actions),
            assistant_text=inference["assistant_text"],
            invalid_parse=parsed.invalid_parse,
            repaired=parsed.repaired,
            usage=dict(inference.get("usage", {})),
            request_id=inference.get("request_id"),
            model=self.config.model,
        )
