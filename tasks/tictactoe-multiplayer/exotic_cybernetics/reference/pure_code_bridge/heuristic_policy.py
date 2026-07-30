"""Pure-code exotic cybernetics reference (0 LLM tokens)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_TASK_ROOT = Path(__file__).resolve().parents[3]
_POLICIES = _TASK_ROOT / "policies"
if str(_TASK_ROOT) not in sys.path:
    sys.path.insert(0, str(_TASK_ROOT))
if str(_POLICIES) not in sys.path:
    sys.path.insert(0, str(_POLICIES))

from containers.codepolicy.heuristic_policy import choose_action as _base_choose_action  # noqa: E402


def choose_action(public: dict[str, Any], agent_id: str, seed: int, ply: int) -> dict[str, Any]:
    return _base_choose_action(public, agent_id, seed, ply)
