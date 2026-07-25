from __future__ import annotations

import asyncio

import pytest

from containers.react import craftax_singleplayer_container as service
from containers.react import trace_emitter


def test_propagated_context_keeps_collector_token_out_of_context(monkeypatch) -> None:
    created = []

    class FakeEmitter:
        def __init__(self, base_url, context, timeout=10.0, collector_token=None):
            self.entry = {
                "base_url": base_url,
                "context": context,
                "collector_token": collector_token,
                "events": [],
            }
            created.append(self.entry)

        def event(self, event_type, payload, **kwargs):
            self.entry["events"].append((event_type, payload, kwargs))
            return f"raw-{len(self.entry['events'])}"

        def flush(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(trace_emitter, "TraceEmitter", FakeEmitter)
    trace = trace_emitter.CraftaxTrace.from_request(
        {
            "trace_context": {
                "SYNTH_TRACE_ID": "trace-1",
                "SYNTH_CAPTURE_ID": "capture-1",
                "SYNTH_ACTOR_ID": "agent-1",
                "SYNTH_ACTOR_SESSION_ID": "session-1",
                "SYNTH_TRACE_COLLECTOR_URL": "http://collector",
                "SYNTH_TRACE_COLLECTOR_TOKEN": "policy-secret-token",
                "SYNTH_ENVIRONMENT_COLLECTOR_TOKEN": "environment-secret-token",
                "SYNTH_ENVIRONMENT_CAPTURE_ID": "environment-capture-1",
                "SYNTH_ENVIRONMENT_ACTOR_ID": "environment-1",
                "SYNTH_ENVIRONMENT_SESSION_ID": "environment-session-1",
                "SYNTH_ENVIRONMENT_DELEGATION_ID": "environment-delegation-1",
            }
        }
    )
    assert len(created) == 2
    assert [item["collector_token"] for item in created] == [
        "policy-secret-token",
        "environment-secret-token",
    ]
    assert all(not hasattr(item["context"], "collector_token") for item in created)
    assert created[0]["context"].actor_id == "agent-1"
    assert created[0]["context"].capture_id == "capture-1"
    assert created[1]["context"].actor_id == "environment-1"
    assert created[1]["context"].capture_id == "environment-capture-1"
    assert trace.event("agent.action_proposed", {}) == "raw-1"
    assert trace.event("environment.observation", {}, actor="environment") == "raw-1"
    assert created[0]["events"][0][0] == "agent.action_proposed"
    assert created[1]["events"][0][0] == "environment.observation"


def test_sync_and_async_rollouts_preserve_required_trace_context(monkeypatch) -> None:
    contexts = []

    async def fake_execute(payload, **_kwargs):
        contexts.append(payload.get("trace_context"))
        return {"rollout_id": payload.get("rollout_id") or "captured", "status": "completed"}

    class FakeRequest:
        def __init__(self, payload):
            self.payload = payload

        async def json(self):
            return self.payload

    monkeypatch.setattr(service, "_execute_goex_rollout", fake_execute)
    context = {
        "SYNTH_TRACE_ID": "trace-required",
        "SYNTH_CAPTURE_ID": "capture-required",
        "SYNTH_ACTOR_ID": "actor-required",
        "SYNTH_ACTOR_SESSION_ID": "session-required",
        "SYNTH_TRACE_COLLECTOR_URL": "http://collector",
        "SYNTH_TRACE_COLLECTOR_TOKEN": "policy-secret-token",
        "SYNTH_ENVIRONMENT_COLLECTOR_TOKEN": "environment-secret-token",
        "SYNTH_ENVIRONMENT_CAPTURE_ID": "environment-capture-required",
        "SYNTH_ENVIRONMENT_ACTOR_ID": "environment-required",
        "SYNTH_ENVIRONMENT_SESSION_ID": "environment-session-required",
        "SYNTH_ENVIRONMENT_DELEGATION_ID": "environment-delegation-required",
    }

    async def exercise():
        await service.rollout(
            FakeRequest(
                {
                    "env": {"config": {}, "seed": 1},
                    "policy": {"config": {}},
                    "trace_context": context,
                }
            )
        )
        submitted = await service.rollouts(
            FakeRequest(
                {
                    "rollout_id": "async-captured",
                    "env": {"config": {}, "seed": 2},
                    "policy": {"config": {}},
                    "trace_context": context,
                }
            )
        )
        await service.ROLLOUT_TASKS[submitted["rollout_id"]]

    asyncio.run(exercise())
    assert contexts == [context, context]


def test_capture_context_rejects_missing_secret_or_environment_identity() -> None:
    base = {
        "SYNTH_TRACE_ID": "trace-required",
        "SYNTH_CAPTURE_ID": "capture-required",
        "SYNTH_ACTOR_ID": "actor-required",
        "SYNTH_ACTOR_SESSION_ID": "session-required",
        "SYNTH_TRACE_COLLECTOR_URL": "http://collector",
        "SYNTH_TRACE_COLLECTOR_TOKEN": "policy-secret-token",
        "SYNTH_ENVIRONMENT_COLLECTOR_TOKEN": "environment-secret-token",
        "SYNTH_ENVIRONMENT_CAPTURE_ID": "environment-capture-required",
        "SYNTH_ENVIRONMENT_ACTOR_ID": "environment-required",
        "SYNTH_ENVIRONMENT_SESSION_ID": "environment-session-required",
        "SYNTH_ENVIRONMENT_DELEGATION_ID": "environment-delegation-required",
    }
    for missing in (
        "SYNTH_TRACE_COLLECTOR_TOKEN",
        "SYNTH_ENVIRONMENT_COLLECTOR_TOKEN",
        "SYNTH_ENVIRONMENT_CAPTURE_ID",
        "SYNTH_ENVIRONMENT_ACTOR_ID",
        "SYNTH_ENVIRONMENT_SESSION_ID",
        "SYNTH_ENVIRONMENT_DELEGATION_ID",
    ):
        malformed = dict(base)
        del malformed[missing]
        with pytest.raises(ValueError, match=missing):
            trace_emitter.CraftaxTrace.from_request({"trace_context": malformed})

    malformed_value = dict(base)
    malformed_value["SYNTH_TRACE_ID"] = 1
    with pytest.raises(ValueError, match="keys and values must be strings"):
        trace_emitter.CraftaxTrace.from_request(
            {"trace_context": malformed_value}
        )


def test_achievement_rewards_are_sparse_and_preserve_identity() -> None:
    events = []

    class FakeTrace:
        def event(self, event_type, payload, **kwargs):
            events.append((event_type, payload, kwargs))
            return f"reward-{len(events)}"

    trace = FakeTrace()
    assert (
        service._emit_achievement_rewards(
            trace,
            step=3,
            new_achievements=[],
            current_achievements={"collect_wood"},
            total_reward=1.0,
            action_event="action-3",
            observation_event="observation-4",
        )
        == []
    )
    assert events == []

    emitted = service._emit_achievement_rewards(
        trace,
        step=4,
        new_achievements=["collect_stone", "make_wood_pickaxe"],
        current_achievements={
            "collect_wood",
            "collect_stone",
            "make_wood_pickaxe",
        },
        total_reward=3.0,
        action_event="action-4",
        observation_event="observation-5",
    )

    assert emitted == ["reward-1", "reward-2"]
    assert [event[1]["achievement"] for event in events] == [
        "collect_stone",
        "make_wood_pickaxe",
    ]
    assert all(event[1]["value"] == 1.0 for event in events)
    assert all(event[2]["actor"] == "environment" for event in events)
    assert all(
        event[2]["caused_by"] == ("action-4", "observation-5") for event in events
    )
