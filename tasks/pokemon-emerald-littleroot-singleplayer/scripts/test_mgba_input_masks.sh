#!/bin/sh
# Verify all GBA buttons and representative chord encodings against the
# python-mGBA enum-index API. Run this in the pinned oracle image so the test
# exercises the exact binding used for evidence capture.
set -eu

image=${MGBA_ORACLE_IMAGE:-gamebench-mgba-oracle:0.10.5-9}
docker run --rm --platform linux/arm64 --entrypoint python3 "$image" -c '
import runpy
import sys
import mgba.core
sys.path.insert(0, "/opt/gamebench")
module = runpy.run_path("/opt/gamebench/mgba_jsonl_oracle.py")
encode = module["button_indices"]
indices = {"a": 0, "b": 1, "select": 2, "start": 3, "right": 4, "left": 5, "up": 6, "down": 7, "r": 8, "l": 9}
for button, index in indices.items():
    actual = mgba.core.Core._keys_to_int(*encode([button], indices))
    expected = 1 << index
    assert actual == expected, (button, actual, expected)
for held in (("a", "b"), ("up", "right"), ("start", "select"), ("l", "r"), ("a", "up", "right")):
    actual = mgba.core.Core._keys_to_int(*encode(list(held), indices))
    expected = sum(1 << indices[button] for button in held)
    assert actual == expected, (held, actual, expected)
assert mgba.core.Core._keys_to_int() == 0
print("mGBA input masks: 10 single buttons + 5 chords passed")
'
