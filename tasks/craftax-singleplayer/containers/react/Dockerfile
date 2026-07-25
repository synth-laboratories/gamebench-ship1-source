FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8104

WORKDIR /app

COPY containers/react/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

# The Trace V5 emitter is supplied as the release-approved wheel, never from a
# mutable checkout or registry fallback. The named context must contain the
# canonical artifact at /synth_containers.whl:
#   docker buildx build \
#     --build-context synth_containers=/path/to/wheel-context \
#     -f containers/react/Dockerfile .
COPY --from=synth_containers /synth_containers.whl /tmp/synth_containers.whl
RUN echo "1eafbca64b40c84c8c9d2554e68c8115605eea971444a378ca1d738fc39f61ee  /tmp/synth_containers.whl" \
        | sha256sum --check --strict - \
    && python -m pip install --no-cache-dir /tmp/synth_containers.whl \
    && python -c "from importlib.metadata import version; assert version('synth-containers') == '0.3.0.20260725'"

COPY . /app

ENV PYTHONPATH=/app:/app/gold_python:/app/shared

EXPOSE 8104

CMD ["python", "-m", "containers.react.craftax_singleplayer_container"]
