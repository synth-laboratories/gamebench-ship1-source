# Reference capture boundary

Frozen Littleroot capture artifacts belong here. Each trace records the
starting save-state identity, button input, frame count, raw 240×160 RGB SHA-256
digest, and an optional lossless frame file.

Capture from the local PokeAgent Emerald environment, but never make the Rust
gold runtime shell out to mGBA, load the ROM, or read emulator memory. The
reference is only a behavior and pixel oracle.

On this Homebrew installation, mGBA's development headers and library are
installed under the versioned Cellar path rather than exposed through
`pkg-config`. Build the extractor from the task root with:

```bash
clang reference_emerald/capture_frame.c \
  -I/opt/homebrew/Cellar/mgba/0.10.5_2/include \
  -L/opt/homebrew/Cellar/mgba/0.10.5_2/lib -lmgba \
  -Wl,-rpath,/opt/homebrew/Cellar/mgba/0.10.5_2/lib \
  -o /tmp/gamebench-capture-frame
```

For example, the source 48-frame eastward exterior trace can then be captured
with key mask `0x10` (`GBA_KEY_RIGHT`) from
`splits/04_rival/04_rival.state`.

When invoked with an object-dump prefix, `capture_frame.c` also writes the
display-register block, active BG VRAM/palette, and OBJ VRAM/palette/OAM
snapshots. These are reference-extraction inputs for staging Rust-owned tile,
palette, animation, priority, and scene-layout data; they are never read by
the runtime from an emulator or ROM.
