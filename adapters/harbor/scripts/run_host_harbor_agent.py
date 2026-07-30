#!/usr/bin/env python3
"""Run host-side Pi or Cursor agents against a prepared GameBench Harbor workspace.

Hard-fails when the agent binary or auth is missing (no silent Codex fallback).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _which(name: str) -> str | None:
    path = shutil.which(name)
    if path:
        return path
    local = Path.home() / ".local" / "bin" / name
    if local.is_file():
        return str(local)
    return None


def cursor_model_arg(model: str, effort: str) -> str:
    model = (model or "").strip()
    effort = (effort or "").strip().lower()
    if "/" in model:
        model = model.split("/", 1)[-1]
    if "[" in model:
        return model
    suffixes = ("-none", "-low", "-medium", "-high", "-xhigh", "-max")
    if model.endswith(suffixes) or model.endswith("-fast"):
        return model
    if effort and effort != "none":
        return f"{model}-{effort}"
    return model


def host_cursor_logged_in(bin_path: str) -> bool:
    try:
        proc = subprocess.run(
            [bin_path, "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    out = (proc.stdout or "") + (proc.stderr or "")
    return "Logged in" in out and "Not logged in" not in out


def resolve_cursor_api_key() -> str | None:
    raw = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if raw:
        return raw
    for path in (
        Path.home() / "Documents" / "GitHub" / "synth-ai" / ".env",
        Path.home() / ".cursor" / ".env",
    ):
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("CURSOR_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
        except OSError:
            continue
    return None


def _pi_auth_has_usable_credentials(auth_path: Path) -> bool:
    """True when auth.json has at least one non-empty provider credential."""
    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False
    if not isinstance(payload, dict) or not payload:
        return False
    for value in payload.values():
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def stage_pi_home(out_dir: Path) -> Path:
    staged = out_dir / "pi_home"
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir(parents=True)

    host_dir = Path.home() / ".pi" / "agent"
    host_auth = host_dir / "auth.json"
    # Empty `{}` auth.json is common after a half-finished /login and must NOT
    # short-circuit the Codex OAuth bridge — that is what left panel pi lanes
    # with "No API key found for openai-codex".
    if host_auth.is_file() and _pi_auth_has_usable_credentials(host_auth):
        shutil.copyfile(host_auth, staged / "auth.json")
        for name in ("models.json", "settings.json"):
            src = host_dir / name
            if src.is_file():
                shutil.copyfile(src, staged / name)
        return staged

    codex_auth_path = Path.home() / ".codex" / "auth.json"
    if not codex_auth_path.is_file():
        _die(
            "Pi needs ~/.pi/agent/auth.json (pi /login) or ~/.codex/auth.json "
            "to bridge openai-codex OAuth"
        )
    codex = json.loads(codex_auth_path.read_text(encoding="utf-8"))
    tokens = dict(codex.get("tokens") or {})
    access = tokens.get("access_token")
    refresh = tokens.get("refresh_token")
    account_id = tokens.get("account_id")
    if not isinstance(access, str) or not access:
        _die("Codex auth.json missing access_token for Pi bridge")
    if not isinstance(refresh, str) or not refresh:
        _die("Codex auth.json missing refresh_token for Pi bridge")

    expires_ms = int(time.time() * 1000) + 3_600_000
    try:
        payload_b64 = access.split(".")[1]
        pad = "=" * ((4 - len(payload_b64) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
        if isinstance(payload.get("exp"), (int, float)):
            expires_ms = int(float(payload["exp"]) * 1000)
        if not account_id:
            claim = payload.get("https://api.openai.com/auth") or {}
            if isinstance(claim, dict) and claim.get("chatgpt_account_id"):
                account_id = claim["chatgpt_account_id"]
    except (IndexError, ValueError, json.JSONDecodeError, TypeError):
        pass

    cred: dict[str, Any] = {
        "type": "oauth",
        "access": access,
        "refresh": refresh,
        "expires": expires_ms,
    }
    if isinstance(account_id, str) and account_id:
        cred["accountId"] = account_id
    auth_path = staged / "auth.json"
    auth_path.write_text(
        json.dumps({"openai-codex": cred}, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(auth_path, 0o600)
    # Prefer host settings/models when present even if auth was empty.
    for name in ("models.json", "settings.json"):
        src = host_dir / name
        if src.is_file():
            shutil.copyfile(src, staged / name)
    return staged


def load_instruction(workspace: Path, instruction_path: Path | None) -> str:
    if instruction_path is not None and instruction_path.is_file():
        return instruction_path.read_text(encoding="utf-8")
    agents = workspace / "AGENTS.md"
    if agents.is_file():
        return agents.read_text(encoding="utf-8")
    _die(f"missing instruction at {instruction_path} and no AGENTS.md in {workspace}")


def run_pi(
    *,
    workspace: Path,
    instruction: str,
    model: str,
    effort: str,
    out_dir: Path,
    timeout_sec: int,
    provider: str,
) -> int:
    pi_bin = _which("pi")
    if not pi_bin:
        _die("pi not found on PATH (install Pi coding agent, or use codex/cursor)")

    pi_home = stage_pi_home(out_dir)
    agent_dir = out_dir / "logs" / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)

    if "/" in model:
        provider_resolved = model.split("/", 1)[0]
        model_resolved = model.split("/", 1)[1]
    else:
        provider_resolved = provider
        model_resolved = model
        if model_resolved.startswith("openai/"):
            model_resolved = model_resolved.split("/", 1)[1]

    (agent_dir / "pi_mode.txt").write_text(
        f"host pi provider={provider_resolved} model={model_resolved} "
        f"thinking={effort} dir={pi_home}\n",
        encoding="utf-8",
    )
    print(
        f"Running host pi provider={provider_resolved} model={model_resolved} "
        f"thinking={effort}",
        flush=True,
    )

    env = os.environ.copy()
    env["PI_CODING_AGENT_DIR"] = str(pi_home)
    # Pi >=0.73 takes the user prompt as a positional message, not `-a`
    # (that flag was removed; current CLI errors with "Unknown option: -a").
    cmd = [
        pi_bin,
        "--print",
        "--mode",
        "json",
        "--no-session",
        "--provider",
        provider_resolved,
        "--model",
        model_resolved,
        "--thinking",
        effort,
        instruction,
    ]
    stdout_path = agent_dir / "pi.stdout.jsonl"
    stderr_path = agent_dir / "pi.stderr.txt"
    t0 = time.time()
    with stdout_path.open("w", encoding="utf-8") as out_fh, stderr_path.open(
        "w", encoding="utf-8"
    ) as err_fh:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workspace),
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            text=True,
            env=env,
        )
        try:
            rc = proc.wait(timeout=max(1, timeout_sec))
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
            rc = 124
            print(f"host pi timeout after {timeout_sec}s", file=sys.stderr)
    print(f"host pi exit={rc} ({time.time() - t0:.0f}s)", flush=True)
    return int(rc)


def run_cursor(
    *,
    workspace: Path,
    instruction: str,
    model: str,
    effort: str,
    out_dir: Path,
    timeout_sec: int,
) -> int:
    bin_path = _which("cursor-agent")
    if not bin_path:
        _die("cursor-agent not found on PATH")

    api_key = resolve_cursor_api_key()
    if not api_key and not host_cursor_logged_in(bin_path):
        _die(
            "cursor mode needs CURSOR_API_KEY or a logged-in host cursor-agent "
            "(`cursor-agent login`)"
        )

    agent_dir = out_dir / "logs" / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    cursor_model = cursor_model_arg(model, effort)
    (agent_dir / "cursor_mode.txt").write_text(
        f"host cursor-agent model={cursor_model} effort={effort}\n",
        encoding="utf-8",
    )
    print(f"Running host cursor-agent model={cursor_model}", flush=True)

    env = os.environ.copy()
    if api_key:
        env["CURSOR_API_KEY"] = api_key

    cmd = [
        bin_path,
        "--print",
        "--force",
        "--trust",
        "--output-format",
        "stream-json",
        "--model",
        cursor_model,
        "--workspace",
        str(workspace),
        instruction,
    ]
    stdout_path = agent_dir / "cursor.stdout.jsonl"
    stderr_path = agent_dir / "cursor.stderr.txt"
    t0 = time.time()
    with stdout_path.open("w", encoding="utf-8") as out_fh, stderr_path.open(
        "w", encoding="utf-8"
    ) as err_fh:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workspace),
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            text=True,
            env=env,
        )
        try:
            rc = proc.wait(timeout=max(1, timeout_sec))
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
            rc = 124
            print(f"host cursor-agent timeout after {timeout_sec}s", file=sys.stderr)
    print(f"host cursor-agent exit={rc} ({time.time() - t0:.0f}s)", flush=True)
    return int(rc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=("pi", "cursor"), required=True)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--instruction", type=Path, default=None)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--effort", default="high")
    parser.add_argument("--timeout-sec", type=int, default=3600)
    parser.add_argument("--pi-provider", default="openai-codex")
    args = parser.parse_args(argv)

    workspace = args.workspace.resolve()
    out_dir = args.out_dir.resolve()
    if not workspace.is_dir():
        _die(f"workspace missing: {workspace}")
    out_dir.mkdir(parents=True, exist_ok=True)

    instruction = load_instruction(workspace, args.instruction)
    if args.agent == "pi":
        return run_pi(
            workspace=workspace,
            instruction=instruction,
            model=str(args.model),
            effort=str(args.effort),
            out_dir=out_dir,
            timeout_sec=int(args.timeout_sec),
            provider=str(args.pi_provider),
        )
    return run_cursor(
        workspace=workspace,
        instruction=instruction,
        model=str(args.model),
        effort=str(args.effort),
        out_dir=out_dir,
        timeout_sec=int(args.timeout_sec),
    )


if __name__ == "__main__":
    raise SystemExit(main())
