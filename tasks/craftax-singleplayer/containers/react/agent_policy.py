"""OpenAI-compatible Craftax ReAct policy.

Harness knobs (all candidate-tunable via ``AgentPolicyConfig`` or a nested
``harness`` mapping in the raw policy config):

- ``max_actions_per_call`` / ``min_actions_per_call``: action batch bounds.
- ``context_window``: how many trailing actions are shown verbatim as
  ``last_actions`` in the decision prompt.
- ``enable_compact_history`` + ``compact_after_turns``: when enabled and the
  action history exceeds ``compact_after_turns``, actions older than the
  context window are folded into an ``earlier_action_counts`` summary line
  instead of being dropped silently.
- ``enable_todo`` / ``enable_scratch`` / ``enable_rules_search``: optional
  local tools (``todo_list``, ``scratch``, ``search_game_rules``). Tool state
  persists across decisions within one episode and is surfaced in the prompt.
- ``max_tool_turns_per_decision``: how many ``{"tool": ...}`` replies are
  honored per decision before an actions reply is required. Tool sub-calls
  share the decision's LLM turn budget slot; their token usage is aggregated
  into the returned ``AgentTurnResult.usage``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

try:
    from containers.react.trace_emitter import CraftaxTrace
except Exception:  # pragma: no cover - trace emission needs the container build
    # Outside the container build context (e.g. heldout grading from a sealed
    # checkout) synth-containers is not installed. Tracing is optional there:
    # callers pass trace=None and no trace events are emitted.
    CraftaxTrace = None  # type: ignore[assignment, misc]

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
DEFAULT_CONTEXT_WINDOW = 16
DEFAULT_COMPACT_AFTER_TURNS = 8

# Facts below are verified against gold_python/engine.py (movement, _do,
# _craft recipes, achievement rewards). Keep them in sync with the engine.
GAME_RULES_LINES = (
    "valid_actions: " + ", ".join(str(action) for action in CRAFTAX_ACTIONS),
    "movement: left/right/up/down turn the player toward, then move in, that direction on the grid.",
    "do: interacts with the tile the player is facing (front_tile): tree gives wood, stone gives stone, coal gives coal, iron gives iron (higher tiers need a better pickaxe).",
    "crafting: every make_* action requires standing next to a crafting_table; make_iron_* additionally requires a nearby furnace.",
    "recipes: make_wood_pickaxe costs 1 wood; make_stone_pickaxe costs 1 wood + 1 stone; make_iron_pickaxe costs 1 wood + 1 stone + 1 iron + 1 coal; swords cost the same as the matching pickaxe.",
    "placing: place_table places a crafting table and place_furnace places a furnace on a nearby tile when resources allow.",
    "reward: each first-time achievement (for example collect_wood, make_wood_pickaxe, collect_stone) grants +1 reward; repeats grant nothing.",
    "waste: noop, rest, and invalid actions never unlock achievements on their own.",
)


@dataclass
class AgentPolicyConfig:
    policy_id: str = "craftax_react_groq_v1"
    inference_url: str = DEFAULT_URL
    api_key: str = ""
    model: str = DEFAULT_MODEL
    temperature: float = 0.0
    # 512 is measured adequate for the providers this policy defaults to: Groq
    # gpt-oss-120b answers in ~180-230 tokens and Gemini flash-lite in ~11. Qwen3.5
    # instead reasons in prose on this plain-JSON prompt and truncates at 512 and at
    # 2048 alike, so it needs the tool-calling policy variant, not a larger budget.
    max_tokens: int = 512
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    use_lm: bool = True
    provider: str = "groq"
    min_actions_per_call: int = DEFAULT_MIN_ACTIONS_PER_CALL
    max_actions_per_call: int = DEFAULT_MAX_ACTIONS_PER_CALL
    context_window: int = DEFAULT_CONTEXT_WINDOW
    enable_compact_history: bool = False
    compact_after_turns: int = DEFAULT_COMPACT_AFTER_TURNS
    enable_todo: bool = False
    enable_scratch: bool = False
    enable_rules_search: bool = False
    max_tool_turns_per_decision: int = 0

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> AgentPolicyConfig:
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
        # Harness knobs may arrive flat or nested under a "harness" mapping
        # (the factorybench.craftax_harness_prompt.v1 candidate shape).
        harness = raw.get("harness")
        knobs: dict[str, Any] = (
            {**raw, **harness} if isinstance(harness, Mapping) else dict(raw)
        )
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
                int(knobs.get("min_actions_per_call", DEFAULT_MIN_ACTIONS_PER_CALL)), 1
            ),
            max_actions_per_call=max(
                int(knobs.get("max_actions_per_call", DEFAULT_MAX_ACTIONS_PER_CALL)), 1
            ),
            context_window=max(
                int(knobs.get("context_window", DEFAULT_CONTEXT_WINDOW)), 1
            ),
            enable_compact_history=bool(knobs.get("enable_compact_history", False)),
            compact_after_turns=max(
                int(knobs.get("compact_after_turns", DEFAULT_COMPACT_AFTER_TURNS)), 1
            ),
            enable_todo=bool(knobs.get("enable_todo", False)),
            enable_scratch=bool(knobs.get("enable_scratch", False)),
            enable_rules_search=bool(knobs.get("enable_rules_search", False)),
            max_tool_turns_per_decision=max(
                int(knobs.get("max_tool_turns_per_decision", 0)), 0
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
    finish_reason: str | None = None
    request_event_id: str | None = None
    response_event_id: str | None = None
    proposal_event_id: str | None = None
    tool_turns: int = 0

    @property
    def action(self) -> str:
        return self.actions[0] if self.actions else "noop"

    @property
    def truncated(self) -> bool:
        """The provider stopped at the token budget, so no action batch was emitted."""
        return self.finish_reason == "length"


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


async def chat_completion(
    config: AgentPolicyConfig,
    prompt: str | None = None,
    *,
    messages: list[dict[str, Any]] | None = None,
    trace: CraftaxTrace | None = None,
    llm_call: int | None = None,
) -> dict[str, Any]:
    if messages is None:
        messages = [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": str(prompt or "")},
        ]
    call_correlation_id = f"craftax-call-{llm_call or 0}-{uuid.uuid4().hex}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.api_key}",
        "x-synth-call-correlation-id": call_correlation_id,
    }
    body: dict[str, Any] = {
        "model": config.model,
        "messages": list(messages),
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    if config.provider == "deepseek":
        body["thinking"] = {"type": "disabled"}
    digest_source = json.dumps(messages, sort_keys=True, separators=(",", ":"))
    request_event_id = (
        trace.event(
            "agent.model_call_intent",
            {
                "provider": config.provider,
                "model": config.model,
                "call_correlation_id": call_correlation_id,
                "prompt_digest": "sha256:"
                + hashlib.sha256(digest_source.encode("utf-8")).hexdigest(),
                "llm_call": llm_call,
            },
            structural={"llm_call": llm_call},
        )
        if trace is not None
        else None
    )
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(config.inference_url, headers=headers, json=body)
        response.raise_for_status()
        payload = response.json()
    choice = payload["choices"][0]
    content = choice["message"].get("content", "")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    response_event_id = (
        trace.event(
            "agent.model_call_observed",
            {
                "provider": config.provider,
                "model": config.model,
                "call_correlation_id": call_correlation_id,
                "provider_request_id": payload.get("id"),
                "finish_reason": str(choice.get("finish_reason") or "") or None,
                "usage": payload.get("usage", {}),
                "llm_call": llm_call,
            },
            caused_by=tuple(item for item in (request_event_id,) if item),
            structural={"llm_call": llm_call},
        )
        if trace is not None
        else None
    )
    return {
        "assistant_text": str(content),
        "usage": payload.get("usage", {}),
        "request_id": payload.get("id"),
        # A response cut off at max_tokens cannot carry an action batch. Without
        # this the caller sees only invalid_parse and blames the prompt.
        "finish_reason": str(choice.get("finish_reason") or "") or None,
        "request_event_id": request_event_id,
        "response_event_id": response_event_id,
    }


def _parse_tool_call(raw_text: Any) -> tuple[str, dict[str, Any]] | None:
    """Parse a {"tool": name, "args": {...}} reply; None when it is not one."""
    try:
        parsed = json.loads(str(raw_text or "").strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or "actions" in parsed:
        return None
    name = parsed.get("tool")
    if not isinstance(name, str) or not name.strip():
        return None
    args = parsed.get("args")
    return name.strip(), dict(args) if isinstance(args, Mapping) else {}


def _accumulate_usage(totals: dict[str, int], usage: Mapping[str, Any]) -> None:
    if not isinstance(usage, Mapping) or not usage:
        return
    prompt_tokens = 0
    for key in ("prompt_tokens", "input_tokens", "prompt_token_count"):
        if usage.get(key) is not None:
            prompt_tokens = int(usage[key])
            break
    completion_tokens = 0
    for key in ("completion_tokens", "output_tokens", "candidates_token_count"):
        if usage.get(key) is not None:
            completion_tokens = int(usage[key])
            break
    totals["prompt_tokens"] += prompt_tokens
    totals["completion_tokens"] += completion_tokens
    totals["total_tokens"] += prompt_tokens + completion_tokens
    totals["llm_sub_calls"] += 1


class AgentPolicy:
    ACTOR = "craftax_agent"

    def __init__(
        self,
        config: AgentPolicyConfig,
        *,
        trace: CraftaxTrace | None = None,
        completer: Any | None = None,
    ) -> None:
        """``completer`` is an injectable async replacement for chat_completion
        with the same signature; when provided, no API key is required (used by
        offline grading tests)."""
        self.config = config
        self.trace = trace
        self._completer = completer or chat_completion
        self._requires_api_key = completer is None
        self._todo: list[str] = []
        self._scratch_note: str = ""

    def _enabled_tools(self) -> dict[str, str]:
        tools: dict[str, str] = {}
        if self.config.enable_todo:
            tools["todo_list"] = 'set or read a short todo list; args {"items":["..."]}'
        if self.config.enable_scratch:
            tools["scratch"] = 'save or read a scratch note; args {"note":"..."}'
        if self.config.enable_rules_search:
            tools["search_game_rules"] = 'search the game rules; args {"query":"..."}'
        return tools

    def _run_tool(self, name: str, args: Mapping[str, Any]) -> dict[str, Any]:
        if name not in self._enabled_tools():
            return {"error": f"tool_unavailable:{name}"}
        if name == "todo_list":
            items = args.get("items")
            if isinstance(items, list):
                self._todo = [str(item) for item in items if str(item).strip()][:12]
            return {"todo_list": list(self._todo)}
        if name == "scratch":
            note = args.get("note")
            if isinstance(note, str) and note.strip():
                self._scratch_note = note.strip()[:2000]
            return {"scratch": self._scratch_note}
        query = str(args.get("query") or "").strip().lower()
        matches = [
            line
            for line in GAME_RULES_LINES
            if not query or query in line.lower()
        ][:12]
        return {"matches": matches}

    def _decision_prompt(
        self,
        *,
        objective: str,
        observation_text: str,
        action_history: list[str],
        steps_remaining: int,
        llm_calls_remaining: int,
        valid_actions: list[str],
        batch_floor: int,
        batch_cap: int,
        llm_call: int | None,
    ) -> str:
        context_window = max(1, int(self.config.context_window))
        tail = action_history[-context_window:]
        lines = [
            objective,
            "",
            observation_text,
            "",
            f"last_actions={json.dumps(tail)}",
        ]
        dropped = len(action_history) - len(tail)
        compacted = (
            dropped > 0
            and self.config.enable_compact_history
            and len(action_history) > max(1, int(self.config.compact_after_turns))
        )
        if compacted:
            counts: dict[str, int] = {}
            for action in action_history[:-context_window]:
                counts[action] = counts.get(action, 0) + 1
            lines.append(
                "earlier_action_counts="
                + json.dumps(dict(sorted(counts.items())), separators=(",", ":"))
            )
        if self.trace is not None and dropped > 0:
            self.trace.event(
                "agent.context_compacted",
                {
                    "strategy": "tail_window_with_counts"
                    if compacted
                    else "tail_window",
                    "retained_action_count": len(tail),
                    "dropped_action_count": dropped,
                    "replacement": "last_actions+earlier_action_counts"
                    if compacted
                    else "last_actions",
                },
                structural={"llm_call": llm_call},
            )
        if self.config.enable_todo and self._todo:
            lines.append(f"todo_list={json.dumps(self._todo)}")
        if self.config.enable_scratch and self._scratch_note:
            lines.append(f"scratch_note={json.dumps(self._scratch_note)}")
        lines.extend(
            [
                f"steps_remaining={steps_remaining}",
                f"llm_calls_remaining={llm_calls_remaining}",
                f"valid_actions={', '.join(valid_actions)}",
            ]
        )
        tools = self._enabled_tools()
        tool_budget = int(self.config.max_tool_turns_per_decision)
        if tools and tool_budget > 0:
            listing = "; ".join(f"{name}: {desc}" for name, desc in tools.items())
            lines.append(
                f"Optional tools ({listing}). Call one with "
                '{"tool":"<name>","args":{...}} '
                f"(at most {tool_budget} tool call(s) this turn), then answer with actions."
            )
        lines.extend(
            [
                f"Plan {batch_floor}-{batch_cap} valid actions to execute sequentially before the next observation.",
                'Reply with JSON only, for example {"actions":["do","right","do","left","do"]}.',
            ]
        )
        return "\n".join(lines)

    async def choose_action(
        self,
        *,
        readout: dict[str, Any],
        objective: str,
        action_history: list[str],
        steps_remaining: int,
        llm_calls_remaining: int,
        llm_call: int | None = None,
    ) -> AgentTurnResult:
        if steps_remaining <= 0 or llm_calls_remaining <= 0:
            raise RuntimeError(
                "craftax policy called with no remaining steps or llm calls"
            )
        valid_actions = list(readout.get("valid_actions") or ACTION_WORDS)
        batch_cap = max(1, min(self.config.max_actions_per_call, steps_remaining))
        batch_floor = max(1, min(self.config.min_actions_per_call, batch_cap))
        observation_text = str(readout.get("observation_text") or "")
        if not self.config.use_lm:
            raise RuntimeError(
                "craftax react policy requires use_lm=true for GELO validation"
            )
        if self._requires_api_key and not self.config.api_key:
            raise RuntimeError(
                f"missing_api_key provider={self.config.provider} policy={self.config.policy_id}"
            )
        prompt = self._decision_prompt(
            objective=objective,
            observation_text=observation_text,
            action_history=action_history,
            steps_remaining=steps_remaining,
            llm_calls_remaining=llm_calls_remaining,
            valid_actions=valid_actions,
            batch_floor=batch_floor,
            batch_cap=batch_cap,
            llm_call=llm_call,
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": prompt},
        ]
        tool_budget = (
            int(self.config.max_tool_turns_per_decision)
            if self._enabled_tools()
            else 0
        )
        tool_turns = 0
        usage_totals = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "llm_sub_calls": 0,
        }
        while True:
            inference = await self._completer(
                self.config,
                None,
                messages=messages,
                trace=self.trace,
                llm_call=llm_call,
            )
            _accumulate_usage(usage_totals, inference.get("usage", {}))
            assistant_text = str(inference.get("assistant_text") or "")
            tool_call = _parse_tool_call(assistant_text)
            if tool_call is None or tool_turns >= tool_budget:
                break
            tool_name, tool_args = tool_call
            tool_result = self._run_tool(tool_name, tool_args)
            tool_turns += 1
            if self.trace is not None:
                self.trace.event(
                    "agent.tool_executed",
                    {
                        "tool": tool_name,
                        "args": dict(tool_args),
                        "result": tool_result,
                        "tool_turn": tool_turns,
                    },
                    structural={"llm_call": llm_call, "tool_turn": tool_turns},
                )
            messages.append({"role": "assistant", "content": assistant_text})
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {"tool_result": {"tool": tool_name, **tool_result}},
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + f"\nNow reply with the actions JSON ({batch_floor}-{batch_cap} actions).",
                }
            )
        parsed = parse_actions_text(
            assistant_text,
            valid_actions,
            min_actions=batch_floor,
            max_actions=batch_cap,
            steps_remaining=steps_remaining,
        )
        proposal_event_id = (
            self.trace.event(
                "agent.action_proposed",
                {
                    "actions": list(parsed.actions),
                    "assistant_text": assistant_text,
                    "invalid_parse": parsed.invalid_parse,
                    "repaired": parsed.repaired,
                    "parse_error": parsed.error,
                    "tool_turns": tool_turns,
                },
                caused_by=tuple(
                    item for item in (inference.get("response_event_id"),) if item
                ),
            )
            if self.trace is not None
            else None
        )
        return AgentTurnResult(
            actions=list(parsed.actions),
            assistant_text=assistant_text,
            invalid_parse=parsed.invalid_parse,
            repaired=parsed.repaired,
            usage=usage_totals,
            request_id=inference.get("request_id"),
            model=self.config.model,
            finish_reason=inference.get("finish_reason"),
            request_event_id=inference.get("request_event_id"),
            response_event_id=inference.get("response_event_id"),
            proposal_event_id=proposal_event_id,
            tool_turns=tool_turns,
        )
