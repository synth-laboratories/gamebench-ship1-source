FROM python:3.12-slim

RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /task

COPY harbor/sync_overcooked_v2_reference.sh /task/harbor/sync_overcooked_v2_reference.sh
COPY harbor/overcooked_v2_multiplayer_gold/task.toml /task/task.toml
COPY harbor/overcooked_v2_multiplayer_gold/instruction.md /task/instruction.md
COPY harbor/overcooked_v2_multiplayer_gold/environment/setup_workspace.sh /task/environment/setup_workspace.sh
COPY harbor/overcooked_v2_multiplayer_gold/solution /task/solution
COPY harbor/overcooked_v2_multiplayer_gold/tests /task/tests
COPY harbor/overcooked_v2_multiplayer_gold/spec /task/spec
COPY tasks/overcooked-v2-multiplayer/gold_python /task/reference/gold_python
COPY tasks/overcooked-v2-multiplayer/shared /task/reference/shared
COPY tasks/overcooked-v2-multiplayer/policies /task/reference/policies
COPY tasks/overcooked-v2-multiplayer/scripts/run_service.py /task/reference/scripts/run_service.py
COPY tasks/overcooked-v2-multiplayer/fixtures/gold /task/tests/fixtures/gold
COPY tasks/overcooked-v2-multiplayer/scripts/spectrum_eval.py /task/tests/spectrum_eval.py
COPY spec/spectrum_correctness.md /task/spec/spectrum_correctness.md
COPY spec/nev_log.md /task/spec/nev_log.md
COPY spec/checkpoint.md /task/spec/checkpoint.md
COPY spec/deterministic_tasks.md /task/spec/deterministic_tasks.md
COPY spec/marl_env_standards.md /task/spec/marl_env_standards.md

RUN chmod +x /task/environment/setup_workspace.sh /task/solution/solve.sh /task/tests/test.sh

WORKDIR /workspace
CMD ["bash"]
