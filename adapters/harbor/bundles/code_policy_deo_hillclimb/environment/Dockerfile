FROM python:3.12-slim

ARG GAMEBENCH_TASK=tictactoe-singleplayer
ARG CANDIDATE_SUBDIR=tictactoe

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GAMEBENCH_TASK=${GAMEBENCH_TASK} \
    CANDIDATE_SUBDIR=${CANDIDATE_SUBDIR} \
    GAMEBENCH_WORKSPACE_ROOT=/workspace \
    GAMEBENCH_ROOT=/workspace/gamebench

RUN pip install --no-cache-dir httpx pydantic

WORKDIR /task

COPY adapters/harbor/bundles/code_policy_deo_hillclimb/task.toml /task/task.toml
COPY adapters/harbor/bundles/code_policy_deo_hillclimb/instruction.md /task/instruction.md
COPY adapters/harbor/bundles/code_policy_deo_hillclimb/environment/setup_workspace.sh /task/environment/setup_workspace.sh
COPY adapters/harbor/bundles/code_policy_deo_hillclimb/solution /task/solution
COPY adapters/harbor/bundles/code_policy_deo_hillclimb/tests/test.sh /task/tests/test.sh
COPY adapters/harbor/bundles/code_policy_deo_hillclimb/tests/score_hillclimb.py /task/tests/score_hillclimb.py

COPY adapters/harbor/bundles/code_policy_deo_hillclimb/files/run_gamebench_hillclimb_task.py /workspace/workspace/run_gamebench_hillclimb_task.py

COPY tasks/${GAMEBENCH_TASK} /workspace/gamebench/tasks/${GAMEBENCH_TASK}
# Singleplayer TTT gold imports board.py from the multiplayer task lane.
COPY tasks/tictactoe-multiplayer/gold/board.py /workspace/gamebench/tasks/tictactoe-singleplayer/gold/board.py

RUN chmod +x /task/environment/setup_workspace.sh /task/solution/solve.sh /task/tests/test.sh

WORKDIR /workspace
CMD ["bash"]
