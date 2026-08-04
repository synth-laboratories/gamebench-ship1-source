# Container-pool build of the GameBench code-policy DEO hillclimb task.
#
# This is NOT a replacement for environment/Dockerfile. That one is built by the
# host Harbor lane (`adapters/harbor/scripts/_run_harbor_agent.sh`) with the
# gamebench repo root as its context and real `--build-arg`s, so it COPYs
# `tasks/shared` and `tasks/<env>` directly. Both are correct for their own lane.
#
# The pool build context is different and much narrower: Rhodes archives the
# Dockerfile's own directory and nothing above it
# (`harbor_tasks.py::_harbor_native_context_archive`), so a pool build cannot
# reach the repo. This Dockerfile therefore sits at the BUNDLE root, making the
# whole bundle the context, and reads the engine trees from `vendor/`, which
# `pool/sync_vendor.sh` stages from the repo before packaging.
#
# Publish with `harbor_dockerfile_path: "Dockerfile"` in the release metadata,
# otherwise the backend looks for the default `environment/Dockerfile` and picks
# up the host-lane one, whose COPYs cannot resolve here.
#
# Build args are not plumbed through the pool build path -- `do_build` takes a
# Dockerfile and a context, no args -- so these ARG defaults are what the image
# is actually built with. `pool/sync_vendor.sh` asserts they match the env it
# vendored rather than letting the two drift into a broken image.

FROM python:3.12-slim

ARG GAMEBENCH_TASK=craftax-singleplayer
ARG CANDIDATE_SUBDIR=craftax

# These must be image ENV, not deployment env_vars: Rhodes exports env_vars into
# the agent phase only, while the verifier phase runs under `set -u` and reads
# GAMEBENCH_TASK (tests/test.sh). Image ENV is present in every exec.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GAMEBENCH_TASK=${GAMEBENCH_TASK} \
    CANDIDATE_SUBDIR=${CANDIDATE_SUBDIR} \
    GAMEBENCH_WORKSPACE_ROOT=/workspace \
    GAMEBENCH_ROOT=/workspace/gamebench

RUN pip install --no-cache-dir httpx pydantic

WORKDIR /task

COPY task.toml /task/task.toml
COPY instruction.md /task/instruction.md
COPY environment/setup_workspace.sh /task/environment/setup_workspace.sh
COPY solution /task/solution
COPY tests/test.sh /task/tests/test.sh
COPY tests/score_hillclimb.py /task/tests/score_hillclimb.py

COPY files/run_gamebench_hillclimb_task.py /workspace/workspace/run_gamebench_hillclimb_task.py

# Staged by pool/sync_vendor.sh from the repo's tracked files.
COPY vendor/tasks/shared /workspace/gamebench/tasks/shared
COPY vendor/tasks/${GAMEBENCH_TASK} /workspace/gamebench/tasks/${GAMEBENCH_TASK}

RUN chmod +x /task/environment/setup_workspace.sh /task/solution/solve.sh /task/tests/test.sh

WORKDIR /workspace
CMD ["bash"]
