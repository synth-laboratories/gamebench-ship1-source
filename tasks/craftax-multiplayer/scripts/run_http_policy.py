#!/usr/bin/env python3
"""Run the deterministic Craftax-Coop policy through either HTTP runtime."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from policies.heuristic_baseline import act


def request(base_url: str, method: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        base_url + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--runtime", choices=("python", "rust"), required=True)
    parser.add_argument("--seed", type=int, default=404)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    health = request(args.base_url, "GET", "/health")
    result = request(args.base_url, "POST", "/reset", {"seed": args.seed})
    observations = result["observations"]
    total_reward = 0.0
    trace = []
    terminal_reason = None
    for index in range(args.steps):
        joint_action = {agent: act(observation) for agent, observation in observations.items()}
        result = request(args.base_url, "POST", "/step", {"joint_action": joint_action})
        observations = result["observations"]
        total_reward += float(result["rewards"]["agent_0"])
        trace.append({"step": index + 1, "actions": joint_action, "reward": result["rewards"]["agent_0"]})
        terminal_reason = result.get("info", {}).get("termination_reason")
        if result["dones"].get("__all__"):
            break
    nev = request(args.base_url, "GET", "/nev")
    first = observations["agent_0"]
    report = {
        "lane": "shared_http_heuristic",
        "runtime": args.runtime,
        "health": health,
        "seed": args.seed,
        "steps": len(trace),
        "total_shared_reward": total_reward,
        "terminated": bool(terminal_reason),
        "termination_reason": terminal_reason,
        "achievements": sorted(name for name, earned in first["shared"]["achievements"].items() if earned),
        "trade_count": first["shared"]["trade_count"],
        "structured_event_count": len(nev["structured"]),
        "legacy_event_count": len(nev["legacy"]),
        "observation_contract": {
            "agents": sorted(observations),
            "ascii": all(bool(observation.get("ascii")) for observation in observations.values()),
            "last_joint_event": all("last_joint_event" in observation for observation in observations.values()),
        },
        "trace": trace,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "trace"}, sort_keys=True))


if __name__ == "__main__":
    main()
