"""Persistent Craftax Rust engine REPL (stdin/stdout JSONL) for fast policy sweeps."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any


TASK_ROOT = Path(__file__).resolve().parents[2]
RUST_DIR = TASK_ROOT / "gold_rust"
REPL_BINARY = RUST_DIR / "target" / "release" / "craftax_repl"

_BUILD_LOCK = threading.Lock()
_REQUEST_ID = 0
_REQUEST_LOCK = threading.Lock()
_READOUT_MODES = frozenset({"full", "policy"})


def ensure_rust_repl_binary() -> Path:
    if _binary_is_current(REPL_BINARY):
        return REPL_BINARY
    with _BUILD_LOCK:
        if _binary_is_current(REPL_BINARY):
            return REPL_BINARY
        command = [
            "cargo",
            "build",
            "--release",
            "--quiet",
            "--manifest-path",
            str(RUST_DIR / "Cargo.toml"),
            "--bin",
            "craftax_repl",
        ]
        subprocess.run(command, check=True)
        if not REPL_BINARY.is_file():
            raise RuntimeError(f"Rust REPL binary missing after build: {REPL_BINARY}")
        return REPL_BINARY


def _binary_is_current(binary: Path) -> bool:
    if not binary.is_file():
        return False
    source_paths = [RUST_DIR / "Cargo.toml", *list((RUST_DIR / "src").rglob("*.rs"))]
    source_mtime = max(path.stat().st_mtime for path in source_paths)
    return binary.stat().st_mtime >= source_mtime


def _next_request_id() -> int:
    global _REQUEST_ID
    with _REQUEST_LOCK:
        _REQUEST_ID += 1
        return _REQUEST_ID


class RustReplSession:
    """One long-lived craftax_repl subprocess per worker thread/process."""

    def __init__(self, *, binary_path: Path | None = None) -> None:
        binary = binary_path or ensure_rust_repl_binary()
        self._proc = subprocess.Popen(
            [str(binary)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=os.environ.copy(),
        )
        if self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("failed to open craftax_repl pipes")
        self._stdin = self._proc.stdin
        self._stdout = self._proc.stdout
        self._io_lock = threading.Lock()
        ping = self._request({"op": "ping"})
        if not ping.get("ok"):
            raise RuntimeError(f"craftax_repl ping failed: {ping}")

    def close(self) -> None:
        with self._io_lock:
            if self._proc.poll() is not None:
                return
            try:
                self._write_unlocked({"id": _next_request_id(), "op": "close"})
                _ = self._read_unlocked()
            except OSError:
                pass
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    self._proc.kill()
                except OSError:
                    pass

    def reset(
        self, *, task: dict[str, Any], seed: int, readout_mode: str = "full"
    ) -> dict[str, Any]:
        response = self._request(
            {
                "op": "reset",
                "task": task,
                "seed": seed,
                "readout_mode": self._readout_mode(readout_mode),
            }
        )
        if not response.get("ok"):
            raise RuntimeError(
                f"craftax_repl reset failed: {response.get('error', response)}"
            )
        return response

    def step(self, action: str, *, readout_mode: str = "full") -> dict[str, Any]:
        response = self._request(
            {
                "op": "step",
                "action": action,
                "readout_mode": self._readout_mode(readout_mode),
            }
        )
        if not response.get("ok"):
            raise RuntimeError(
                f"craftax_repl step failed: {response.get('error', response)}"
            )
        return response

    def steps(
        self, actions: list[str], *, readout_mode: str = "full"
    ) -> dict[str, Any]:
        response = self._request(
            {
                "op": "steps",
                "actions": actions,
                "readout_mode": self._readout_mode(readout_mode),
            }
        )
        if not response.get("ok"):
            raise RuntimeError(
                f"craftax_repl steps failed: {response.get('error', response)}"
            )
        return response

    def readout(self, *, readout_mode: str = "full") -> dict[str, Any]:
        response = self._request(
            {"op": "readout", "readout_mode": self._readout_mode(readout_mode)}
        )
        if not response.get("ok"):
            raise RuntimeError(
                f"craftax_repl readout failed: {response.get('error', response)}"
            )
        return response

    def _readout_mode(self, value: str) -> str:
        if value not in _READOUT_MODES:
            raise ValueError(f"unsupported craftax_repl readout_mode: {value}")
        return value

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._io_lock:
            request = {"id": _next_request_id(), **payload}
            self._write_unlocked(request)
            return self._read_unlocked()

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self._stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self._stdin.flush()

    def _read_unlocked(self) -> dict[str, Any]:
        while True:
            line = self._stdout.readline()
            if not line:
                code = self._proc.poll()
                raise RuntimeError(f"craftax_repl exited unexpectedly (code={code})")
            line = line.strip()
            if not line:
                continue
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                return parsed
            raise RuntimeError(f"craftax_repl returned non-object: {parsed!r}")

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
