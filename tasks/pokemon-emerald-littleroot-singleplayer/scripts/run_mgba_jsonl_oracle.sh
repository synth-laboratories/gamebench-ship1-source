#!/bin/sh
set -eu

if [ "$#" -ne 2 ] && [ "$#" -ne 3 ] && [ "$#" -ne 4 ]; then
  echo "usage: $0 /absolute/path/to/emerald.gba /absolute/path/to/checkpoint.state [checkpoint-id] [snapshot-output-dir]" >&2
  exit 2
fi

rom_path=$1
state_path=$2
checkpoint_id=${3:-bedroom_idle}
snapshot_output_dir=${4:-}
case "$rom_path" in
  /*) ;;
  *) echo "ROM path must be absolute: $rom_path" >&2; exit 2 ;;
esac
case "$state_path" in
  /*) ;;
  *) echo "save-state path must be absolute: $state_path" >&2; exit 2 ;;
esac
if [ ! -f "$rom_path" ]; then
  echo "ROM not found: $rom_path" >&2
  exit 2
fi
if [ ! -f "$state_path" ]; then
  echo "save state not found: $state_path" >&2
  exit 2
fi
case "$checkpoint_id" in
  *[!a-z0-9_]*|'') echo "checkpoint id must use lowercase letters, digits, and underscores" >&2; exit 2 ;;
esac
if [ -n "$snapshot_output_dir" ]; then
  case "$snapshot_output_dir" in
    /*) ;;
    *) echo "snapshot output directory must be absolute: $snapshot_output_dir" >&2; exit 2 ;;
  esac
  if [ ! -d "$snapshot_output_dir" ]; then
    echo "snapshot output directory not found: $snapshot_output_dir" >&2
    exit 2
  fi
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to run the pinned Apple-Silicon mGBA oracle" >&2
  exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
image=${MGBA_ORACLE_IMAGE:-gamebench-mgba-oracle:0.10.5-9}
expected_image_id=${MGBA_ORACLE_EXPECTED_IMAGE_ID:-sha256:5995357b864e56df0715730a0ec2735d1a3f6af73d0bd90b87ee1b4f8bd7e0ed}

if ! docker image inspect "$image" >/dev/null 2>&1; then
  docker build \
    --platform linux/arm64 \
    --tag "$image" \
    --file "$script_dir/mgba_oracle.Dockerfile" \
    "$script_dir" >&2
fi
image_id=$(docker image inspect --format '{{.Id}}' "$image")
if [ "$image_id" != "$expected_image_id" ]; then
  echo "oracle image identity mismatch: got $image_id, expected $expected_image_id" >&2
  echo "refusing to run an unreviewed emulator image" >&2
  exit 2
fi

if [ -n "$snapshot_output_dir" ]; then
  exec docker run \
    --rm \
    --interactive \
    --platform linux/arm64 \
    --network none \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=32m \
    --volume "$rom_path:/oracle/emerald.gba:ro" \
    --volume "$state_path:/oracle/checkpoint.state:ro" \
    --volume "$snapshot_output_dir:/oracle-output:rw" \
    --env MGBA_ORACLE_ROM_PATH=/oracle/emerald.gba \
    --env MGBA_ORACLE_STATE_PATH=/oracle/checkpoint.state \
    --env MGBA_ORACLE_SNAPSHOT_DIR=/oracle-output \
    --env "MGBA_ORACLE_CHECKPOINT_ID=$checkpoint_id" \
    --env "MGBA_ORACLE_IMAGE_ID=$image_id" \
    "$image"
fi

exec docker run \
  --rm \
  --interactive \
  --platform linux/arm64 \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  --volume "$rom_path:/oracle/emerald.gba:ro" \
  --volume "$state_path:/oracle/checkpoint.state:ro" \
  --env MGBA_ORACLE_ROM_PATH=/oracle/emerald.gba \
  --env MGBA_ORACLE_STATE_PATH=/oracle/checkpoint.state \
  --env "MGBA_ORACLE_CHECKPOINT_ID=$checkpoint_id" \
  --env "MGBA_ORACLE_IMAGE_ID=$image_id" \
  "$image"
