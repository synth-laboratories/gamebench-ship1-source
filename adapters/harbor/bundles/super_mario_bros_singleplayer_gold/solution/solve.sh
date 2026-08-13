#!/usr/bin/env bash
# Reference solution — stage the research-safe Rust engine in the candidate workspace.
set -euo pipefail

DEST="/workspace/candidate"
rm -rf "$DEST/gold_rust"
mkdir -p "$DEST"
cp -a /task/reference/gold_rust "$DEST/gold_rust"
mkdir -p "$DEST/scripts"
cp /task/reference/scripts/run_service.py "$DEST/scripts/run_service.py"
echo "reference Rust platformer staged at $DEST/gold_rust"
