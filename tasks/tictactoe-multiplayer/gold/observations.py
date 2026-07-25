"""Per-agent observation projections (MARL)."""

from __future__ import annotations

from typing import Any

from gold.engine import AGENT_IDS
from gold.render import build_render_state
from gold.state import PrivateState, PublicState


def project_observation_for_agent(
    public: PublicState,
    private: PrivateState,
    agent_id: str,
    profile: str = "llm_text",
) -> dict[str, Any]:
    agent_index = AGENT_IDS.index(agent_id)
    is_active = public.current_agent == agent_id and not private.terminated
    if profile == "llm_text":
        render = build_render_state(public)
        return {
            "profile": profile,
            "agent_id": agent_id,
            "agent_index": agent_index,
            "board_text": render.ascii_board,
            "turn": public.to_dict()["turn"],
            "current_agent": public.current_agent,
            "legal_agent_ids": [public.current_agent] if is_active else [],
            "winner": public.winner,
            "terminated": private.terminated,
            "last_joint_event": None,
        }
    if profile == "structured_facts":
        return {
            "profile": profile,
            "agent_id": agent_id,
            "agent_index": agent_index,
            "board": list(public.board),
            "turn": public.to_dict()["turn"],
            "current_agent": public.current_agent,
            "legal_agent_ids": [public.current_agent] if is_active else [],
            "winner": public.winner,
            "step_index": private.step_index,
            "ply": private.ply,
        }
    raise ValueError(f"unknown observation profile: {profile}")


def project_observations(
    public: PublicState,
    private: PrivateState,
    profile: str = "llm_text",
    last_joint_event: str | None = None,
) -> dict[str, dict[str, Any]]:
    observations: dict[str, dict[str, Any]] = {}
    for agent_id in AGENT_IDS:
        obs = project_observation_for_agent(public, private, agent_id, profile=profile)
        if last_joint_event is not None:
            obs["last_joint_event"] = last_joint_event
        observations[agent_id] = obs
    return observations
