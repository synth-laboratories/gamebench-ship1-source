"""Groq chat-completions agent policy (multiplayer joint-action lane)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_SYSTEM_PROMPT = (
    "You are playing tic-tac-toe. Cells are numbered 0-8:\n"
    "0 1 2\n3 4 5\n6 7 8\n"
    "Reply with exactly one legal cell index as JSON: {\"position\": 4} "
    "or XML <position>4</position>. You may also use Ludic coords A1-C3."
)

POSITION_TAG_RE = re.compile(r"<position>\s*(\d+)\s*</position>", re.IGNORECASE)
COORD_RE = re.compile(r"^[ABCabc][123]$")


@dataclass
class GroqPolicyConfig:
    inference_url: str = DEFAULT_GROQ_URL
    api_key: str = ""
    model: str = DEFAULT_GROQ_MODEL
    temperature: float = 0.0
    max_tokens: int = 128
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    actor: str = "groq_lm"

    @classmethod
    def from_mapping(cls, raw: dict[str, Any], *, default_model: str | None = None) -> GroqPolicyConfig:
        api_key = (
            str(raw.get("api_key", "")).strip()
            or os.environ.get("GROQ_API_KEY", "").strip()
            or os.environ.get("OPENAI_API_KEY", "").strip()
        )
        model_default = default_model or os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        return cls(
            inference_url=str(raw.get("inference_url", DEFAULT_GROQ_URL)),
            api_key=api_key,
            model=str(raw.get("model", model_default)),
            temperature=float(raw.get("temperature", 0.0)),
            max_tokens=max(int(raw.get("max_tokens", 128)), 16),
            system_prompt=str(raw.get("system_prompt", DEFAULT_SYSTEM_PROMPT)),
            actor=str(raw.get("actor", "groq_lm")),
        )


@dataclass
class GroqTurnResult:
    position: int
    assistant_text: str
    invalid_parse: bool
    usage: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    error: str | None = None


def _coord_to_index(coord: str) -> int:
    coord = coord.strip().upper()
    if not COORD_RE.match(coord):
        raise ValueError(f"invalid coord: {coord}")
    row = {"A": 0, "B": 1, "C": 2}[coord[0]]
    col = {"1": 0, "2": 1, "3": 2}[coord[1]]
    return row * 3 + col


def _legal_positions(board: list[str]) -> list[int]:
    return [index for index, cell in enumerate(board) if not cell]


def parse_lm_position(raw_text: str, board: list[str]) -> tuple[int, bool]:
    text = raw_text.strip()
    invalid = False
    legal = set(_legal_positions(board))

    match = POSITION_TAG_RE.search(text)
    if match:
        position = int(match.group(1))
        if position in legal:
            return position, invalid
        invalid = True

    if COORD_RE.match(text):
        position = _coord_to_index(text)
        if position in legal:
            return position, invalid
        invalid = True

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            if "position" in parsed:
                position = int(parsed["position"])
                if position in legal:
                    return position, invalid
                invalid = True
            move = str(parsed.get("move", "")).strip().upper()
            if COORD_RE.match(move):
                position = _coord_to_index(move)
                if position in legal:
                    return position, invalid
                invalid = True
    except json.JSONDecodeError:
        pass

    for token in re.findall(r"\b(\d)\b", text):
        position = int(token)
        if position in legal:
            return position, invalid
        invalid = True

    return min(legal), True


def format_lm_prompt(
    observation: dict[str, Any],
    mark: str,
    action_history: list[dict[str, Any]],
) -> str:
    legal = _legal_positions(observation.get("board", []))
    return "\n".join(
        [
            observation.get("board_text", ""),
            f"You are '{mark}' ({observation.get('agent_id', '')}). Legal empty cells (0-8): {json.dumps(legal)}",
            f"Prior moves: {json.dumps(action_history)}",
            "Respond with {\"position\": N} for one legal cell.",
        ]
    )


async def groq_chat(
    config: GroqPolicyConfig,
    user_prompt: str,
) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.api_key}",
    }
    body: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(config.inference_url, headers=headers, json=body)
        response.raise_for_status()
        payload = response.json()
    message = payload["choices"][0]["message"]
    content = message.get("content", "")
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return {
        "assistant_text": str(content),
        "usage": payload.get("usage", {}),
        "request_id": payload.get("id"),
    }


class GroqAgentPolicy:
    def __init__(self, config: GroqPolicyConfig, agent_id: str) -> None:
        self.config = config
        self.agent_id = agent_id

    @property
    def actor(self) -> str:
        return self.config.actor or f"groq_{self.agent_id}"

    async def choose(
        self,
        observation: dict[str, Any],
        mark: str,
        action_history: list[dict[str, Any]],
    ) -> GroqTurnResult:
        user_prompt = format_lm_prompt(observation, mark, action_history)
        try:
            inference = await groq_chat(self.config, user_prompt)
            assistant_text = str(inference["assistant_text"])
            position, invalid_parse = parse_lm_position(assistant_text, list(observation["board"]))
            return GroqTurnResult(
                position=position,
                assistant_text=assistant_text,
                invalid_parse=invalid_parse,
                usage=dict(inference.get("usage", {})),
                request_id=inference.get("request_id"),
            )
        except Exception as exc:
            board = list(observation["board"])
            position, invalid_parse = parse_lm_position("0", board)
            return GroqTurnResult(
                position=position,
                assistant_text="",
                invalid_parse=invalid_parse,
                error=str(exc),
            )
