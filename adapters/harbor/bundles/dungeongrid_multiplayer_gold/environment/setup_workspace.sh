#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/candidate /workspace/reference
cp -a /task/reference/dungeongrid-multiplayer /workspace/reference/dungeongrid-multiplayer
touch /workspace/candidate/README.txt
