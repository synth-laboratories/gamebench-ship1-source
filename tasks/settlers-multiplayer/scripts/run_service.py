#!/usr/bin/env python3
"""Minimal JSON-lines service for the owned Python gold lane.

Input commands are reset, step, checkpoint, and restore.  Output is one JSON
document per input line, making the service usable from a headless runner.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

TASK_DIR = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(TASK_DIR))
from gold_python.engine import SettlersEnv

def main() -> None:
    env = SettlersEnv()
    for line in sys.stdin:
        command = json.loads(line)
        kind = command.get("kind")
        if kind == "reset":
            observations, info = env.reset(int(command.get("seed", 0))); result = {"observations": observations, "info": info}
        elif kind == "step":
            observations, rewards, dones, info = env.step(command.get("action")); result = {"observations": observations, "rewards": rewards, "dones": dones, "info": info}
        elif kind == "checkpoint": result = env.checkpoint()
        elif kind == "restore": result = {"observations": env.restore(command["checkpoint"])}
        else: result = {"error": "unknown command", "kind": kind}
        print(json.dumps(result, sort_keys=True), flush=True)

if __name__ == "__main__": main()
