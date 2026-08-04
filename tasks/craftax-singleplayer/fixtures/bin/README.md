# Prebuilt Craftax Binaries

Tracked prebuilt binaries live under an immutable target-specific fixture
directory, never under Cargo's ignored `target/` tree. Each binary has a
`gamebench.prebuilt_binary.v1` manifest that binds it to:

- the exact binary SHA-256, size, executable format, and GNU build ID;
- a reachable canonical GameBench commit and the complete Cargo/Rust source
  closure used to build it;
- an immutable builder image, toolchain identity, working directory, and
  locked build command; and
- two independent, byte-identical rebuild digests.

`containers/codepolicy/rust_repl_session.py` verifies the manifest, source
closure, mode, ELF header and machine, dynamic loader, GNU Build ID, Rust
toolchain marker, glibc requirement, host glibc suitability, and binary
identities before atomically materializing
`gold_rust/target/release/craftax_repl`. A missing or ambiguous identity fails
closed on Linux/AArch64; it never falls back to an ambient Cargo toolchain.
Non-fixture host builds use an operating-system/architecture-specific Cargo
target directory, so they cannot reuse fixture bytes through Cargo's mtime
cache.

The earlier runtime-only Linux/AArch64 binary with SHA-256
`4dc2bbb999ea6a44e2ccb9f3035bb3e9836d3c0ebf5d02a4863d8a9b7aa9c6d5`
is non-authoritative lineage. It was intentionally replaced because its source
snapshot was not reachable from canonical GameBench history.

The Linux/AArch64 binary with SHA-256
`de85d645a3d2c72e9680795c5606974b7f5f105169c9df1172aeaf02bd5fe8af`
(source snapshot `80c630db6ab35e7c9ae2b79eda51ac2bfc16ad6b`, verified
2026-07-16) is superseded lineage. Engine feature work on `src/native.rs`
(ranged hostile projectiles, survival homeostasis and death, day/night and
descent-gate observability, the `path` glyph) landed without republishing the
fixture, so its source closure no longer matched the tree and startup
validation failed closed. The current fixture was rebuilt from the tree at the
manifest's `canonical_commit` with the same pinned builder image and command.

To publish a replacement, rebuild from the exact manifest source closure with
the manifest's pinned image and command, then update the binary and every
affected manifest identity together. Reviewers must prove the rebuilt bytes
match the manifest SHA-256 and an independent rebuild before accepting the
change.
