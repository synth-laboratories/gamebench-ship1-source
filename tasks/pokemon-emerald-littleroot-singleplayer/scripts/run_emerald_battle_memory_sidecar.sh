#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 /absolute/path/to/emerald.gba /absolute/path/to/checkpoint.state" >&2
  exit 2
fi
rom_path=$1
state_path=$2
case "$rom_path:$state_path" in
  /*:/*) ;;
  *) echo "ROM and state paths must be absolute" >&2; exit 2 ;;
esac
if [ ! -f "$rom_path" ] || [ ! -f "$state_path" ]; then
  echo "ROM and state paths must name existing files" >&2
  exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
task_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
sidecar="$script_dir/emerald_battle_memory_sidecar.py"
manifest="$task_dir/fixtures/gold/emerald_battle_observability.json"
image=gamebench-mgba-oracle:0.10.5-9
expected_image_id=sha256:5995357b864e56df0715730a0ec2735d1a3f6af73d0bd90b87ee1b4f8bd7e0ed
expected_script_sha=af64e8dddc4c409e8e14d810e4c8d9a4622eb6682b7223fafe1300da4fbbb105
expected_manifest_sha=f6e6ea071215886113dc88373335b5a494a262f9354049450057432b562c751b

image_id=$(docker image inspect --format '{{.Id}}' "$image")
if [ "$image_id" != "$expected_image_id" ]; then
  echo "battle sidecar image identity mismatch: got $image_id" >&2
  exit 2
fi
script_sha=$(shasum -a 256 "$sidecar" | awk '{print $1}')
manifest_sha=$(shasum -a 256 "$manifest" | awk '{print $1}')
if [ "$script_sha" != "$expected_script_sha" ] || [ "$manifest_sha" != "$expected_manifest_sha" ]; then
  echo "battle sidecar source/manifest identity mismatch" >&2
  exit 2
fi

exec docker run \
  --rm \
  --platform linux/arm64 \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  --volume "$rom_path:/oracle/emerald.gba:ro" \
  --volume "$state_path:/oracle/checkpoint.state:ro" \
  --volume "$sidecar:/sidecar/emerald_battle_memory_sidecar.py:ro" \
  --volume "$manifest:/sidecar/emerald_battle_observability.json:ro" \
  --env EMERALD_BATTLE_ROM_PATH=/oracle/emerald.gba \
  --env EMERALD_BATTLE_STATE_PATH=/oracle/checkpoint.state \
  --env EMERALD_BATTLE_SYMBOL_MANIFEST_PATH=/sidecar/emerald_battle_observability.json \
  --env "EMERALD_BATTLE_IMAGE_ID=$image_id" \
  --env "EMERALD_BATTLE_SCRIPT_SHA256=$expected_script_sha" \
  --env "EMERALD_BATTLE_SYMBOL_MANIFEST_SHA256=$expected_manifest_sha" \
  --entrypoint python3 \
  "$image" \
  /sidecar/emerald_battle_memory_sidecar.py
