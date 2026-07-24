#!/usr/bin/env python3
"""Resolve GameBench eval family metadata for Harbor adapters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import tomllib

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "eval_registry.toml"


def load_registry() -> dict[str, Any]:
    return tomllib.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def normalize_family(name: str) -> str:
    key = str(name).strip().lower().replace("-", "_")
    aliases = {"code_policy": "code_policy_opt", "code_policy_opt": "code_policy_opt"}
    resolved = aliases.get(key)
    if not resolved:
        raise SystemExit(f"unknown eval family: {name}")
    return resolved


def task_entry(registry: dict[str, Any], task_id: str) -> dict[str, Any]:
    for row in registry.get("task", []):
        if row.get("id") == task_id:
            return row
    raise SystemExit(f"unknown task_id: {task_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    listing = sub.add_parser("list-tasks")
    listing.add_argument("--json", action="store_true")
    bundle = sub.add_parser("harbor-bundle")
    bundle.add_argument("family")
    bundle.add_argument("task_id")
    config = sub.add_parser("task-config")
    config.add_argument("task_id")
    config.add_argument("--json", action="store_true")
    args = parser.parse_args()
    registry = load_registry()

    if args.cmd == "list-tasks":
        rows = [row["id"] for row in registry.get("task", [])]
        print(json.dumps(rows, indent=2) if args.json else "\n".join(rows))
        return 0
    if args.cmd == "harbor-bundle":
        family = normalize_family(args.family)
        task_entry(registry, args.task_id)
        print(registry["families"][family]["harbor_bundle"])
        return 0
    if args.cmd == "task-config":
        payload = task_entry(registry, args.task_id)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for key, value in payload.items():
                if isinstance(value, list):
                    print(f"{key}={json.dumps(value)}")
                else:
                    print(f"{key}={value}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
