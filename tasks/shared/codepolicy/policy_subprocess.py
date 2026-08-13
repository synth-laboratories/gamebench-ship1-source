"""Isolate untrusted GameBench policy code behind observation/action JSONL IPC."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any


_POLICY_ENV_ALLOWLIST: frozenset[str] = frozenset()
_MAX_IPC_LINE_CHARS = 2 * 1024 * 1024
_LINUX_SANDBOX_UID = 65534
_LINUX_SANDBOX_GID = 65534
# Prefer OrbStack when present; fall back to the active Docker context.
_DARWIN_DOCKER_CONTEXT_PREFERRED = "orbstack"
# Pin per-arch digests for python:3.13.14-slim-bookworm. Apple Silicon must use
# linux/arm64 — linux/amd64 goes through Rosetta and fails with
# `rosetta error: mmap_anonymous_rw` under OrbStack (rc 133).
_DARWIN_POLICY_IMAGES: dict[str, tuple[str, str]] = {
    "arm64": (
        "linux/arm64",
        "python:3.13-slim-bookworm@"
        "sha256:56249d7a2f93306106f6d8bcdf6423afb73c1b747d874febcc778beee25cb8bb",
    ),
    "aarch64": (
        "linux/arm64",
        "python:3.13-slim-bookworm@"
        "sha256:56249d7a2f93306106f6d8bcdf6423afb73c1b747d874febcc778beee25cb8bb",
    ),
    "x86_64": (
        "linux/amd64",
        "python:3.13-slim-bookworm@"
        "sha256:dd86541a59b252667f4c12f8b2ee17216de37dd65ac773bf097bef996fa78860",
    ),
    "amd64": (
        "linux/amd64",
        "python:3.13-slim-bookworm@"
        "sha256:dd86541a59b252667f4c12f8b2ee17216de37dd65ac773bf097bef996fa78860",
    ),
}
_POLICY_LABEL = "synth.factorybench.policy"
_RUNNER_PID_LABEL = "synth.factorybench.runner_pid"
_WORKER_PID_LABEL = "synth.factorybench.worker_pid"
POLICY_PROCESS_CANDIDATE_FAILURE_EXIT_CODE = 40
_CANDIDATE_FAILURE_CODE = "candidate_policy_failure"


def _darwin_host_machine() -> str:
    return os.uname().machine


def _darwin_policy_platform_and_image() -> tuple[str, str]:
    machine = _darwin_host_machine()
    try:
        return _DARWIN_POLICY_IMAGES[machine]
    except KeyError as exc:
        raise RuntimeError(
            f"FactoryBench Darwin policy sandbox unsupported on machine {machine!r}"
        ) from exc


def _real_user_home() -> Path:
    """Home directory of the real user, ignoring Harbor HOME remaps."""
    try:
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except Exception:
        return Path.home()


def _resolve_darwin_docker_context(*, env: dict[str, str]) -> str:
    explicit = (
        env.get("DOCKER_CONTEXT")
        or os.environ.get("FACTORYBENCH_DOCKER_CONTEXT")
        or ""
    ).strip()
    if explicit:
        return explicit
    docker = shutil.which("docker")
    if not docker:
        return _DARWIN_DOCKER_CONTEXT_PREFERRED
    try:
        listed = subprocess.run(
            [docker, "context", "ls", "--format", "{{.Name}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _DARWIN_DOCKER_CONTEXT_PREFERRED
    names = {line.strip() for line in listed.stdout.splitlines() if line.strip()}
    if _DARWIN_DOCKER_CONTEXT_PREFERRED in names:
        return _DARWIN_DOCKER_CONTEXT_PREFERRED
    if "default" in names:
        return "default"
    return next(iter(names), _DARWIN_DOCKER_CONTEXT_PREFERRED)


class CandidatePolicyFailure(RuntimeError):
    """Stable trusted classification for candidate-owned policy failures."""

    def __init__(self, _code: str = _CANDIDATE_FAILURE_CODE) -> None:
        super().__init__(_CANDIDATE_FAILURE_CODE)


def _candidate_environment(*, home: str, path: str) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key in _POLICY_ENV_ALLOWLIST
    }
    env.update(
        {
            "HOME": home,
            "PATH": path,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "TMPDIR": "/tmp",
        }
    )
    return env


def _linux_bwrap_userns_available(bwrap: str) -> bool:
    """True when non-privileged bubblewrap can create user namespaces.

    Nested Dock/SMR runtimes often ship ``bwrap`` but disable unprivileged
    userns; probing avoids a hard fail mid-episode.
    """
    try:
        probe = subprocess.run(
            [
                bwrap,
                "--unshare-all",
                "--die-with-parent",
                "--ro-bind",
                "/usr",
                "/usr",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "/usr/bin/true",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0

def _linux_process_fallback_command(
    *, root: Path, executable: Path
) -> tuple[list[str], dict[str, str], str]:
    """IPC process isolation without OS namespaces (Dock/SMR nested runtimes)."""
    base_prefix = Path(sys.base_prefix).resolve()
    command = [
        str(executable),
        str(root / "policy_subprocess.py"),
        "--serve",
        str(root / "policy.py"),
    ]
    env = _candidate_environment(
        home=str(root / "empty"),
        path=f"{base_prefix / 'bin'}:/usr/bin:/bin",
    )
    env["PWD"] = str(root)
    return command, env, "process_fallback"


def _linux_sandbox_command(
    *, root: Path, executable: Path
) -> tuple[list[str], dict[str, str], str]:
    bwrap = shutil.which("bwrap")
    if not bwrap or not _linux_bwrap_userns_available(bwrap):
        return _linux_process_fallback_command(root=root, executable=executable)
    command = [
        bwrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--uid",
        str(_LINUX_SANDBOX_UID),
        "--gid",
        str(_LINUX_SANDBOX_GID),
        "--ro-bind",
        "/usr",
        "/usr",
    ]
    for system_path in (Path("/bin"), Path("/lib"), Path("/lib64")):
        if system_path.is_symlink():
            command.extend(
                ("--symlink", os.readlink(system_path), str(system_path))
            )
        elif system_path.exists():
            command.extend(("--ro-bind", str(system_path), str(system_path)))
    base_prefix = Path(sys.base_prefix).resolve()
    if not base_prefix.is_relative_to(Path("/usr")):
        command.extend(("--ro-bind", str(base_prefix), str(base_prefix)))
    command.extend(
        (
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--ro-bind",
            str(root / "empty"),
            "/dev/shm",
            "--ro-bind",
            str(root / "empty"),
            "/tmp",
            "--dir",
            "/home",
            "--ro-bind",
            str(root / "empty"),
            "/home/candidate",
            "--ro-bind",
            str(root),
            "/workspace",
            "--chdir",
            "/workspace",
            str(executable),
            "/workspace/policy_subprocess.py",
            "--serve",
            "/workspace/policy.py",
        )
    )
    return (
        command,
        _candidate_environment(
            home="/home/candidate",
            path=f"{base_prefix / 'bin'}:/usr/bin:/bin",
        ),
        "bubblewrap",
    )


def _docker_client_environment() -> dict[str, str]:
    keys = {
        "DOCKER_CONFIG",
        "DOCKER_CONTEXT",
        "DOCKER_HOST",
        "HOME",
        "PATH",
        "XDG_CONFIG_HOME",
    }
    env = {key: value for key, value in os.environ.items() if key in keys}
    # Harbor remaps HOME into the lane workspace; Docker then loses the user's
    # context metadata (orbstack). Always point DOCKER_CONFIG at the real home
    # unless the caller already set an explicit config dir.
    if "DOCKER_CONFIG" not in env:
        real_config = _real_user_home() / ".docker"
        if real_config.is_dir():
            env["DOCKER_CONFIG"] = str(real_config)
    # Keep HOME coherent with DOCKER_CONFIG for clients that key off HOME.
    if env.get("DOCKER_CONFIG"):
        env["HOME"] = str(_real_user_home())
    return env


def _darwin_sandbox_command(
    *, root: Path, container_name: str
) -> tuple[list[str], dict[str, str]]:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError(
            "FactoryBench candidate isolation requires Docker on Darwin"
        )
    empty = root / "empty"
    readonly_mounts = (
        (root, Path("/workspace")),
        (empty, Path("/tmp")),
        (empty, Path("/home/candidate")),
        (empty, Path("/dev/shm")),
    )
    runner_pid = str(
        os.environ.get("FACTORYBENCH_POLICY_RUNNER_PID") or os.getppid()
    ).strip()
    if not runner_pid.isdigit():
        raise RuntimeError("FactoryBench policy runner pid must be numeric")
    env = _docker_client_environment()
    context = _resolve_darwin_docker_context(env=env)
    platform, image = _darwin_policy_platform_and_image()
    command = [
        docker,
        "--context",
        context,
        "run",
        "--rm",
        "--interactive",
        "--pull=never",
        "--name",
        container_name,
        "--label",
        f"{_POLICY_LABEL}=true",
        "--label",
        f"{_RUNNER_PID_LABEL}={runner_pid}",
        "--label",
        f"{_WORKER_PID_LABEL}={os.getpid()}",
        "--platform",
        platform,
        "--network",
        "none",
        "--read-only",
        "--memory",
        "512m",
        "--memory-swap",
        "512m",
        "--pids-limit",
        "1",
        "--cpus",
        "1",
        "--user",
        f"{_LINUX_SANDBOX_UID}:{_LINUX_SANDBOX_GID}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--ulimit",
        "fsize=1048576:1048576",
        "--ulimit",
        "nofile=64:64",
        "--log-driver",
        "none",
        "--workdir",
        "/workspace",
    ]
    for source, target in readonly_mounts:
        command.extend(
            (
                "--mount",
                f"type=bind,source={source},target={target},readonly",
            )
        )
    command.extend(
        (
            image,
            "/usr/bin/env",
            "-i",
            "HOME=/home/candidate",
            "PATH=/usr/local/bin:/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE=1",
            "PYTHONNOUSERSITE=1",
            "TMPDIR=/tmp",
            "/usr/local/bin/python3",
            "/workspace/policy_subprocess.py",
            "--serve",
            "/workspace/policy.py",
        )
    )
    return command, env


def cleanup_isolated_policy_containers(*, runner_pid: int, worker_pid: int) -> None:
    """Remove only a supervised episode's exactly labeled Darwin containers."""
    if sys.platform != "darwin":
        return
    docker = shutil.which("docker")
    if not docker:
        return
    env = _docker_client_environment()
    context = _resolve_darwin_docker_context(env=env)
    filters = [
        "--filter",
        f"label={_POLICY_LABEL}=true",
        "--filter",
        f"label={_RUNNER_PID_LABEL}={int(runner_pid)}",
        "--filter",
        f"label={_WORKER_PID_LABEL}={int(worker_pid)}",
    ]
    try:
        listed = subprocess.run(
            [
                docker,
                "--context",
                context,
                "ps",
                "--all",
                "--quiet",
                *filters,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
        )
        container_ids = [
            value.strip()
            for value in listed.stdout.splitlines()
            if value.strip()
            and 12 <= len(value.strip()) <= 64
            and all(char in "0123456789abcdef" for char in value.strip())
        ]
        if container_ids:
            subprocess.run(
                [
                    docker,
                    "--context",
                    context,
                    "rm",
                    "--force",
                    *container_ids,
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                env=env,
            )
    except subprocess.TimeoutExpired:
        return


def _sandbox_command(
    *, root: Path, container_name: str | None
) -> tuple[list[str], dict[str, str], str]:
    if sys.platform.startswith("linux"):
        executable = Path(
            str(getattr(sys, "_base_executable", "") or sys.executable)
        ).resolve()
        return _linux_sandbox_command(root=root, executable=executable)
    if sys.platform == "darwin":
        if not container_name:
            raise RuntimeError("FactoryBench Darwin sandbox requires a container name")
        command, env = _darwin_sandbox_command(root=root, container_name=container_name)
        return command, env, "docker"
    raise RuntimeError(
        f"FactoryBench candidate isolation unsupported on platform {sys.platform!r}"
    )


def _apply_candidate_resource_limits() -> None:
    """Bound damage inside the OS sandbox without weakening the parent grader."""
    if os.name != "posix":
        return
    import resource

    limits = (
        (resource.RLIMIT_FSIZE, 1024 * 1024),
        (resource.RLIMIT_NOFILE, 64),
    )
    if sys.platform.startswith("linux"):
        limits += (
            (resource.RLIMIT_AS, 512 * 1024 * 1024),
            (resource.RLIMIT_NPROC, 1),
        )
    for kind, ceiling in limits:
        _soft, hard = resource.getrlimit(kind)
        target = min(ceiling, hard) if hard != resource.RLIM_INFINITY else ceiling
        resource.setrlimit(kind, (target, target))


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
    with open(os.devnull, "w", encoding="utf-8") as candidate_output:
        with contextlib.redirect_stdout(candidate_output), contextlib.redirect_stderr(
            candidate_output
        ):
            spec.loader.exec_module(module)
    candidate = getattr(module, "choose_actions", None)
    if not callable(candidate):
        raise ValueError(f"policy module {resolved} missing callable choose_actions")
    return candidate


def _serve(policy_path: Path) -> int:
    _apply_candidate_resource_limits()
    protocol_out = sys.stdout
    try:
        candidate = _load_policy(policy_path)
    except BaseException:
        protocol_out.write(
            json.dumps(
                {
                    "op": "ready",
                    "ok": False,
                    "error_code": _CANDIDATE_FAILURE_CODE,
                },
                separators=(",", ":"),
            )
            + "\n"
        )
        protocol_out.flush()
        return POLICY_PROCESS_CANDIDATE_FAILURE_EXIT_CODE
    protocol_out.write(
        json.dumps({"op": "ready", "ok": True}, separators=(",", ":")) + "\n"
    )
    protocol_out.flush()
    for line in sys.stdin:
        if len(line) > _MAX_IPC_LINE_CHARS:
            raise ValueError("isolated policy request exceeds IPC limit")
        request = json.loads(line)
        request_id = request.get("id")
        if request.get("op") == "close":
            protocol_out.write(json.dumps({"id": request_id, "ok": True}) + "\n")
            protocol_out.flush()
            return 0
        if request.get("op") != "choose_actions":
            raise ValueError("unsupported isolated policy operation")
        try:
            with open(os.devnull, "w", encoding="utf-8") as candidate_output:
                with contextlib.redirect_stdout(
                    candidate_output
                ), contextlib.redirect_stderr(candidate_output):
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
                raise ValueError("candidate policy response is invalid")
            response = {
                "id": request_id,
                "ok": True,
                "decision": {
                    "actions": [str(action) for action in decision["actions"]],
                    "policy_reason": str(decision.get("policy_reason") or ""),
                },
            }
            encoded = json.dumps(response, separators=(",", ":"))
            if len(encoded) > _MAX_IPC_LINE_CHARS:
                raise ValueError("candidate policy response exceeds IPC limit")
        except BaseException:
            protocol_out.write(
                json.dumps(
                    {
                        "id": request_id,
                        "ok": False,
                        "error_code": _CANDIDATE_FAILURE_CODE,
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )
            protocol_out.flush()
            return POLICY_PROCESS_CANDIDATE_FAILURE_EXIT_CODE
        protocol_out.write(encoded + "\n")
        protocol_out.flush()
    return 0


class IsolatedPolicyProcess:
    """Callable policy proxy; the child never receives suite paths or seed IDs."""

    def __init__(self, policy_path: Path) -> None:
        source_path = policy_path.expanduser().resolve()
        if not source_path.is_file():
            raise CandidatePolicyFailure()
        sandbox_parent: str | None = None
        if sys.platform == "darwin":
            sandbox_parent_path = next(
                (
                    path.resolve()
                    for path in (Path("/private/var/tmp"), Path("/private/tmp"))
                    if path.is_dir()
                    and not path.resolve().is_relative_to(source_path.parent)
                ),
                None,
            )
            if sandbox_parent_path is None:
                raise RuntimeError(
                    "FactoryBench cannot place the Darwin policy sandbox outside "
                    "the protected source parent"
                )
            sandbox_parent = str(sandbox_parent_path)
        self._sandbox = tempfile.TemporaryDirectory(
            prefix="craftax-policy-sandbox-",
            dir=sandbox_parent,
        )
        sandbox_root = Path(self._sandbox.name)
        sandbox_root.chmod(0o755)
        policy_copy = sandbox_root / "policy.py"
        server_copy = sandbox_root / "policy_subprocess.py"
        empty = sandbox_root / "empty"
        empty.mkdir()
        empty.chmod(0o555)
        policy_copy.write_bytes(source_path.read_bytes())
        server_copy.write_bytes(Path(__file__).resolve().read_bytes())
        policy_copy.chmod(0o444)
        server_copy.chmod(0o444)
        self._container_name = (
            f"factorybench-policy-{uuid.uuid4().hex}"
            if sys.platform == "darwin"
            else None
        )
        command, env, sandbox_mode = _sandbox_command(
            root=sandbox_root,
            container_name=self._container_name,
        )
        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=sandbox_root,
            env=env,
            close_fds=True,
        )
        if self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("isolated policy process pipes unavailable")
        if self._proc.stderr is None:
            raise RuntimeError("isolated policy process diagnostic pipe unavailable")
        self._stdin = self._proc.stdin
        self._stdout = self._proc.stdout
        self._lock = threading.Lock()
        self._request_id = 0
        self._discarded_stderr_bytes = 0
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            name=f"craftax-policy-stderr-{self._proc.pid}",
            daemon=True,
        )
        self._stderr_thread.start()
        try:
            ready_line = self._stdout.readline(_MAX_IPC_LINE_CHARS + 1)
            if not ready_line:
                self._stderr_thread.join(timeout=0.25)
                returncode = self._proc.poll()
                if returncode == POLICY_PROCESS_CANDIDATE_FAILURE_EXIT_CODE:
                    raise CandidatePolicyFailure()
                raise RuntimeError(
                    f"isolated_policy_startup_failed:rc={returncode}"
                )
            if len(ready_line) > _MAX_IPC_LINE_CHARS or not ready_line.endswith("\n"):
                raise CandidatePolicyFailure()
            try:
                ready = json.loads(ready_line)
            except json.JSONDecodeError:
                raise CandidatePolicyFailure() from None
            if (
                not isinstance(ready, dict)
                or ready.get("op") != "ready"
                or ready.get("ok") not in {True, False}
            ):
                raise CandidatePolicyFailure()
            if ready.get("ok") is not True:
                raise CandidatePolicyFailure()
        except BaseException:
            try:
                self._terminate()
            finally:
                self._sandbox.cleanup()
            raise
        linux_bwrap = sandbox_mode == "bubblewrap"
        self.isolation_receipt = {
            "contract": (
                "os_sandbox_observation_action.v2"
                if sandbox_mode != "process_fallback"
                else "process_observation_action.v1"
            ),
            "platform": sys.platform,
            "sandbox": sandbox_mode,
            "network": (
                "unshared"
                if linux_bwrap
                else ("denied" if sandbox_mode == "docker" else "shared_with_evaluator")
            ),
            "filesystem": (
                "policy_only_read_only"
                if sandbox_mode != "process_fallback"
                else "process_cwd_policy_only"
            ),
            "policy_uid": _LINUX_SANDBOX_UID if linux_bwrap else os.getuid(),
            "suite_visible": False,
            "output_visible": False,
            "evaluator_visible": sandbox_mode == "process_fallback",
            "forking": "denied" if sandbox_mode != "process_fallback" else "inherited",
        }
        if sys.platform == "darwin":
            platform, image = _darwin_policy_platform_and_image()
            docker_env = _docker_client_environment()
            self.isolation_receipt.update(
                {
                    "container_context": _resolve_darwin_docker_context(env=docker_env),
                    "container_image": image,
                    "container_platform": platform,
                    "memory_limit_bytes": 512 * 1024 * 1024,
                    "pids_limit": 1,
                }
            )

    def _drain_stderr(self) -> None:
        assert self._proc.stderr is not None
        while True:
            chunk = self._proc.stderr.read(4096)
            if not chunk:
                return
            # Candidate code owns this channel, so its bytes must never cross
            # into a benchmark result, typed grading status, or exception text.
            self._discarded_stderr_bytes += len(chunk.encode("utf-8", errors="replace"))

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        session = dict(kwargs.get("session") or {})
        observation_text = str(kwargs.get("observation_text") or "")
        valid_actions = [str(action) for action in kwargs.get("valid_actions") or []]
        source_readout = dict(kwargs.get("readout") or {})
        public_readout = {
            key: source_readout[key]
            for key in ("ascii", "observation", "observation_text")
            if key in source_readout
        }
        public_readout["valid_actions"] = valid_actions
        request = {
            "op": "choose_actions",
            "observation_text": observation_text,
            "session": {
                "lane": str(session.get("lane") or "rust"),
                "ply": int(session.get("ply") or 0),
            },
            "valid_actions": valid_actions,
            "ply": int(kwargs.get("ply") or 0),
            "readout": public_readout,
        }
        with self._lock:
            if self._proc.poll() is not None:
                raise CandidatePolicyFailure()
            self._request_id += 1
            request_id = self._request_id
            request["id"] = request_id
            encoded_request = json.dumps(request, separators=(",", ":"))
            if len(encoded_request) > _MAX_IPC_LINE_CHARS:
                raise ValueError("isolated policy request exceeds IPC limit")
            try:
                self._stdin.write(encoded_request + "\n")
                self._stdin.flush()
            except (BrokenPipeError, OSError):
                raise CandidatePolicyFailure() from None
            try:
                response_line = self._stdout.readline(_MAX_IPC_LINE_CHARS + 1)
            except UnicodeError:
                self._terminate()
                raise CandidatePolicyFailure() from None
        if not response_line:
            self._stderr_thread.join(timeout=0.25)
            raise CandidatePolicyFailure()
        if len(response_line) > _MAX_IPC_LINE_CHARS or not response_line.endswith("\n"):
            self._terminate()
            raise CandidatePolicyFailure()
        try:
            response = json.loads(response_line)
        except json.JSONDecodeError:
            self._terminate()
            raise CandidatePolicyFailure() from None
        if (
            isinstance(response, dict)
            and response.get("id") == request_id
            and response.get("ok") is False
            and response.get("error_code") == _CANDIDATE_FAILURE_CODE
        ):
            raise CandidatePolicyFailure()
        if (
            not isinstance(response, dict)
            or response.get("id") != request_id
            or response.get("ok") is not True
            or not isinstance(response.get("decision"), dict)
        ):
            raise CandidatePolicyFailure()
        return dict(response["decision"])

    def _terminate(self) -> None:
        if self._container_name:
            docker = shutil.which("docker")
            if docker:
                try:
                    env = _docker_client_environment()
                    context = _resolve_darwin_docker_context(env=env)
                    subprocess.run(
                        [
                            docker,
                            "--context",
                            context,
                            "rm",
                            "--force",
                            self._container_name,
                        ],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=3,
                        env=env,
                    )
                except subprocess.TimeoutExpired:
                    pass
        if self._proc.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.kill(self._proc.pid, signal.SIGTERM)
            else:
                self._proc.terminate()
            self._proc.wait(timeout=1)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            if self._proc.poll() is None:
                self._proc.kill()
                self._proc.wait(timeout=2)

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
                    self._terminate()
            self._sandbox.cleanup()


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--serve":
        raise SystemExit("usage: policy_subprocess.py --serve <policy.py>")
    return _serve(Path(sys.argv[2]))


if __name__ == "__main__":
    raise SystemExit(main())
