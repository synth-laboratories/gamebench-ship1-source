"""Read-only, fail-closed access to the pinned NLE 0.9.0 ISAAC64 state.

NLE's public ``get_seeds`` API returns the configured seeds, not the evolving
state.  The pinned macOS wheel retains the local ``rnglist`` symbol in its
Mach-O symbol table.  This module resolves that symbol relative to exported
function addresses, verifies the exact C layout and function pointers, and
copies the two ISAAC64 contexts without advancing either generator.

This is oracle instrumentation.  It is never simulator input and deliberately
provides no write/restore API.
"""

from __future__ import annotations

import ctypes
import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ISAAC64_SIZE = 256
PINNED_BINARY_SHA256 = "7ac1270dfd5fa0a5fb2f715ef6a7151058f06cda595e4b722ac6d070ce0f2057"
PINNED_SOURCE_COMMIT = "2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa"
EXPECTED_CONTEXT_SIZE = 4128
EXPECTED_ENTRY_SIZE = 4144
EXPECTED_STATE_OFFSET = 16


class Isaac64Context(ctypes.Structure):
    _fields_ = [
        ("n", ctypes.c_uint),
        ("r", ctypes.c_uint64 * ISAAC64_SIZE),
        ("m", ctypes.c_uint64 * ISAAC64_SIZE),
        ("a", ctypes.c_uint64),
        ("b", ctypes.c_uint64),
        ("c", ctypes.c_uint64),
    ]


class RngEntry(ctypes.Structure):
    _fields_ = [
        ("fn", ctypes.c_void_p),
        ("init", ctypes.c_ubyte),
        ("state", Isaac64Context),
    ]


