"""Inference proxy shim for tictactoe-multiplayer."""

import os

os.environ.setdefault("GAMEBENCH_CYBERNETICS_ENV_LABEL", "Tic-Tac-Toe multiplayer symbolic policy")

from shared.exotic_cybernetics.inference_proxy import *  # noqa: F403
