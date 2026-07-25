#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/candidate /workspace/spec
cp -a /task/spec/. /workspace/spec/
touch /workspace/candidate/README.txt
