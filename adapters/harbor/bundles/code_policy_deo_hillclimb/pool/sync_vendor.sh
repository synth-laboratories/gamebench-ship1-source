#!/usr/bin/env bash
# Stage the engine trees this bundle needs into vendor/ for a container-pool build.
#
# The pool build context is the Dockerfile's own directory, so a pool build
# cannot COPY from the repo the way the host Harbor lane does. This script
# copies the two trees the task needs out of the repo and into vendor/, which is
# gitignored: the repo stays the single source of truth and nothing is
# duplicated in git.
#
# Only git-TRACKED files are copied. tasks/craftax-singleplayer is 333 MB on
# disk and 4.7 MB tracked -- the rest is build output, __pycache__, and run
# residue that would otherwise ship into a container image and into S3.
#
#   ./pool/sync_vendor.sh                      # craftax-singleplayer
#   ./pool/sync_vendor.sh sokoban-singleplayer # another env (see the ARG note)
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(git -C "$BUNDLE_DIR" rev-parse --show-toplevel)"
GAMEBENCH_TASK="${1:-craftax-singleplayer}"
VENDOR_DIR="$BUNDLE_DIR/vendor"

if [ ! -d "$REPO_ROOT/tasks/$GAMEBENCH_TASK" ]; then
  echo "sync_vendor: unknown env '$GAMEBENCH_TASK' (no tasks/$GAMEBENCH_TASK)" >&2
  exit 1
fi

# Build args are not plumbed through the pool build path, so the Dockerfile's
# ARG default is what the image is actually built with. Vendoring one env while
# the Dockerfile names another produces an image that builds clean and then
# fails its first rollout on a missing task directory -- fail here instead.
DOCKERFILE_TASK="$(sed -n 's/^ARG GAMEBENCH_TASK=\(.*\)$/\1/p' "$BUNDLE_DIR/Dockerfile" | head -1)"
if [ "$DOCKERFILE_TASK" != "$GAMEBENCH_TASK" ]; then
  echo "sync_vendor: Dockerfile builds '$DOCKERFILE_TASK' but you asked to vendor '$GAMEBENCH_TASK'." >&2
  echo "             Update the ARG defaults in $BUNDLE_DIR/Dockerfile, or vendor '$DOCKERFILE_TASK'." >&2
  exit 1
fi

rm -rf "$VENDOR_DIR"
mkdir -p "$VENDOR_DIR/tasks"

copy_tracked() {
  local subpath="$1"
  local count=0
  while IFS= read -r -d '' rel; do
    local dest="$VENDOR_DIR/$rel"
    mkdir -p "$(dirname "$dest")"
    cp "$REPO_ROOT/$rel" "$dest"
    count=$((count + 1))
  done < <(git -C "$REPO_ROOT" ls-files -z "$subpath")
  if [ "$count" -eq 0 ]; then
    echo "sync_vendor: no tracked files under $subpath" >&2
    exit 1
  fi
  echo "  $subpath: $count tracked files"
}

echo "sync_vendor: staging into $VENDOR_DIR"
copy_tracked "tasks/shared"
copy_tracked "tasks/$GAMEBENCH_TASK"

TOTAL_BYTES="$(find "$VENDOR_DIR" -type f -exec stat -f '%z' {} + 2>/dev/null | awk '{s+=$1} END {print s+0}')"
echo "sync_vendor: staged $(( TOTAL_BYTES / 1024 )) KiB for $GAMEBENCH_TASK"
echo "sync_vendor: package with harbor_dockerfile_path=\"Dockerfile\""
