#!/usr/bin/env bash
# Reference solution — copies gold implementation into candidate workspace.
set -euo pipefail

DEST="/workspace/candidate"
mkdir -p "$DEST/gold_python" "$DEST/shared" "$DEST/policies" "$DEST/scripts"
cp -a /task/reference/gold_python/. "$DEST/gold_python/"
cp -a /task/reference/shared/. "$DEST/shared/"
cp -a /task/reference/policies/. "$DEST/policies/"
cp /task/reference/scripts/run_service.py "$DEST/scripts/run_service.py"
echo "reference solution staged at $DEST"
