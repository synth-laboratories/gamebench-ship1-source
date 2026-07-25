"""Monty policy loader — per-agent policies for joint-step MARL rollouts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

PolicyFn = Callable[[dict[str, Any], int, int], dict[str, Any]]

POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"


def _ensure_policies_path() -> None:
    policies_path = str(POLICIES_DIR)
    if policies_path not in sys.path:
        sys.path.insert(0, policies_path)


def _registry_place_action(policy_id: str, state: dict[str, Any], seed: int, ply: int) -> dict[str, Any]:
    _ensure_policies_path()
    from registry import choose_action as registry_fn

    legacy = registry_fn(policy_id, state, seed=seed, ply=ply)
    return {"kind": "place", "position": int(legacy["position"])}


def _load_module_policy(module_name: str, entry: str = "choose_action") -> PolicyFn:
    module_path = POLICIES_DIR / f"{module_name}.py"
    if not module_path.is_file():
        raise ValueError(f"policy module not found: {module_path}")
    _ensure_policies_path()
    spec = importlib.util.spec_from_file_location(f"ttt_mp_policy_{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load policy module: {module_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, entry, None)
    if fn is None:
        raise ValueError(f"policy module {module_name} missing entry {entry}")
    return fn


def resolve_policy(spec: dict[str, Any], agent_id: str) -> PolicyFn:
    kind = spec.get("kind", "registry")
    if kind == "registry":
        policy_id = str(spec["policy_id"])

        def registry_wrapper(public: dict[str, Any], seed: int, ply: int) -> dict[str, Any]:
            state = {
                "board": list(public["board"]),
                "turn": public["turn"],
                "winner": public.get("winner"),
                "agent_id": agent_id,
                "current_agent": public.get("current_agent"),
            }
            return _registry_place_action(policy_id, state, seed=seed, ply=ply)

        return registry_wrapper
    if kind == "monty_python":
        module_fn = _load_module_policy(str(spec["module"]), str(spec.get("entry", "choose_action")))

        def module_wrapper(public: dict[str, Any], seed: int, ply: int) -> dict[str, Any]:
            legacy = module_fn(public, seed, ply)
            if legacy.get("kind") == "place":
                return legacy
            return {"kind": "place", "position": int(legacy["position"])}

        return module_wrapper
    raise ValueError(f"unknown policy kind: {kind}")


def public_dict_from_engine(public: Any) -> dict[str, Any]:
    return public.to_dict()