@dataclass(frozen=True)
class RngSnapshot:
    core: bytes
    display: bytes
    core_n: int
    display_n: int
    binary_sha256: str

    def public_record(self) -> dict[str, Any]:
        return {
            "schema": "gamebench.nethack.authoritative_rng_snapshot.v1",
            "binary_sha256": self.binary_sha256,
            "core": {
                "n": self.core_n,
                "byte_length": len(self.core),
                "state_hex": self.core.hex(),
                "state_sha256": hashlib.sha256(self.core).hexdigest(),
            },
            "display": {
                "n": self.display_n,
                "byte_length": len(self.display),
                "state_hex": self.display.hex(),
                "state_sha256": hashlib.sha256(self.display).hexdigest(),
            },
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _symbol_offsets(path: Path) -> dict[str, int]:
    if sys.platform != "darwin":
        raise RuntimeError("authoritative RNG symbol probe currently supports only the pinned macOS NLE wheel")
    result = subprocess.run(
        ["nm", "-a", str(path)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    wanted = {"rnglist", "rn2", "rn2_on_display_rng"}
    offsets: dict[str, int] = {}
    pattern = re.compile(r"^([0-9A-Fa-f]+)\s+\w\s+_(rnglist|rn2|rn2_on_display_rng)$")
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match and match.group(2) in wanted:
            offsets[match.group(2)] = int(match.group(1), 16)
    if set(offsets) != wanted:
        raise RuntimeError(f"pinned NLE binary lacks required unambiguous RNG symbols: {sorted(offsets)}")
    return offsets


class PinnedNleRngReader:
    """Verified read-only view of one live ``nethack.Nethack`` instance."""

    def __init__(self, nethack_instance: Any):
        path = Path(str(getattr(nethack_instance, "dlpath", ""))).resolve()
        if not path.is_file():
            raise RuntimeError("live NLE instance does not expose its copied libnethack path")
        try:
            from nle.nethack.nethack import DLPATH
        except ImportError as error:
            raise RuntimeError("pinned NLE runtime identity is unavailable") from error
        binary_sha256 = _sha256(path)
        installed_sha256 = _sha256(Path(DLPATH).resolve())
        if binary_sha256 != PINNED_BINARY_SHA256 or installed_sha256 != PINNED_BINARY_SHA256:
            raise RuntimeError("live and installed libnethack do not match the exact pinned oracle binary")
        if (
            ctypes.sizeof(Isaac64Context) != EXPECTED_CONTEXT_SIZE
            or ctypes.sizeof(RngEntry) != EXPECTED_ENTRY_SIZE
            or RngEntry.state.offset != EXPECTED_STATE_OFFSET
        ):
            raise RuntimeError("host ctypes layout does not match pinned NLE 0.9.0 ISAAC64 ABI")

        offsets = _symbol_offsets(path)
        library = ctypes.CDLL(str(path))
        addresses = {
            name: int(ctypes.cast(getattr(library, name), ctypes.c_void_p).value or 0)
            for name in ("rn2", "rn2_on_display_rng")
        }
        base_from_core = addresses["rn2"] - offsets["rn2"]
        base_from_display = addresses["rn2_on_display_rng"] - offsets["rn2_on_display_rng"]
        if base_from_core <= 0 or base_from_core != base_from_display:
            raise RuntimeError("NLE RNG symbol slide is inconsistent")

        entries = (RngEntry * 2).from_address(base_from_core + offsets["rnglist"])
        if int(entries[0].fn or 0) != addresses["rn2"]:
            raise RuntimeError("NLE core RNG function pointer does not match rnglist[0]")
        if int(entries[1].fn or 0) != addresses["rn2_on_display_rng"]:
            raise RuntimeError("NLE display RNG function pointer does not match rnglist[1]")
        if not (0 <= int(entries[0].state.n) <= ISAAC64_SIZE):
            raise RuntimeError("NLE core ISAAC64 index is out of range")
        if not (0 <= int(entries[1].state.n) <= ISAAC64_SIZE):
            raise RuntimeError("NLE display ISAAC64 index is out of range")

        self._path = path
        self._library = library
        # The exact ISAAC64 next-value routine is exported by the pinned
        # binary.  It is called only with a private ctypes copy of a snapshot,
        # never with ``rnglist`` memory.  This lets us prove a call count from
        # full before/after bytes rather than treating the exposed ``n`` index
        # as a hash-like hint.
        next_uint64 = getattr(library, "isaac64_next_uint64", None)
        if next_uint64 is None:
            raise RuntimeError("pinned NLE binary lacks exported ISAAC64 next-value routine")
        next_uint64.argtypes = [ctypes.POINTER(Isaac64Context)]
        next_uint64.restype = ctypes.c_uint64
        self._next_uint64 = next_uint64
        self._entries = entries
        self._binary_sha256 = binary_sha256

    def snapshot(self) -> RngSnapshot:
        core = ctypes.string_at(ctypes.addressof(self._entries[0].state), EXPECTED_CONTEXT_SIZE)
        display = ctypes.string_at(ctypes.addressof(self._entries[1].state), EXPECTED_CONTEXT_SIZE)
        return RngSnapshot(
            core=core,
            display=display,
            core_n=int(self._entries[0].state.n),
            display_n=int(self._entries[1].state.n),
            binary_sha256=self._binary_sha256,
        )

    def replay_draws(self, snapshot: RngSnapshot, lane: str, count: int) -> RngSnapshot:
        """Advance an isolated exact ISAAC64 snapshot, read-only to NLE.

        The clone is initialised from all 4,128 raw bytes, then advanced by
        the pinned binary's own ISAAC routine.  This is intentionally not a
        Python PRNG reimplementation and cannot mutate the live oracle.
        """

        if snapshot.binary_sha256 != self._binary_sha256:
            raise ValueError("RNG snapshot does not belong to this pinned oracle binary")
        if lane not in {"core", "display"}:
            raise ValueError("lane must be core or display")
        if type(count) is not int or count < 0:
            raise ValueError("draw count must be a non-negative integer")
        raw = snapshot.core if lane == "core" else snapshot.display
        if len(raw) != EXPECTED_CONTEXT_SIZE:
            raise ValueError("RNG snapshot has an invalid ISAAC64 state length")
        clone = Isaac64Context.from_buffer_copy(raw)
        for _ in range(count):
            self._next_uint64(ctypes.byref(clone))
        advanced = ctypes.string_at(ctypes.addressof(clone), EXPECTED_CONTEXT_SIZE)
        return RngSnapshot(
            core=advanced if lane == "core" else snapshot.core,
            display=advanced if lane == "display" else snapshot.display,
            core_n=int(clone.n) if lane == "core" else snapshot.core_n,
            display_n=int(clone.n) if lane == "display" else snapshot.display_n,
            binary_sha256=self._binary_sha256,
        )

    def exact_call_count(
        self,
        before: RngSnapshot,
        after: RngSnapshot,
        lane: str,
        *,
        max_draws: int = 512,
    ) -> int:
        """Recover one exact transition count from full state bytes.

        A result is accepted only if advancing the isolated *raw* pre-state
        produces the complete raw post-state for that lane at one and only one
        bounded count.  The other lane is reported separately by callers: it
        may legitimately advance during one action, and does not invalidate a
        per-lane chronology.  No match or a zero-comparison request is a hard
        failure rather than a fitted count.
        """

        if before.binary_sha256 != self._binary_sha256 or after.binary_sha256 != self._binary_sha256:
            raise ValueError("RNG transition binary identity mismatch")
        if lane not in {"core", "display"}:
            raise ValueError("lane must be core or display")
        if type(max_draws) is not int or max_draws < 0:
            raise ValueError("max_draws must be non-negative")
        matches: list[int] = []
        for count in range(max_draws + 1):
            candidate = self.replay_draws(before, lane, count)
            target_before = candidate.core if lane == "core" else candidate.display
            target_after = after.core if lane == "core" else after.display
            target_before_n = candidate.core_n if lane == "core" else candidate.display_n
            target_after_n = after.core_n if lane == "core" else after.display_n
            if target_before == target_after and target_before_n == target_after_n:
                matches.append(count)
        if len(matches) != 1:
            raise ValueError(
                "exact RNG call chronology is unjudgeable: "
                f"found {len(matches)} full-state matches within {max_draws} draws"
            )
        return matches[0]


def bounded_call_count(before: RngSnapshot, after: RngSnapshot, lane: str) -> int:
    """Return the draw count when a boundary consumed at most one ISAAC block."""

    if before.binary_sha256 != after.binary_sha256:
        raise ValueError("RNG snapshots came from different oracle binaries")
    if lane not in {"core", "display"}:
        raise ValueError("lane must be core or display")
    before_n = before.core_n if lane == "core" else before.display_n
    after_n = after.core_n if lane == "core" else after.display_n
    count = before_n - after_n
    if count < 0:
        count += ISAAC64_SIZE
    if count >= ISAAC64_SIZE:
        raise ValueError("RNG call count is not bounded to one ISAAC64 block")
    if count == 0:
        before_bytes = before.core if lane == "core" else before.display
        after_bytes = after.core if lane == "core" else after.display
        if before_bytes != after_bytes:
            raise ValueError("RNG state changed without an auditable bounded index delta")
    return count


def validate_rng_record(record: dict[str, Any]) -> list[str]:
    """Validate that a serialized source record contains exact state, not hashes only."""

    failures: list[str] = []
    if not isinstance(record, dict) or record.get("schema") != "gamebench.nethack.authoritative_rng_snapshot.v1":
        return ["invalid authoritative RNG record schema"]
    if record.get("binary_sha256") != PINNED_BINARY_SHA256:
        failures.append("authoritative RNG record binary identity mismatch")
    for lane in ("core", "display"):
        value = record.get(lane)
        if not isinstance(value, dict):
            failures.append(f"authoritative RNG record lacks {lane} state")
            continue
        state_hex = value.get("state_hex")
        if not isinstance(state_hex, str):
            failures.append(f"authoritative RNG record lacks exact {lane} bytes")
            continue
        try:
            state = bytes.fromhex(state_hex)
        except ValueError:
            failures.append(f"authoritative RNG record has malformed {lane} state")
            continue
        if len(state) != EXPECTED_CONTEXT_SIZE or value.get("byte_length") != EXPECTED_CONTEXT_SIZE:
            failures.append(f"authoritative RNG record has wrong {lane} state length")
        if value.get("state_sha256") != hashlib.sha256(state).hexdigest():
            failures.append(f"authoritative RNG record has invalid {lane} state digest")
        n = value.get("n")
        if type(n) is not int or not 0 <= n <= ISAAC64_SIZE:
            failures.append(f"authoritative RNG record has invalid {lane} index")
    return failures
