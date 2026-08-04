ARG SCORER_BASE_IMAGE
ARG SCORER_BUILDER_IMAGE

FROM ${SCORER_BUILDER_IMAGE} AS rust-builder

WORKDIR /build
COPY gold_rust /build/gold_rust
RUN CARGO_TARGET_DIR=/build/target cargo build \
    --release \
    --locked \
    --quiet \
    --manifest-path /build/gold_rust/Cargo.toml \
    --bin craftax_repl

FROM ${SCORER_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONNOUSERSITE=1
ENV PYTHONUNBUFFERED=1

# The declared security context below is the Cloud Slot (privileged VM) mode:
# candidate code is re-sandboxed inside the container with bubblewrap, which
# needs seccomp=unconfined and nested namespaces. On managed sandboxes
# (Modal/Daytona, gVisor-style) neither is grantable — there the service
# AUTO-DETECTS standalone mode: when the slot-chain service auth file (the
# mount at the authority's service_auth_file path) is absent, the bubblewrap
# layer and its startup preflight are skipped (safe because the provider's
# own single-tenant sandbox is the isolation boundary for this trusted
# first-party image) and /health reports local-service readiness instead of
# a CloudDeployment fenced claim. Slot VMs always mount that file, so their
# behavior is unchanged. GAMEBENCH_STANDALONE=1 forces standalone for
# testing; unset/""/"0" means auto-detect.
# See containers/scorer_service/standalone.py.
LABEL ai.synth.gamebench.runtime.security-context="seccomp=unconfined,cap-drop=ALL,no-new-privileges"

RUN apt-get update \
    && apt-get install --yes --no-install-recommends bubblewrap \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY containers/scorer_service/requirements.txt /tmp/scorer-requirements.txt
RUN python -m pip install --no-cache-dir --requirement /tmp/scorer-requirements.txt

COPY . /app
ENV PYTHONPATH=/app

# The candidate-isolation authority lives at tasks/shared/codepolicy in the
# repo, one level above this build context, and the containers/codepolicy
# adapter resolves it via parents[3] — /shared/codepolicy inside this image.
# It must be supplied as a named context (gamebench_shared=tasks/shared);
# without it every score job fails at policy-sandbox load, on any substrate.
COPY --from=gamebench_shared codepolicy/policy_subprocess.py /shared/codepolicy/policy_subprocess.py

COPY --from=rust-builder \
    /build/target/release/craftax_repl \
    /app/gold_rust/target/gamebench-host/linux-x86_64/release/craftax_repl

# craftax_repl resolves runtime data (defaults/worlds.json and friends) from
# a task_dir baked at compile time as CARGO_MANIFEST_DIR/..: /build for the
# binary built above, /workspace/tasks/craftax-singleplayer for the prebuilt
# aarch64 fixture lane. Without defaults at the matching path every episode
# fails its first reset with "read .../defaults/worlds.json" — the image
# builds clean and then cannot score anything.
COPY defaults /build/defaults
COPY defaults /workspace/tasks/craftax-singleplayer/defaults
RUN python -c "from containers.codepolicy.rust_repl_session import ensure_rust_repl_binary; ensure_rust_repl_binary()"

USER 65532:65532
ENTRYPOINT ["python", "-m", "containers.scorer_service.service"]
