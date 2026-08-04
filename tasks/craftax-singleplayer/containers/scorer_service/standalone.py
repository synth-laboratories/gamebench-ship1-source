"""Standalone mode for managed sandboxes (Modal, Daytona, Railway).

The scorer image was designed for privileged Cloud Slot VMs, where two
substrate assumptions hold:

1. The container is granted ``seccomp=unconfined`` and may create nested
   namespaces, so candidate code is re-sandboxed inside the container with
   bubblewrap (``bwrap --unshare-all``).
2. An active fenced CloudDeployment claim exists in the backend, and
   ``/health`` reports healthy only while that claim is provably current.

Managed cloud sandboxes (gVisor-style substrates) can grant neither nested
namespace/seccomp privileges nor slot-chain claims. Standalone mode declares
that the container is running on such a substrate as a single-tenant,
trusted, first-party image whose outer boundary is the provider's own
sandbox:

- The bubblewrap layer and its startup preflight are skipped; the verifier
  and rollout workers run directly inside the (already provider-sandboxed)
  container. This is safe exactly because the whole container is the sandbox
  — there is no co-tenant to protect and the image is first-party.
- ``/health`` reports readiness of the container's own local services (Rust
  REPL binary, writable state/workspace directories, live job executor)
  instead of a CloudDeployment claim it cannot hold.

Mode selection is AUTO-DETECTED from the one slot-chain input the fenced
claim path cannot exist without: the service auth bearer-token file that the
Cloud Slot chain mounts read-only into the container (compose mounts it at
``/run/gamebench/service-auth``; the authority file names the path). Slot
provisioning always mounts it; managed sandboxes cannot, because the token
belongs to the private slotctl VM chain. Present -> cloud-slot mode, exactly
as today. Absent -> standalone mode.

``GAMEBENCH_STANDALONE`` is an explicit override for testing: ``1`` forces
standalone mode even when the auth file is present; unset, ``""``, and ``0``
mean auto-detect. Any other value is a typed startup error.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


STANDALONE_ENV_VAR = "GAMEBENCH_STANDALONE"


class StandaloneModeError(RuntimeError):
    """The standalone-mode flag was present but not a recognized value."""


@dataclass(frozen=True)
class StandaloneResolution:
    """One startup decision: which mode, and the observable reason why."""

    enabled: bool
    reason: str

    @property
    def mode(self) -> str:
        return "standalone" if self.enabled else "cloud_slot"


def standalone_mode_forced(environ: Mapping[str, str] | None = None) -> bool:
    """Whether GAMEBENCH_STANDALONE=1 explicitly forces standalone mode.

    Only ``"1"`` forces; unset, ``""``, and ``"0"`` defer to auto-detection.
    Any other value is a typed startup error rather than a silent default,
    because the two modes have different isolation semantics.
    """
    source = os.environ if environ is None else environ
    raw = source.get(STANDALONE_ENV_VAR)
    if raw is None or raw in {"", "0"}:
        return False
    if raw == "1":
        return True
    raise StandaloneModeError(
        f"{STANDALONE_ENV_VAR} must be unset, '', '0', or '1'; got {raw!r}"
    )


def resolve_standalone_mode(
    *,
    service_auth_file: Path,
    environ: Mapping[str, str] | None = None,
) -> StandaloneResolution:
    """Decide the runtime mode once, at startup, with an auditable reason.

    Slot VMs always mount the slot-chain service auth file, so its presence
    selects the legacy fenced-claim behavior unchanged; its absence means no
    CloudDeployment claim is reachable and the container must be on a managed
    single-tenant substrate, so standalone mode is selected automatically.
    GAMEBENCH_STANDALONE=1 forces standalone regardless (testing override).
    """
    if standalone_mode_forced(environ):
        return StandaloneResolution(
            enabled=True,
            reason=f"{STANDALONE_ENV_VAR}=1 explicitly forces standalone mode",
        )
    if service_auth_file.is_file():
        return StandaloneResolution(
            enabled=False,
            reason=(
                "slot-chain service auth file is present at "
                f"{service_auth_file}; fenced CloudDeployment claim path selected"
            ),
        )
    return StandaloneResolution(
        enabled=True,
        reason=(
            "slot-chain service auth file is absent at "
            f"{service_auth_file}; no fenced CloudDeployment claim is reachable, "
            "so this container is treated as a provider-sandboxed standalone "
            "deployment"
        ),
    )


__all__ = [
    "STANDALONE_ENV_VAR",
    "StandaloneModeError",
    "StandaloneResolution",
    "resolve_standalone_mode",
    "standalone_mode_forced",
]
