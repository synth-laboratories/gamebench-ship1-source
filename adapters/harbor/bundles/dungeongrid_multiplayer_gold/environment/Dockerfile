FROM rust:1.82-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /task

COPY harbor/dungeongrid_multiplayer_gold/task.toml /task/task.toml
COPY harbor/dungeongrid_multiplayer_gold/instruction.md /task/instruction.md
COPY harbor/dungeongrid_multiplayer_gold/environment/setup_workspace.sh /task/environment/setup_workspace.sh
COPY harbor/dungeongrid_multiplayer_gold/solution /task/solution
COPY harbor/dungeongrid_multiplayer_gold/tests /task/tests
COPY tasks/dungeongrid-multiplayer /task/reference/dungeongrid-multiplayer

RUN chmod +x /task/environment/setup_workspace.sh /task/solution/solve.sh /task/tests/test.sh

WORKDIR /workspace
CMD ["bash"]
