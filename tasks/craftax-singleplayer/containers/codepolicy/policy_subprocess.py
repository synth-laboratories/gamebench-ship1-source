"""Isolate untrusted Craftax policy code behind observation/action JSONL IPC."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any


_POLICY_ENV_ALLOWLIST = frozenset(
    {
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONHOME",
        "PYTHONPATH",
        "SYSTEMROOT",
        "TMPDIR",
        "VIRTUAL_ENV",
    }
)


def _load_policy(policy_path: Path) -> Any:
    resolved = policy_path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"policy file not found: {resolved}")
    if str(resolved.parent) not in sys.path:
        sys.path.insert(0, str(resolved.parent))
    module_name = f"isolated_craftax_policy_{os.getpid()}"
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load policy module: {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    with contextlib.redirect_stdout(sys.stderr):
        spec.loader.exec_module(module)
    candidate = getattr(module, "choose_actions", None)
    if not callable(candidate):
        raise ValueError(f"policy module {resolved} missing callable choose_actions")
    return candidate


def _serve(policy_path: Path) -> int:
    protocol_out = sys.stdout
    candidate = _load_policy(policy_path)
    for line in sys.stdin:
        request = json.loads(line)
        request_id = request.get("id")
        if request.get("op") == "close":
            protocol_out.write(json.dumps({"id": request_id, "ok": True}) + "\n")
            protocol_out.flush()
            return 0
        if request.get("op") != "choose_actions":
            raise ValueError("unsupported isolated policy operation")
        with contextlib.redirect_stdout(sys.stderr):
            decision = candidate(
                observation_text=str(request.get("observation_text") or ""),
                session=dict(request.get("session") or {}),
                valid_actions=list(request.get("valid_actions") or []),
                engine=None,
                seed=None,
                ply=int(request.get("ply") or 0),
                readout=dict(request.get("readout") or {}),
            )
        if not isinstance(decision, dict) or not isinstance(
            decision.get("actions"), list
        ):
            raise ValueError("choose_actions must return {'actions': [...]}")
        response = {
            "id": request_id,
            "ok": True,
            "decision": {
                "actions": [str(action) for action in decision["actions"]],
                "policy_reason": str(decision.get("policy_reason") or ""),
            },
        }
        protocol_out.write(json.dumps(response, separators=(",", ":")) + "\n")
        protocol_out.flush()
    return 0


class IsolatedPolicyProcess:
    """Callable policy proxy; the child never receives suite paths or seed IDs."""

    def __init__(self, policy_path: Path) -> None:
        self._home = tempfile.TemporaryDirectory(prefix="craftax-policy-home-")
        env = {
            key: value
            for key, value in os.environ.items()
            if key in _POLICY_ENV_ALLOWLIST
        }
        env["HOME"] = self._home.name
        self._proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--serve", str(policy_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            cwd=policy_path.expanduser().resolve().parent,
            env=env,
            close_fds=True,
        )
        if self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("isolated policy process pipes unavailable")
        self._stdin = self._proc.stdin
        self._stdout = self._proc.stdout
        self._lock = threading.Lock()
        self._request_id = 0

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        session = dict(kwargs.get("session") or {})
        observation_text = str(kwargs.get("observation_text") or "")
        valid_actions = [str(action) for action in kwargs.get("valid_actions") or []]
        request = {
            "op": "choose_actions",
            "observation_text": observation_text,
            "session": {
                "lane": str(session.get("lane") or "rust"),
                "ply": int(session.get("ply") or 0),
            },
            "valid_actions": valid_actions,
            "ply": int(kwargs.get("ply") or 0),
            "readout": {
                "observation_text": observation_text,
                "valid_actions": valid_actions,
            },
        }
        with self._lock:
            if self._proc.poll() is not None:
                raise RuntimeError("isolated policy process exited unexpectedly")
            self._request_id += 1
            request_id = self._request_id
            request["id"] = request_id
            self._stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            self._stdin.flush()
            response_line = self._stdout.readline()
        if not response_line:
            raise RuntimeError("isolated policy process returned no response")
        response = json.loads(response_line)
        if (
            not isinstance(response, dict)
            or response.get("id") != request_id
            or response.get("ok") is not True
            or not isinstance(response.get("decision"), dict)
        ):
            raise RuntimeError("isolated policy process returned an invalid response")
        return dict(response["decision"])

    def close(self) -> None:
        with self._lock:
            if self._proc.poll() is None:
                try:
                    self._request_id += 1
                    self._stdin.write(
                        json.dumps(
                            {"id": self._request_id, "op": "close"},
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                    self._stdin.flush()
                    self._proc.wait(timeout=2)
                except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                    self._proc.kill()
                    self._proc.wait(timeout=2)
            self._home.cleanup()


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--serve":
        raise SystemExit("usage: policy_subprocess.py --serve <policy.py>")
    return _serve(Path(sys.argv[2]))


if __name__ == "__main__":
    raise SystemExit(main())
