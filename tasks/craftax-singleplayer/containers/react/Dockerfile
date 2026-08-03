FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8104

WORKDIR /app

COPY containers/react/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

# The Trace V5 emitter is supplied as the release-approved wheel, never from a
# mutable checkout or registry fallback. The named context must contain the
# canonical artifact at
# /synth_containers-0.4.0.20260730-py3-none-any.whl:
#   docker buildx build \
#     --build-context synth_containers=/path/to/wheel-context \
#     -f containers/react/Dockerfile .
COPY --from=synth_containers /synth_containers-0.4.0.20260730-py3-none-any.whl /tmp/synth_containers-0.4.0.20260730-py3-none-any.whl
RUN echo "b201f57d99ee3df7a92042b230d140d13f185a8fb83c982db09ccebf6a2d5764  /tmp/synth_containers-0.4.0.20260730-py3-none-any.whl" \
    | sha256sum --check --strict - \
    && python -m pip install --no-cache-dir /tmp/synth_containers-0.4.0.20260730-py3-none-any.whl \
    && python -c "from importlib.metadata import version; assert version('synth-containers') == '0.4.0.20260730'"

LABEL ai.synth.containers.version="0.4.0.20260730"
LABEL ai.synth.containers.source_commit="286832c80715fa8f2339b56bedc7ee07a19cf48a"
LABEL ai.synth.containers.wheel_sha256="b201f57d99ee3df7a92042b230d140d13f185a8fb83c982db09ccebf6a2d5764"

COPY . /app

ENV PYTHONPATH=/app:/app/gold_python:/app/shared

EXPOSE 8104

CMD ["python", "-m", "containers.react.craftax_singleplayer_container"]
