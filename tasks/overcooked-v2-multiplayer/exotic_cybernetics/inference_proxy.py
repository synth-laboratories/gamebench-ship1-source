"""Inference proxy shim for overcooked-v2-multiplayer."""

import os

os.environ.setdefault("GAMEBENCH_CYBERNETICS_ENV_LABEL", "Overcooked v2 joint symbolic policy")

from shared.exotic_cybernetics.inference_proxy import *  # noqa: F403
