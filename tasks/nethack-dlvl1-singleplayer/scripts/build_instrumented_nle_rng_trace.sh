#!/usr/bin/env bash
# Build a disposable, trace-only NLE candidate from the exact pinned source.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 PINNED_NLE_SOURCE OUTPUT_DIRECTORY" >&2
  exit 64
fi

source_dir=$1
output_dir=$2
task_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
patch_file="$task_dir/tools/nle_rng_trace.patch"
cmake_bin=${CMAKE_BIN:-cmake}
python_bin=${PYTHON_BIN:-"$task_dir/.venv/bin/python"}
expected_commit=2fa1be5ac1dbe0a8b075f3274891c306ab8aa0aa

[[ -d "$source_dir/.git" && -f "$patch_file" && -x "$python_bin" ]] || {
  echo "source must be a git checkout; patch and Python runtime must exist" >&2
  exit 65
}
[[ ! -e "$output_dir" ]] || { echo "output directory already exists: $output_dir" >&2; exit 66; }
[[ $(git -C "$source_dir" rev-parse HEAD) == "$expected_commit" ]] || {
  echo "source commit is not pinned $expected_commit" >&2
  exit 67
}
git -C "$source_dir" diff --quiet || { echo "source checkout is dirty" >&2; exit 68; }
git -C "$source_dir" submodule update --init --recursive >&2
git -C "$source_dir" submodule foreach --recursive 'git diff --quiet'

mkdir -p "$output_dir"
cp -R "$source_dir" "$output_dir/source"
git -C "$output_dir/source" apply --check "$patch_file"
git -C "$output_dir/source" apply "$patch_file"

"$cmake_bin" -S "$output_dir/source" -B "$output_dir/build" \
  -DPYTHON_SRC_PARENT="$output_dir/source" -DHACKDIR="$output_dir/hackdir" \
  -DUSE_SEEDING=ON -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DPYTHON_EXECUTABLE="$python_bin" -DCMAKE_C_FLAGS=-g -DCMAKE_CXX_FLAGS=-g >&2
"$cmake_bin" --build "$output_dir/build" --target nethack -j 4 >&2

library="$output_dir/build/libnethack.so"
[[ -f "$library" ]] || { echo "instrumented library was not produced" >&2; exit 69; }
nm -a "$library" | grep -q ' _nle_rng_trace_get$' || { echo "trace ABI missing" >&2; exit 70; }

patch_sha=$(shasum -a 256 "$patch_file" | awk '{print $1}')
library_sha=$(shasum -a 256 "$library" | awk '{print $1}')
toolchain_sha=$( { "$cmake_bin" --version; clang --version; "$python_bin" --version; } | shasum -a 256 | awk '{print $1}')
printf '{"instrumented_lib":"%s","instrumented_source":"%s","library_sha256":"%s","patch_sha256":"%s","toolchain_identity_sha256":"%s"}\n' \
  "$library" "$output_dir/source" "$library_sha" "$patch_sha" "$toolchain_sha"
