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
sidecar="$script_dir/emerald_field_state_sidecar.py"
manifest="$task_dir/fixtures/gold/emerald_field_state_observability.json"
image=gamebench-mgba-oracle:0.10.5-9
expected_image_id=sha256:5995357b864e56df0715730a0ec2735d1a3f6af73d0bd90b87ee1b4f8bd7e0ed
expected_script_sha=81713aab44ef35e575b606dbfe4449933f6cbf54a82d9cf360a0ab2ab6478d72
expected_manifest_sha=3bbd6795787fbd122787955e0dcdf1de90bfc5d8bd99d565dc13766fa39b8140

image_id=$(docker image inspect --format '{{.Id}}' "$image")
if [ "$image_id" != "$expected_image_id" ]; then
  echo "field sidecar image identity mismatch: got $image_id" >&2
  exit 2
fi
script_sha=$(shasum -a 256 "$sidecar" | awk '{print $1}')
manifest_sha=$(shasum -a 256 "$manifest" | awk '{print $1}')
if [ "$script_sha" != "$expected_script_sha" ] || [ "$manifest_sha" != "$expected_manifest_sha" ]; then
  echo "field sidecar source/manifest identity mismatch" >&2
  exit 2
fi

exec docker run --rm --platform linux/arm64 --network none --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  --volume "$rom_path:/oracle/emerald.gba:ro" \
  --volume "$state_path:/oracle/checkpoint.state:ro" \
  --volume "$sidecar:/sidecar/emerald_field_state_sidecar.py:ro" \
  --volume "$manifest:/sidecar/emerald_field_state_observability.json:ro" \
  --env EMERALD_FIELD_ROM_PATH=/oracle/emerald.gba \
  --env EMERALD_FIELD_STATE_PATH=/oracle/checkpoint.state \
  --env EMERALD_FIELD_SYMBOL_MANIFEST_PATH=/sidecar/emerald_field_state_observability.json \
  --env "EMERALD_FIELD_IMAGE_ID=$image_id" \
  --env "EMERALD_FIELD_SCRIPT_SHA256=$expected_script_sha" \
  --env "EMERALD_FIELD_SYMBOL_MANIFEST_SHA256=$expected_manifest_sha" \
  --entrypoint python3 "$image" /sidecar/emerald_field_state_sidecar.py
