"""Standalone-mode coverage for the Craftax scorer.

Covers auto-detection (slot auth file present -> legacy mode; absent ->
standalone), the GAMEBENCH_STANDALONE override contract, the health verdict
in both modes, the claim stand-in, and the direct (no-bubblewrap) candidate
launch command used on managed sandboxes (Modal/Daytona) where nested
namespaces are unavailable.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from containers.scorer_service import service
from containers.scorer_service.authority import ScorerAuthority
from containers.scorer_service.claim_authority import (
    ClaimAuthorityError,
    StandaloneClaimAuthority,
)
from containers.scorer_service.standalone import (
    STANDALONE_ENV_VAR,
    StandaloneModeError,
    resolve_standalone_mode,
    standalone_mode_forced,
)


_SHA1 = "a" * 40
_SHA256 = "b" * 64
_SHARED_POLICY_SUBPROCESS = (
    Path(__file__).resolve().parents[4] / "shared" / "codepolicy" / "policy_subprocess.py"
)


def _load_shared_policy_subprocess():
    spec = importlib.util.spec_from_file_location(
        "gamebench_policy_subprocess_under_test", _SHARED_POLICY_SUBPROCESS
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _authority(
    tmp_path: Path, service_auth_file: str = "/run/gamebench/service-auth"
) -> ScorerAuthority:
    state = tmp_path / "state"
    workspace = tmp_path / "workspace"
    state.mkdir(mode=0o700, exist_ok=True)
    workspace.mkdir(mode=0o700, exist_ok=True)
    return ScorerAuthority.model_validate(
        {
            "schema_version": "gamebench.craftax.scorer_authority.v1",
            "environment": "dev",
            "cloud_slot": "slot1-cloud",
            "deployment_id": "dep-standalone-test",
            "claim_id": "claim-standalone-test",
            "fencing_token": 7,
            "gamebench_source_sha": _SHA1,
            "scorer_source_sha": _SHA1,
            "scorer_fixture_manifest_sha256": _SHA256,
            "scorer_binary_sha256": _SHA256,
            "scorer_image_digest": f"sha256:{_SHA256}",
            "backend_api_base_url": "https://backend.invalid",
            "service_auth_file": service_auth_file,
            "request_bearer_token_sha256": _SHA256,
            "backend_claim_read_timeout_seconds": 5.0,
            "expected_platform_system": "Linux",
            "expected_platform_machine": "x86_64",
            "state_directory": str(state),
            "workspace_directory": str(workspace),
            "max_candidate_bytes": 1024,
            "max_request_body_bytes": 131072,
            "max_action_body_bytes": 4096,
            "max_active_jobs": 1,
            "max_queued_jobs": 1,
            "max_retained_jobs": 4,
            "max_cleaned_state_records": 16,
            "cleaned_state_record_policy": "retain_until_external_archive",
            "maximum_timeout_seconds": 60.0,
            "process_termination_grace_seconds": 5.0,
            "episode_parallelism": 1,
            "profiles": [
                {
                    "execution_contract_version": "gamebench.craftax.score.v1",
                    "entrypoint": "policy.py",
                    "task_id": "craftax-singleplayer",
                    "suite_id": "suite-standalone-test",
                    "seeds": [0, 1],
                    "max_steps": 10,
                    "lane": "rust",
                    "policy_identity": "git_source_sha256_v1",
                    "task_template": "tasks/policy_dev_template.json",
                }
            ],
        }
    )


class TestFlagContract:
    def test_unset_empty_and_zero_mean_auto_detect(self) -> None:
        assert standalone_mode_forced({}) is False
        assert standalone_mode_forced({STANDALONE_ENV_VAR: ""}) is False
        assert standalone_mode_forced({STANDALONE_ENV_VAR: "0"}) is False

    def test_one_forces(self) -> None:
        assert standalone_mode_forced({STANDALONE_ENV_VAR: "1"}) is True

    @pytest.mark.parametrize("value", ["true", "yes", "on", "2", " 1"])
    def test_other_values_are_typed_startup_errors(self, value: str) -> None:
        with pytest.raises(StandaloneModeError, match=STANDALONE_ENV_VAR):
            standalone_mode_forced({STANDALONE_ENV_VAR: value})

    def test_reads_process_environment_by_default(self, monkeypatch) -> None:
        monkeypatch.delenv(STANDALONE_ENV_VAR, raising=False)
        assert standalone_mode_forced() is False
        monkeypatch.setenv(STANDALONE_ENV_VAR, "1")
        assert standalone_mode_forced() is True


class TestResolveStandaloneMode:
    def test_slot_auth_file_present_selects_legacy_mode(self, tmp_path) -> None:
        auth = tmp_path / "service-auth"
        auth.write_text("{}")
        resolution = resolve_standalone_mode(service_auth_file=auth, environ={})
        assert resolution.enabled is False
        assert resolution.mode == "cloud_slot"
        assert str(auth) in resolution.reason

    def test_slot_auth_file_absent_selects_standalone(self, tmp_path) -> None:
        resolution = resolve_standalone_mode(
            service_auth_file=tmp_path / "absent", environ={}
        )
        assert resolution.enabled is True
        assert resolution.mode == "standalone"
        assert "absent" in resolution.reason

    def test_flag_forces_standalone_even_with_auth_file(self, tmp_path) -> None:
        auth = tmp_path / "service-auth"
        auth.write_text("{}")
        resolution = resolve_standalone_mode(
            service_auth_file=auth, environ={STANDALONE_ENV_VAR: "1"}
        )
        assert resolution.enabled is True
        assert "forces" in resolution.reason

    def test_invalid_flag_is_typed_error(self, tmp_path) -> None:
        with pytest.raises(StandaloneModeError, match=STANDALONE_ENV_VAR):
            resolve_standalone_mode(
                service_auth_file=tmp_path / "absent",
                environ={STANDALONE_ENV_VAR: "yes"},
            )


class TestExpectedIsolationReceipt:
    def test_slot_mode_requires_bubblewrap(self) -> None:
        assert service.expected_isolation_receipt(standalone=False) == {
            "sandbox": "bubblewrap",
            "network": "unshared",
        }

    def test_standalone_mode_requires_honest_direct_receipt(self) -> None:
        assert service.expected_isolation_receipt(standalone=True) == {
            "sandbox": "container_standalone",
            "network": "container",
        }


class TestStandaloneReadinessChecks:
    def test_all_pass_when_services_are_actually_up(self, tmp_path) -> None:
        binary = tmp_path / "craftax_repl"
        binary.write_bytes(b"#!/bin/sh\n")
        binary.chmod(0o755)
        checks = service.standalone_readiness_checks(
            closed=False,
            scorer_binary=binary,
            state_directory=tmp_path,
            workspace_directory=tmp_path,
        )
        assert checks == {
            "job_executor_open": True,
            "rust_repl_binary_executable": True,
            "state_directory_writable": True,
            "workspace_directory_writable": True,
        }

    def test_missing_binary_and_directories_fail(self, tmp_path) -> None:
        checks = service.standalone_readiness_checks(
            closed=True,
            scorer_binary=tmp_path / "absent",
            state_directory=tmp_path / "no-state",
            workspace_directory=tmp_path / "no-workspace",
        )
        assert checks == {
            "job_executor_open": False,
            "rust_repl_binary_executable": False,
            "state_directory_writable": False,
            "workspace_directory_writable": False,
        }

    def test_non_executable_binary_fails(self, tmp_path) -> None:
        binary = tmp_path / "craftax_repl"
        binary.write_bytes(b"#!/bin/sh\n")
        binary.chmod(0o644)
        checks = service.standalone_readiness_checks(
            closed=False,
            scorer_binary=binary,
            state_directory=tmp_path,
            workspace_directory=tmp_path,
        )
        assert checks["rust_repl_binary_executable"] is False


def _standalone_manager(monkeypatch, tmp_path, *, forced: bool = False):
    """Manager on a standalone substrate: no slot auth file mounted."""
    if forced:
        # Explicit override: flag forces standalone even though the slot
        # auth file is present.
        auth = tmp_path / "service-auth"
        auth.write_text("{}")
        auth.chmod(0o600)
        monkeypatch.setenv(STANDALONE_ENV_VAR, "1")
        authority = _authority(tmp_path, service_auth_file=str(auth))
    else:
        monkeypatch.delenv(STANDALONE_ENV_VAR, raising=False)
        authority = _authority(
            tmp_path, service_auth_file=str(tmp_path / "no-service-auth")
        )
    binary = tmp_path / "craftax_repl"
    binary.write_bytes(b"#!/bin/sh\n")
    binary.chmod(0o755)
    monkeypatch.setattr(service, "ensure_rust_repl_binary", lambda: binary)
    return service.ScoreJobManager(authority), binary


class TestManagerHealthStandalone:
    def test_health_reflects_real_local_readiness(self, monkeypatch, tmp_path) -> None:
        # Auto-detected: no flag set, slot auth file absent.
        manager, binary = _standalone_manager(monkeypatch, tmp_path)
        try:
            assert isinstance(manager._claim_authority, StandaloneClaimAuthority)
            payload = manager.health()
            assert payload["status"] == "healthy"
            assert payload["mode"] == "standalone"
            assert payload["claim_current"] is None
            assert all(payload["standalone_checks"].values())

            binary.chmod(0o644)
            degraded = manager.health()
            assert degraded["status"] == "unhealthy"
            assert degraded["standalone_checks"]["rust_repl_binary_executable"] is False
        finally:
            manager.close()
        closed = manager.health()
        assert closed["status"] == "unhealthy"
        assert closed["standalone_checks"]["job_executor_open"] is False

    def test_binary_removal_flips_health(self, monkeypatch, tmp_path) -> None:
        manager, binary = _standalone_manager(monkeypatch, tmp_path)
        try:
            assert manager.health()["status"] == "healthy"
            binary.unlink()
            assert manager.health()["status"] == "unhealthy"
        finally:
            manager.close()

    def test_info_reports_direct_candidate_execution(self, monkeypatch, tmp_path) -> None:
        manager, _binary = _standalone_manager(monkeypatch, tmp_path)
        try:
            assert manager.info()["candidate_execution"] == "container_standalone_direct"
        finally:
            manager.close()

    def test_flag_forces_standalone_despite_present_auth_file(
        self, monkeypatch, tmp_path
    ) -> None:
        manager, _binary = _standalone_manager(monkeypatch, tmp_path, forced=True)
        try:
            assert isinstance(manager._claim_authority, StandaloneClaimAuthority)
            assert manager.health()["mode"] == "standalone"
        finally:
            manager.close()


class TestManagerHealthSlotMode:
    class _StubClaim:
        instances: list["TestManagerHealthSlotMode._StubClaim"] = []

        def __init__(self, **_kwargs) -> None:
            self.fail = False
            type(self).instances.append(self)

        def assert_current(self) -> None:
            if self.fail:
                raise ClaimAuthorityError("cloud claim authority is stale or mismatched")

    def test_health_still_requires_current_claim(self, monkeypatch, tmp_path) -> None:
        # Slot chain detected: auth file mounted, no flag set -> legacy mode.
        monkeypatch.delenv(STANDALONE_ENV_VAR, raising=False)
        auth = tmp_path / "service-auth"
        auth.write_text("{}")
        auth.chmod(0o600)
        self._StubClaim.instances.clear()
        monkeypatch.setattr(service, "ClaimAuthorityClient", self._StubClaim)
        manager = service.ScoreJobManager(
            _authority(tmp_path, service_auth_file=str(auth))
        )
        try:
            payload = manager.health()
            assert payload["status"] == "healthy"
            assert payload["claim_current"] is True
            # Slot-mode payload is unchanged by the standalone feature.
            assert "mode" not in payload
            assert "standalone_checks" not in payload

            self._StubClaim.instances[0].fail = True
            degraded = manager.health()
            assert degraded["status"] == "unhealthy"
            assert degraded["claim_current"] is False

            assert manager.info()["candidate_execution"] == "linux_bwrap_no_network"
        finally:
            manager.close()


class TestStandaloneClaimAuthority:
    def test_assert_current_never_raises_and_returns_none(self) -> None:
        assert StandaloneClaimAuthority().assert_current() is None


class TestSharedPolicySubprocessStandalone:
    def test_flag_contract_matches_scorer_helper(self, monkeypatch) -> None:
        module = _load_shared_policy_subprocess()
        monkeypatch.delenv(STANDALONE_ENV_VAR, raising=False)
        assert module._standalone_mode() is False
        monkeypatch.setenv(STANDALONE_ENV_VAR, "0")
        assert module._standalone_mode() is False
        monkeypatch.setenv(STANDALONE_ENV_VAR, "1")
        assert module._standalone_mode() is True
        monkeypatch.setenv(STANDALONE_ENV_VAR, "true")
        with pytest.raises(RuntimeError, match=STANDALONE_ENV_VAR):
            module._standalone_mode()

    def test_standalone_command_runs_policy_server_without_bwrap(
        self, monkeypatch, tmp_path
    ) -> None:
        module = _load_shared_policy_subprocess()
        (tmp_path / "empty").mkdir()
        executable = Path(sys.executable).resolve()
        command, env = module._linux_standalone_command(
            root=tmp_path, executable=executable
        )
        assert command == [
            str(executable),
            str(tmp_path / "policy_subprocess.py"),
            "--serve",
            str(tmp_path / "policy.py"),
        ]
        assert not any("bwrap" in part for part in command)
        # Environment stays scrubbed: nothing from os.environ leaks through.
        assert set(env) == {
            "HOME",
            "PATH",
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONNOUSERSITE",
            "TMPDIR",
        }
        assert env["HOME"] == str(tmp_path / "empty")

    def test_sandbox_command_gates_on_flag_for_linux(
        self, monkeypatch, tmp_path
    ) -> None:
        module = _load_shared_policy_subprocess()
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setenv(STANDALONE_ENV_VAR, "1")
        command, _env = module._sandbox_command(root=tmp_path, container_name=None)
        assert not any("bwrap" in part for part in command)
        assert command[1] == str(tmp_path / "policy_subprocess.py")
