#!/usr/bin/env bash
set -euo pipefail

cd /task/reference/dungeongrid-multiplayer
python3 scripts/run_scenario_suite.py
python3 scripts/compare_gold_lanes.py
python3 scripts/run_rust_mechanics_probe.py
python3 scripts/compare_mechanics_probes.py
