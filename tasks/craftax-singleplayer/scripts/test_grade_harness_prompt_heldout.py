"""Offline tests for the gold_python harness+prompt heldout grader.

No live LLM calls: every test injects a deterministic stub completer.
Run: python3 scripts/test_grade_harness_prompt_heldout.py
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import grade_harness_prompt_heldout as grader

from containers.react.agent_policy import AgentPolicy, AgentPolicyConfig

BASELINE = {
    "schema_version": "factorybench.craftax_harness_prompt.v1",
    "candidate_id": "craftax_harness_prompt_baseline_v1",
    "entrypoint": "containers/react/agent_policy.py",
    "execution_contract_version": "factorybench.craftax_harness_prompt.v1",
    "git_remote": "factorybench://seeded-candidate",
    "system_prompt": "Prefer resting and waiting. Reply with JSON only.",
    "provider": "groq",
    "model": "openai/gpt-oss-120b",
    "temperature": 0.0,
    "max_tokens": 256,
    "harness": {
        "context_window": 4,
        "compact_after_turns": 99,
        "enable_todo": False,
        "enable_scratch": False,
        "enable_rules_search": False,
        "enable_compact_history": False,
        "max_actions_per_call": 3,
        "max_tool_turns_per_decision": 0,
        "min_actions_per_call": 1,
    },
    "cost_bounds": {"heldout_seeds": [11, 17], "max_steps": 8, "max_llm_turns": 2},
    "notes": "test baseline",
}

CANDIDATE = {
    "schema_version": "factorybench.craftax_harness_prompt.v1",
    "candidate_id": "craftax_harness_prompt_seed_v1",
    "entrypoint": "containers/react/agent_policy.py",
    "execution_contract_version": "factorybench.craftax_harness_prompt.v1",
    "git_remote": "factorybench://seeded-candidate",
    "system_prompt": "Harvest aggressively. Reply with JSON only.",
    "provider": "groq",
    "model": "openai/gpt-oss-120b",
    "temperature": 0.0,
    "max_tokens": 384,
    "harness": {
        "context_window": 12,
        "compact_after_turns": 8,
        "enable_todo": True,
        "enable_scratch": True,
        "enable_rules_search": True,
        "enable_compact_history": True,
        "max_actions_per_call": 8,
        "max_tool_turns_per_decision": 1,
        "min_actions_per_call": 4,
    },
    "cost_bounds": {"heldout_seeds": [11, 17], "max_steps": 8, "max_llm_turns": 2},
    "notes": "test candidate",
}


def make_completer(script: dict[str, list[str]], calls: list[dict[str, Any]]):
    """Deterministic stub: pops scripted replies per policy_id, records calls."""

    async def completer(
        config: AgentPolicyConfig,
        prompt: str | None = None,
        *,
        messages: list[dict[str, Any]] | None = None,
        trace: Any = None,
        llm_call: int | None = None,
    ) -> dict[str, Any]:
        del prompt, trace, llm_call
        calls.append({"policy_id": config.policy_id, "messages": copy.deepcopy(messages)})
        replies = script[config.policy_id]
        text = replies.pop(0) if len(replies) > 1 else replies[0]
        return {
            "assistant_text": text,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "request_id": "stub",
            "finish_reason": "stop",
        }

    return completer


def run_grade(baseline=BASELINE, candidate=CANDIDATE, *, script=None, calls=None):
    calls = calls if calls is not None else []
    script = script or {
        "craftax_harness_prompt_baseline_v1": ['{"actions":["noop","rest","noop"]}'],
        "craftax_harness_prompt_seed_v1": [
            '{"actions":["do","right","do","do","make_wood_pickaxe","make_wood_sword"]}'
        ],
    }
    return asyncio.run(
        grader.grade_pair(
            baseline=baseline,
            candidate=candidate,
            seeds=[11, 17],
            max_steps=8,
            max_llm_turns=2,
            task_path="tasks/policy_dev_template.json",
            completer=make_completer(script, calls),
        )
    )


class ValidationTest(unittest.TestCase):
    def test_accepts_v1_schema(self) -> None:
        validated = grader._validated_candidate(CANDIDATE, baseline=BASELINE)
        self.assertEqual(validated["max_tool_turns_per_decision"], 1)
        self.assertEqual(validated["context_window"], 12)
        self.assertTrue(validated["enable_rules_search"])

    def test_rejects_rust_schema(self) -> None:
        bad = {**CANDIDATE, "schema_version": "factorybench.craftax_rust_harness.v1"}
        with self.assertRaisesRegex(ValueError, "candidate_schema_version_invalid"):
            grader._validated_candidate(bad, baseline=BASELINE)

    def test_provider_drift_refused(self) -> None:
        bad = {**CANDIDATE, "provider": "openai"}
        with self.assertRaisesRegex(ValueError, "candidate_provider_drift:openai/"):
            run_grade(candidate=bad)

    def test_model_drift_refused(self) -> None:
        bad = {**CANDIDATE, "model": "openai/gpt-oss-20b"}
        with self.assertRaisesRegex(ValueError, "candidate_provider_drift"):
            grader._validated_candidate(bad, baseline=BASELINE)

    def test_unknown_candidate_field_refused(self) -> None:
        bad = {**CANDIDATE, "reasoning_effort": "high"}
        with self.assertRaisesRegex(
            ValueError, "candidate_unknown_fields:reasoning_effort"
        ):
            grader._validated_candidate(bad, baseline=BASELINE)

    def test_unknown_harness_field_refused(self) -> None:
        bad = copy.deepcopy(CANDIDATE)
        bad["harness"]["batch_bonus"] = 2
        with self.assertRaisesRegex(
            ValueError, "candidate_harness_unknown_fields:batch_bonus"
        ):
            run_grade(candidate=bad)

    def test_action_batch_bounds_refused(self) -> None:
        bad = copy.deepcopy(CANDIDATE)
        bad["harness"]["max_actions_per_call"] = 40
        with self.assertRaisesRegex(ValueError, "candidate_action_batch_bounds_invalid"):
            grader._validated_candidate(bad, baseline=BASELINE)


class PairedScoringTest(unittest.TestCase):
    def test_paired_scoring_math_and_records(self) -> None:
        scorecard = run_grade()
        self.assertEqual(scorecard["schema_version"], grader.SCHEMA_VERSION)
        self.assertEqual(scorecard["rollout_count"], 4)
        self.assertEqual(scorecard["heldout_seed_count"], 2)
        self.assertEqual(scorecard["baseline_mean"], 0.0)
        self.assertGreater(scorecard["champion_mean"], 0.0)
        self.assertAlmostEqual(
            scorecard["paired_mean_lift"],
            scorecard["champion_mean"] - scorecard["baseline_mean"],
        )
        self.assertEqual(scorecard["baseline_score"], scorecard["baseline_mean"])
        self.assertEqual(scorecard["held_out_score"], scorecard["champion_mean"])
        self.assertEqual(
            [row["seed"] for row in scorecard["records"]["candidate"]], [11, 17]
        )
        self.assertEqual(scorecard["lift_verdict"], "accepted")
        self.assertTrue(scorecard["accepted"])
        # Evals-side required scorecard keys.
        for key in (
            "accepted",
            "baseline_mean",
            "champion_mean",
            "lift_verdict",
            "rollout_count",
            "llm_calls",
            "total_tokens",
            "gamebench_source_sha",
            "task_fixture_sha256",
            "baseline_sha256",
            "candidate_sha256",
        ):
            self.assertIn(key, scorecard)
        self.assertEqual(scorecard["llm_calls"], 8)  # 2 seeds x 2 arms x 2 decisions
        self.assertGreater(scorecard["total_tokens"], 0)

    def test_deterministic_output(self) -> None:
        first = run_grade()
        second = run_grade()
        self.assertEqual(
            json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True)
        )

    def test_no_lift_is_rejected(self) -> None:
        script = {
            "craftax_harness_prompt_baseline_v1": ['{"actions":["noop"]}'],
            "craftax_harness_prompt_seed_v1": ['{"actions":["noop","noop","noop","noop"]}'],
        }
        scorecard = run_grade(script=script)
        self.assertEqual(scorecard["paired_mean_lift"], 0.0)
        self.assertFalse(scorecard["accepted"])
        self.assertEqual(scorecard["lift_verdict"], "rejected")


class ToolLoopTest(unittest.TestCase):
    def test_tool_turn_then_actions(self) -> None:
        calls: list[dict[str, Any]] = []
        script = {
            "craftax_harness_prompt_baseline_v1": ['{"actions":["noop"]}'],
            "craftax_harness_prompt_seed_v1": [
                '{"tool":"search_game_rules","args":{"query":"pickaxe"}}',
                '{"actions":["do","right","do","do"]}',
            ],
        }
        scorecard = run_grade(script=script, calls=calls)
        candidate_rows = scorecard["records"]["candidate"]
        # First candidate decision consumed one tool sub-call.
        self.assertEqual(candidate_rows[0]["tool_sub_calls"], 1)
        tool_followups = [
            call
            for call in calls
            if call["policy_id"] == "craftax_harness_prompt_seed_v1"
            and len(call["messages"]) > 2
        ]
        self.assertTrue(tool_followups)
        tool_result_msg = tool_followups[0]["messages"][-1]["content"]
        self.assertIn("tool_result", tool_result_msg)
        self.assertIn("pickaxe", tool_result_msg)

    def test_tools_disabled_tool_reply_falls_back(self) -> None:
        script = {
            "craftax_harness_prompt_baseline_v1": [
                '{"tool":"search_game_rules","args":{"query":"pickaxe"}}'
            ],
            "craftax_harness_prompt_seed_v1": ['{"actions":["do"]}'],
        }
        scorecard = run_grade(script=script)
        baseline_rows = scorecard["records"]["baseline"]
        # Baseline has tools off: the tool reply is not honored, no sub-calls,
        # and the unparseable reply degrades to the fallback action.
        self.assertEqual(baseline_rows[0]["tool_sub_calls"], 0)
        self.assertGreater(baseline_rows[0]["invalid_parse_count"], 0)


class KnobBehaviorTest(unittest.TestCase):
    def test_context_window_and_compact_history(self) -> None:
        captured: list[str] = []

        async def completer(config, prompt=None, *, messages=None, trace=None, llm_call=None):
            del config, prompt, trace, llm_call
            captured.append(messages[-1]["content"])
            return {"assistant_text": '{"actions":["noop"]}', "usage": {}}

        config = AgentPolicyConfig.from_mapping(
            {
                "policy_id": "knob_test",
                "system_prompt": "test",
                "harness": {
                    "context_window": 2,
                    "enable_compact_history": True,
                    "compact_after_turns": 3,
                    "max_actions_per_call": 2,
                    "min_actions_per_call": 1,
                },
            }
        )
        policy = AgentPolicy(config, completer=completer)
        asyncio.run(
            policy.choose_action(
                readout={"observation_text": "obs", "valid_actions": ["noop", "do"]},
                objective="obj",
                action_history=["do", "do", "right", "left", "up"],
                steps_remaining=4,
                llm_calls_remaining=2,
            )
        )
        prompt = captured[0]
        self.assertIn('last_actions=["left", "up"]', prompt)
        self.assertIn('earlier_action_counts={"do":2,"right":1}', prompt)

    def test_scratch_note_persists_across_decisions(self) -> None:
        responses = [
            '{"tool":"scratch","args":{"note":"go mine iron"}}',
            '{"actions":["noop"]}',
            '{"actions":["noop"]}',
        ]
        captured: list[str] = []

        async def completer(config, prompt=None, *, messages=None, trace=None, llm_call=None):
            del config, prompt, trace, llm_call
            captured.append(messages[-1]["content"])
            return {"assistant_text": responses.pop(0), "usage": {}}

        config = AgentPolicyConfig.from_mapping(
            {
                "policy_id": "scratch_test",
                "system_prompt": "test",
                "harness": {
                    "enable_scratch": True,
                    "max_tool_turns_per_decision": 1,
                    "max_actions_per_call": 1,
                    "min_actions_per_call": 1,
                },
            }
        )
        policy = AgentPolicy(config, completer=completer)
        readout = {"observation_text": "obs", "valid_actions": ["noop"]}
        common = dict(
            readout=readout, objective="obj", steps_remaining=4, llm_calls_remaining=4
        )
        asyncio.run(policy.choose_action(action_history=[], **common))
        asyncio.run(policy.choose_action(action_history=["noop"], **common))
        self.assertIn('scratch_note="go mine iron"', captured[-1])


if __name__ == "__main__":
    unittest.main()
