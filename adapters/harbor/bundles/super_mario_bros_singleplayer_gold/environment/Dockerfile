FROM rust:1.85-slim-bookworm

WORKDIR /task

COPY harbor/super_mario_bros_singleplayer_gold/task.toml /task/task.toml
COPY harbor/super_mario_bros_singleplayer_gold/instruction.md /task/instruction.md
COPY harbor/super_mario_bros_singleplayer_gold/environment/setup_workspace.sh /task/environment/setup_workspace.sh
COPY harbor/super_mario_bros_singleplayer_gold/solution /task/solution
COPY harbor/super_mario_bros_singleplayer_gold/tests /task/tests
COPY harbor/super_mario_bros_singleplayer_gold/spec /task/spec
COPY tasks/super-mario-bros-singleplayer/gold_rust /task/reference/gold_rust
COPY tasks/super-mario-bros-singleplayer/scripts /task/reference/scripts

RUN chmod +x /task/environment/setup_workspace.sh /task/solution/solve.sh /task/tests/test.sh \
    && cargo test --manifest-path /task/reference/gold_rust/Cargo.toml

WORKDIR /workspace
CMD ["bash"]
