ARG SCORER_BASE_IMAGE
FROM ${SCORER_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONNOUSERSITE=1
ENV PYTHONUNBUFFERED=1

LABEL ai.synth.gamebench.runtime.security-context="seccomp=unconfined,cap-drop=ALL,no-new-privileges"

RUN apt-get update \
    && apt-get install --yes --no-install-recommends bubblewrap \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY containers/scorer_service/requirements.txt /tmp/scorer-requirements.txt
RUN python -m pip install --no-cache-dir --requirement /tmp/scorer-requirements.txt

COPY . /app
ENV PYTHONPATH=/app

RUN python -c "from containers.codepolicy.rust_repl_session import ensure_rust_repl_binary; ensure_rust_repl_binary()"

USER 65532:65532
ENTRYPOINT ["python", "-m", "containers.scorer_service.service"]
