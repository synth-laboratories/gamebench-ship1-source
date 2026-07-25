from __future__ import annotations

import asyncio
import sys
import types
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

if "httpx" not in sys.modules:
    httpx = types.ModuleType("httpx")
    httpx.AsyncClient = object
    httpx.Client = object
    httpx.HTTPError = Exception
    httpx.HTTPStatusError = Exception
    httpx.Limits = object
    sys.modules["httpx"] = httpx

if "transformers" not in sys.modules:
    transformers = types.ModuleType("transformers")
    transformers.AutoTokenizer = object
    sys.modules["transformers"] = transformers

from evaluate_tinker_policy_rollouts import sample_policy_text, summarize_model


class _Tokenizer:
    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> str:
        del messages, tokenize, add_generation_prompt
        return "rendered:"

    def __call__(self, text: str, *, add_special_tokens: bool) -> dict[str, list[int]]:
        del text, add_special_tokens
        return {"input_ids": [10, 20]}

    def decode(self, tokens: list[int]) -> str:
        del tokens
        return 'right","right","right","right","right"]}'


class _ModelInput:
    @classmethod
    def from_ints(cls, tokens: list[int]) -> list[int]:
        return tokens


class _SamplingParams:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class _SampleClient:
    sampling_params: _SamplingParams | None = None

    async def sample_async(
        self,
        model_input: Any,
        *,
        num_samples: int,
        sampling_params: _SamplingParams,
    ) -> Any:
        del model_input, num_samples
        self.sampling_params = sampling_params
        sequence = types.SimpleNamespace(tokens=[30, 40], stop_reason="length")
        return types.SimpleNamespace(sequences=[sequence])


class PolicyRolloutMetricsTest(unittest.TestCase):
    def test_sampler_uses_the_requested_token_budget(self) -> None:
        client = _SampleClient()
        tinker = types.SimpleNamespace(
            ModelInput=_ModelInput,
            SamplingParams=_SamplingParams,
        )

        text, stop_reason = asyncio.run(
            sample_policy_text(
                client,
                _Tokenizer(),
                tinker,
                "prompt",
                model="openai/gpt-oss-20b",
                max_tokens=512,
            )
        )

        self.assertEqual(client.sampling_params.max_tokens, 512)
        self.assertEqual(stop_reason, "length")
        self.assertEqual(text, '{"actions":["right","right","right","right","right"]}')

    def test_summary_reports_mean_truncation_and_raw_stop_reasons(self) -> None:
        rows = [
            {
                "model": "test-model",
                "reward": 1.0,
                "achievement_count": 2,
                "decision_calls": 2,
                "parse_rate": 0.5,
                "call_truncation_rate": 0.5,
                "invalid_action_count": 0,
                "achievement_delta": {"collect_wood": 1},
                "turns": [
                    {"stop_reason": "length"},
                    {"stop_reason": "stop"},
                ],
            },
            {
                "model": "test-model",
                "reward": 3.0,
                "achievement_count": 4,
                "decision_calls": 1,
                "parse_rate": 1.0,
                "call_truncation_rate": 0.0,
                "invalid_action_count": 1,
                "achievement_delta": {"collect_stone": 1},
                "turns": [{"stop_reason": None}],
            },
        ]

        summary = summarize_model("test-model", rows)

        self.assertEqual(summary["reward_mean"], 2.0)
        self.assertEqual(summary["call_truncation_rate_mean"], 0.25)
        self.assertEqual(
            summary["stop_reason_counts"],
            {"None": 1, "length": 1, "stop": 1},
        )


if __name__ == "__main__":
    unittest.main()
