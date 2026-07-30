#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
PYTHONPATH=.:gold_python:shared python -c 'import asyncio, json; from containers.react.rollout_policy import EnvRolloutConfig, RolloutPolicy; result = asyncio.run(RolloutPolicy.from_policy_config({"policy_id":"solver_v1"}).run(None, EnvRolloutConfig(seed=1), "smoke-react-1")); print(json.dumps({"outcome": result["reward_info"]["details"]["outcome"], "steps": result["reward_info"]["details"]["steps"]}, sort_keys=True))'
