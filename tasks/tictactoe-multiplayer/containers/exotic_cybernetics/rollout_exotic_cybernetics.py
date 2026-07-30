"""tictactoe-multiplayer exotic-cybernetics rollout with proxied steering budget."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import uuid
from pathlib import Path
from typing import Any

TASK_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = TASK_ROOT.parents[1]
for path in reversed((REPO_ROOT, TASK_ROOT, TASK_ROOT / "gold_python", TASK_ROOT / "shared", TASK_ROOT / "scripts")):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from exotic_cybernetics.policy_loader import load_env_cybernetics_policy, policy_sha256
from exotic_cybernetics.steer_session import SteerBudgetExhausted, SteerSession
from shared.exotic_cybernetics.episode import attach_cybernetics


def _open_proxy_rollout(rollout_id: str) -> None:
    base = os.environ.get("GAMEBENCH_INFERENCE_PROXY_URL", "").rstrip("/")
    payload = json.dumps({"rollout_id": rollout_id}).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/v1/rollouts/open",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        json.loads(response.read().decode("utf-8"))


def _close_proxy_rollout(rollout_id: str) -> dict[str, Any]:
    base = os.environ.get("GAMEBENCH_INFERENCE_PROXY_URL", "").rstrip("/")
    payload = json.dumps({"rollout_id": rollout_id}).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/v1/rollouts/close",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body if isinstance(body, dict) else {}


def rollout_exotic_cybernetics_episode(
    *, policy_path: Path, seed: int, task_path: str = "tasks/policy_dev_template.json", max_steps: int = 80, include_trace: bool = False,
) -> dict[str, Any]:
    rollout_id = f"tictactoe_mp-ec-{uuid.uuid4().hex[:12]}"
    sha = policy_sha256(policy_path)
    _open_proxy_rollout(rollout_id)
    steer = SteerSession(
        rollout_id=rollout_id,
        proxy_base=os.environ["GAMEBENCH_INFERENCE_PROXY_URL"],
        policy_sha256=sha,
    )
    SteerSession.bind(steer)
    try:
        from run_hillclimb import rollout_candidate
        
        suite_path = "defaults/exotic_cybernetics/eval_dev_v10.json"
        suite = json.loads((TASK_ROOT / suite_path).read_text(encoding="utf-8"))
        candidate_fn = load_env_cybernetics_policy(policy_path, steer_session=steer)
        report = rollout_candidate(
            candidate_fn=candidate_fn,
            seed=seed,
            opponent_policy_id=str(suite.get("opponent_policy_id", "block_win_center_v1")),
            max_plies=int(suite.get("max_plies", max_steps)),
        )
        episode = {
            "reward_info": {
                "outcome_reward": float(report.get("reward", 0.0)),
                "details": report,
            }
        }
    finally:
        SteerSession.unbind()
    cybernetics = _close_proxy_rollout(rollout_id)
    return attach_cybernetics(episode, cybernetics)
