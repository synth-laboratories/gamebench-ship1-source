# Pokémon Emerald — Littleroot Town

This is the GameBench Rust-port lane for a pixel-identical reproduction of the
Pokémon Emerald opening map, beginning with Littleroot Town. It follows the
same shape as the existing Rogue and Craftax ports: a Rust gold library, JSON
scenario CLI, HTTP gold-service binary, deterministic frame hashes, and frozen
reference artifacts.

Implementation coverage is tracked in [PROGRESS.md](PROGRESS.md).

The authoritative visual target is the local mGBA/PokeAgent Emerald reference
at `../../../pokeagent-speedrun/Emerald-GBAdvance/rom.gba`. That ROM is an oracle,
not a runtime dependency: the finished Rust lane must render its own 240×160
RGB frames from locally represented map, sprite, palette, and timing data.

## Current scope

- Fixed 240×160 RGB framebuffer and SHA-256 frame fingerprinting.
- Fifty-seven byte-identical mGBA oracle frames embedded in the Rust gold crate,
  covering title timing through the first Professor Birch-intro frame, staged
  checkpoint idles, all four bedroom movement directions at 16/32/48 frames,
  outdoor first-step movement, and the opening Pokédex navigation sequence.
- Frame-accurate input vocabulary and deterministic session state.
- Source-derived bounds and warp destinations for Little Root, both homes, and
  Professor Birch's Lab, with 16-frame walking cadence in the world model.
- Rust-native terrain composition paths for the exterior plus those five
  interiors, sourced from staged Porymap layouts and tilesets.
- Rust scenario CLI (`scenario`) and HTTP server (`emerald_gold`) matching the
  established GameBench gold-port entrypoints.
- Explicit reference-capture manifest format for frozen Littleroot input/frame
  traces.

The native May-bedroom, Little Root, and Birch-exterior idle reference frames
are proven pixel-identical; all are rendered by Rust rather than copied at
runtime. Full-town completion still
requires continuous player/NPC animation timing; per-tile collision; fade timing; menus;
scripts; and a reference trace for
every reachable Little Root view.

## Entry points

```bash
cd tasks/pokemon-emerald-littleroot-singleplayer
cargo run --manifest-path gold_rust/Cargo.toml --bin scenario
cargo run --manifest-path gold_rust/Cargo.toml --bin emerald_gold -- --port 8103
```

The HTTP service offers `/health`, `/info`, `POST /rollouts`,
`POST /rollouts/{id}/step`, `POST /rollouts/{id}/checkpoint`,
`POST /rollouts/{id}/restore`, `POST /rollouts/{id}/simulate`,
`GET /rollouts/{id}/readout`, and `GET /rollouts/{id}/frame`. Checkpoint
payloads are renderer-independent JSON state encoded as base64; restore redraws
the frame from Rust-owned state before a branch continues.
