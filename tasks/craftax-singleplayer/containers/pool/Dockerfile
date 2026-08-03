# Craftax single-player, packaged as one container-pool deployment unit.
#
# Two services in one image: the Rust gold engine (sealed binary, no model, no
# egress) and the Python ReAct policy service that speaks the pool contract and
# calls a model. They are split by trust and dependency profile, not by
# convenience — the engine carries no credentials and no `synth-containers`
# wheel, while the policy carries both.
#
# One image rather than a two-container compose: the pool has to probe a single
# `/health`, and the engine is never addressable on its own here. Split them
# into a `docker_compose` service topology only when something outside this
# image needs to reach :8098 directly.
#
# BUILD CONTEXT IS THE TASK DIRECTORY, NOT THE CRATE.
# `native.rs::task_dir()` is `CARGO_MANIFEST_DIR/..`, baked in at compile time,
# so the binary reads `defaults/worlds.json` and friends from the crate's
# PARENT at runtime. A build from `gold_rust/` alone compiles clean and then
# 400s on its first rollout. `/build/craftax/defaults` must exist in the final
# image with the layout it had in the builder.
#
#   docker buildx build \
#     --build-context synth_containers=/path/to/wheel-context \
#     -f containers/pool/Dockerfile .
#
# linux/arm64 and linux/amd64 build natively; never under QEMU emulation.

# 1.83 cannot build this crate's lockfile: getrandom 0.4.x requires edition2024,
# stabilized in 1.85. Pinned to the toolchain the native lane is proven on.
ARG CRAFTAX_BUILDER_IMAGE=rust:1.93-bookworm
ARG CRAFTAX_POLICY_IMAGE=python:3.11-slim

# `synth-containers` is the Trace V5 authority and is supplied as the
# release-approved wheel from a named context — never a registry fallback.
# Bump both together; the sha is what makes the pin real.
ARG SYNTH_CONTAINERS_VERSION=0.4.0.20260730
ARG SYNTH_CONTAINERS_WHEEL_SHA256=b201f57d99ee3df7a92042b230d140d13f185a8fb83c982db09ccebf6a2d5764

FROM ${CRAFTAX_BUILDER_IMAGE} AS rust-builder

COPY . /build/craftax
RUN CARGO_TARGET_DIR=/build/target cargo build \
    --release \
    --locked \
    --quiet \
    --manifest-path /build/craftax/gold_rust/Cargo.toml \
    --bin craftax_gold

FROM ${CRAFTAX_POLICY_IMAGE}

ARG SYNTH_CONTAINERS_VERSION
ARG SYNTH_CONTAINERS_WHEEL_SHA256
ARG CRAFTAX_SOURCE_COMMIT
ARG CRAFTAX_SOURCE_SUBPATH

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY containers/react/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY --from=synth_containers /synth_containers-${SYNTH_CONTAINERS_VERSION}-py3-none-any.whl /tmp/synth_containers-${SYNTH_CONTAINERS_VERSION}-py3-none-any.whl
RUN echo "${SYNTH_CONTAINERS_WHEEL_SHA256}  /tmp/synth_containers-${SYNTH_CONTAINERS_VERSION}-py3-none-any.whl" | sha256sum --check --strict - \
    && python -m pip install --no-cache-dir /tmp/synth_containers-${SYNTH_CONTAINERS_VERSION}-py3-none-any.whl \
    && python -c "from importlib.metadata import version; \
assert version('synth-containers') == '${SYNTH_CONTAINERS_VERSION}', version('synth-containers')" \
    && rm /tmp/synth_containers-${SYNTH_CONTAINERS_VERSION}-py3-none-any.whl

# The engine binary, plus the runtime data it resolves relative to its
# compile-time task_dir. Both paths are load-bearing; see the header.
COPY --from=rust-builder /build/target/release/craftax_gold /usr/local/bin/craftax_gold
COPY --from=rust-builder /build/craftax/defaults /build/craftax/defaults

COPY . /app
COPY containers/pool/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

LABEL ai.synth.containers.version="${SYNTH_CONTAINERS_VERSION}"
LABEL ai.synth.containers.wheel_sha256="${SYNTH_CONTAINERS_WHEEL_SHA256}"
LABEL ai.synth.pool.task_family="craftax-singleplayer"
LABEL ai.synth.pool.source_repo="gamebench"
LABEL ai.synth.pool.source_commit="${CRAFTAX_SOURCE_COMMIT}"
LABEL ai.synth.pool.source_subpath="${CRAFTAX_SOURCE_SUBPATH}"

ENV PYTHONPATH=/app:/app/gold_python:/app/shared
ENV CRAFTAX_SOURCE_COMMIT=${CRAFTAX_SOURCE_COMMIT}
ENV CRAFTAX_GOLD_PORT=8098
ENV CRAFTAX_GOLD_HOST=127.0.0.1
# The Python client's own default is :8103, which is not where the engine
# binds. Pinned here so the image is correct without an env override.
ENV CRAFTAX_GOLD_URL=http://127.0.0.1:8098
ENV PORT=8104

# Only the policy service is exposed. The engine is an implementation detail of
# this image and must not be reachable from outside it.
EXPOSE 8104

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
