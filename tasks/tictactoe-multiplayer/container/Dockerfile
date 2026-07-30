FROM python:3.12-slim

WORKDIR /app

COPY tictactoe-multiplayer/container/requirements.txt /app/container/requirements.txt
RUN pip install --no-cache-dir -r /app/container/requirements.txt

COPY tictactoe-multiplayer/gold /app/gold
COPY tictactoe-multiplayer/container /app/container

ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8091
ENV GROQ_AGENT_0_MODEL=llama-3.3-70b-versatile
ENV GROQ_AGENT_1_MODEL=llama-3.1-8b-instant

EXPOSE 8091

CMD ["python", "/app/container/tictactoe_multiplayer_container.py"]
