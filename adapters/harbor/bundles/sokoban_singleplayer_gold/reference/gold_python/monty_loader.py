"""Load Monty reward modules for Sokoban gold."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable


MONTY_DIR = Path(__file__).resolve().parent / "monty"


def load_monty_scorer(spec: dict[str, Any] | None) -> Callable[..., float] | None:
    if not spec:
        return None
    if spec.get("kind") not in {None, "monty_python"}:
        return None
    module_name = str(spec.get("module") or "")
    entry = str(spec.get("entry") or "score_transition")
    module_path = MONTY_DIR / f"{module_name}.py"
    if not module_path.exists():
        raise FileNotFoundError(f"missing monty module: {module_path}")
    spec_obj = importlib.util.spec_from_file_location(f"sokoban_monty_{module_name}", module_path)
    if spec_obj is None or spec_obj.loader is None:
        raise ValueError(f"cannot import monty module: {module_path}")
    module = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(module)
    fn = getattr(module, entry, None)
    if not callable(fn):
        raise ValueError(f"monty module missing entry {entry}: {module_path}")
    return fn
