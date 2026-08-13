#!/bin/sh
set -eu

if [ "$#" -ne 4 ]; then
  echo "usage: $0 /abs/emerald.gba /abs/input.state /abs/tape.json /abs/terminal.state" >&2
  exit 2
fi
rom=$1
state=$2
tape=$3
terminal=$4
for path in "$rom" "$state" "$tape" "$terminal"; do
  case "$path" in /*) ;; *) echo "all paths must be absolute" >&2; exit 2 ;; esac
done
if [ ! -f "$rom" ] || [ ! -f "$state" ] || [ ! -f "$tape" ]; then
  echo "ROM, input state, and tape must exist" >&2
  exit 2
fi
if [ -e "$terminal" ] || [ ! -d "$(dirname "$terminal")" ]; then
  echo "terminal state must be a new file in an existing directory" >&2
  exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
task_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
trace_script="$script_dir/emerald_continuous_battle_trace.py"
manifest="$task_dir/fixtures/gold/emerald_battle_observability.json"
image=gamebench-mgba-oracle:0.10.5-9
expected_image_id=sha256:5995357b864e56df0715730a0ec2735d1a3f6af73d0bd90b87ee1b4f8bd7e0ed
expected_script_sha=767168b5ccba67403ce70bc18a659d85f965aa79b17a99ec35890a598fd0e418
expected_manifest_sha=f6e6ea071215886113dc88373335b5a494a262f9354049450057432b562c751b
image_id=$(docker image inspect --format '{{.Id}}' "$image")
script_sha=$(shasum -a 256 "$trace_script" | awk '{print $1}')
manifest_sha=$(shasum -a 256 "$manifest" | awk '{print $1}')
if [ "$image_id" != "$expected_image_id" ] \
  || [ "$script_sha" != "$expected_script_sha" ] \
  || [ "$manifest_sha" != "$expected_manifest_sha" ]; then
  echo "continuous battle trace identity mismatch" >&2
  exit 2
fi

output_dir=$(dirname "$terminal")
output_name=$(basename "$terminal")
exec docker run \
  --rm \
  --platform linux/arm64 \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  --volume "$rom:/oracle/emerald.gba:ro" \
  --volume "$state:/oracle/input.state:ro" \
  --volume "$tape:/oracle/tape.json:ro" \
  --volume "$trace_script:/sidecar/emerald_continuous_battle_trace.py:ro" \
  --volume "$manifest:/sidecar/emerald_battle_observability.json:ro" \
  --volume "$output_dir:/oracle-output:rw" \
  --env EMERALD_TRACE_ROM_PATH=/oracle/emerald.gba \
  --env EMERALD_TRACE_STATE_PATH=/oracle/input.state \
  --env EMERALD_TRACE_TAPE_PATH=/oracle/tape.json \
  --env EMERALD_TRACE_SYMBOL_MANIFEST_PATH=/sidecar/emerald_battle_observability.json \
  --env "EMERALD_TRACE_TERMINAL_STATE_PATH=/oracle-output/$output_name" \
  --env "EMERALD_TRACE_IMAGE_ID=$image_id" \
  --env "EMERALD_TRACE_SCRIPT_SHA256=$expected_script_sha" \
  --env "EMERALD_TRACE_SYMBOL_MANIFEST_SHA256=$expected_manifest_sha" \
  --entrypoint python3 \
  "$image" \
  /sidecar/emerald_continuous_battle_trace.py
