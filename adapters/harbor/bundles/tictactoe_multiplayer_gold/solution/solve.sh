#!/usr/bin/env bash
# Reference solution — copies gold implementation into candidate workspace.
set -euo pipefail

DEST="/workspace/candidate"
mkdir -p "$DEST/gold" "$DEST/policies" "$DEST/scripts"
cp -a /task/reference/gold/. "$DEST/gold/"
cp -a /task/reference/policies/. "$DEST/policies/"
cp /task/reference/scripts/run_service.py "$DEST/scripts/run_service.py"
echo "reference solution staged at $DEST"
