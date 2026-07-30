FROM python:3.12-slim

RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /task

COPY runtime /task/runtime
COPY harbor/tictactoe_multiplayer_gold/task.toml /task/task.toml
COPY harbor/tictactoe_multiplayer_gold/instruction.md /task/instruction.md
COPY harbor/tictactoe_multiplayer_gold/environment/setup_workspace.sh /task/environment/setup_workspace.sh
COPY harbor/tictactoe_multiplayer_gold/solution /task/solution
COPY harbor/tictactoe_multiplayer_gold/tests /task/tests
COPY harbor/tictactoe_multiplayer_gold/spec /task/spec
COPY tasks/tictactoe-multiplayer/gold /task/reference/gold
COPY tasks/tictactoe-multiplayer/gold/board.py /task/reference/gold/board.py
COPY tasks/tictactoe-multiplayer/policies /task/reference/policies
COPY tasks/tictactoe-multiplayer/scripts/run_service.py /task/reference/scripts/run_service.py
COPY tasks/tictactoe-multiplayer/fixtures/gold /task/tests/fixtures/gold
COPY tasks/tictactoe-multiplayer/scripts/spectrum_eval.py /task/tests/spectrum_eval.py

RUN chmod +x /task/environment/setup_workspace.sh /task/solution/solve.sh /task/tests/test.sh

WORKDIR /workspace
CMD ["bash"]
