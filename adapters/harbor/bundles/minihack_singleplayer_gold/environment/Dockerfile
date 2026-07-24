FROM python:3.12-slim

RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /task

COPY harbor/sync_minihack_reference.sh /task/harbor/sync_minihack_reference.sh
COPY harbor/minihack_singleplayer_gold/task.toml /task/task.toml
COPY harbor/minihack_singleplayer_gold/instruction.md /task/instruction.md
COPY harbor/minihack_singleplayer_gold/environment/setup_workspace.sh /task/environment/setup_workspace.sh
COPY harbor/minihack_singleplayer_gold/solution /task/solution
COPY harbor/minihack_singleplayer_gold/tests /task/tests
COPY harbor/minihack_singleplayer_gold/spec /task/spec
COPY tasks/minihack-singleplayer/gold_python /task/reference/gold_python
COPY tasks/minihack-singleplayer/shared /task/reference/shared
COPY tasks/minihack-singleplayer/policies /task/reference/policies
COPY tasks/minihack-singleplayer/scripts/run_service.py /task/reference/scripts/run_service.py
COPY tasks/minihack-singleplayer/fixtures/gold /task/tests/fixtures/gold
COPY tasks/minihack-singleplayer/scripts/spectrum_eval.py /task/tests/spectrum_eval.py
COPY spec/spectrum_correctness.md /task/spec/spectrum_correctness.md
COPY spec/nev_log.md /task/spec/nev_log.md
COPY spec/checkpoint.md /task/spec/checkpoint.md
COPY spec/deterministic_tasks.md /task/spec/deterministic_tasks.md
COPY tasks/minihack-singleplayer/shared/http_contract.md /task/spec/http_protocol.md

RUN chmod +x /task/environment/setup_workspace.sh /task/solution/solve.sh /task/tests/test.sh

WORKDIR /workspace
CMD ["bash"]
