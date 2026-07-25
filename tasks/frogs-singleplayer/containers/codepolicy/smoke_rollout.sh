#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
python containers/codepolicy/run_policy_sweep.py --output-dir /tmp/frogs-codepolicy-smoke --seeds 1 --policy-path containers/codepolicy/heuristic_policy.py
