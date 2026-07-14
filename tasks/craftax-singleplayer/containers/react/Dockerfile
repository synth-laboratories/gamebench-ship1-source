FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8104

WORKDIR /app

COPY containers/react/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app

ENV PYTHONPATH=/app:/app/gold_python:/app/shared

EXPOSE 8104

CMD ["python", "-m", "containers.react.craftax_singleplayer_container"]
