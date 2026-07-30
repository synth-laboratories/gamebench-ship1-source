"""Canonical fixture materialization for the Fog Duel Lite contract."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(TASK_DIR))
from gold_python.engine import FogDuelEnv, execute_tape
from gold_python.scenarios import load_all_scenarios


def fixture_documents() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    scenarios = load_all_scenarios()
    scenario_rows: list[dict[str, Any]] = []
    eventlogs: dict[str, Any] = {"schema_version": "gamebench.fog_duel_lite.fixture_eventlogs.v0", "scenarios": {}}
    states: dict[str, Any] = {"schema_version": "gamebench.fog_duel_lite.fixture_states.v0", "scenarios": {}}
    checkpoints: dict[str, Any] = {"schema_version": "gamebench.fog_duel_lite.fixture_checkpoints.v0", "scenarios": {}}
    for scenario in scenarios:
        scenario_id = scenario["id"]
        tape = copy.deepcopy(scenario["fixture_tape"])
        execution = execute_tape(scenario_id, tape)
        scenario_rows.append({"id": scenario_id, "seed": scenario["seed"], "tape": tape})
        eventlogs["scenarios"][scenario_id] = execution["events"]
        states["scenarios"][scenario_id] = execution["state"]
        checkpoint = execution["checkpoints"][-1]
        restored = FogDuelEnv()
        restored.restore(checkpoint)
        checkpoints["scenarios"][scenario_id] = {
            "checkpoint": checkpoint,
            "restored_state": restored.state_projection(),
            "restored_observation": restored.observe(),
        }
    return (
        {"schema_version": "gamebench.fog_duel_lite.fixture_scenarios.v0", "scenarios": scenario_rows},
        eventlogs,
        states,
        checkpoints,
    )
