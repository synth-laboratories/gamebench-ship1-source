FROM python@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
        libmgba0.10t64=0.10.5+dfsg-1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    mgba==0.10.2 \
    Pillow==11.3.0 \
    cached-property==2.0.1 \
    cffi==2.1.0 \
    pycparser==3.0

COPY mgba_jsonl_oracle.py /opt/gamebench/mgba_jsonl_oracle.py
COPY emerald_source_observability.py /opt/gamebench/emerald_source_observability.py

ENTRYPOINT ["python", "/opt/gamebench/mgba_jsonl_oracle.py"]
