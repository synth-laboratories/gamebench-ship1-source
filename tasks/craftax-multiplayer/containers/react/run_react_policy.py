"""Gemini/OpenAI-compatible independent ReAct policies for all Coop agents."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

TASK_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TASK_ROOT))
from gold_python.engine import CraftaxCoopEnv

SYSTEM = """You control one member of a three-agent Craftax-Coop team. Coordinate through the teammate dashboard and request/give actions. Respect your Warrior, Forager, or Miner specialization. Return JSON only: {\"action\":\"one exact legal action\",\"reason\":\"short reason\"}."""


def _completion(api_key: str, model: str, observation: dict[str, Any]) -> dict[str, Any]:
    prompt = json.dumps({"objective":"survive, trade across roles, descend nine levels, and defeat the boss","observation":observation}, separators=(",", ":"))
    payload = json.dumps({"model":model,"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],"temperature":0,"max_tokens":160}).encode()
    request = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", data=payload, headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = json.loads(response.read())
    text = raw["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {}
    action = str(parsed.get("action", "noop"))
    legal = observation["legal_actions"]
    return {"kind": action if action in legal else "noop", "assistant_text": text, "usage": raw.get("usage", {}), "request_id": raw.get("id")}


async def rollout(seed: int, max_steps: int, model: str, api_key: str) -> dict[str, Any]:
    env = CraftaxCoopEnv(); observations, _ = env.reset(seed); trace=[]; total=0.0
    for ply in range(max_steps):
        decisions = await asyncio.gather(*[asyncio.to_thread(_completion, api_key, model, observations[a]) for a in env.agent_ids])
        joint = {agent:{"kind":decisions[i]["kind"]} for i,agent in enumerate(env.agent_ids)}
        observations,rewards,dones,info=env.step(joint); total+=rewards[env.agent_ids[0]]
        trace.append({"ply":ply,"joint_action":joint,"responses":{a:decisions[i]["assistant_text"] for i,a in enumerate(env.agent_ids)},"reward":rewards[env.agent_ids[0]],"events":info["events"]})
        if dones["__all__"]: break
    state=env._require_state()
    return {"schema_version":"gamebench.rollout.v1","env_family":env.env_family,"lane":"python","policy_kind":"react","provider":"gemini","model":model,"seed":seed,"steps":state.timestep,"shared_reward":total,"achievements":sorted(k for k,v in state.achievements.items() if v),"trades":state.trade_count,"termination_reason":state.termination_reason,"state_hash":env.state_hash(),"trace":trace}


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--seed",type=int,default=101); parser.add_argument("--steps",type=int,default=30); parser.add_argument("--model",default="gemini-3.1-flash-lite"); parser.add_argument("--output",type=Path); args=parser.parse_args()
    key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key: raise SystemExit("missing GEMINI_API_KEY or GOOGLE_API_KEY")
    result=asyncio.run(rollout(args.seed,args.steps,args.model,key)); encoded=json.dumps(result,indent=2,sort_keys=True)
    if args.output: args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(encoded+"\n")
    print(encoded)


if __name__ == "__main__": main()
