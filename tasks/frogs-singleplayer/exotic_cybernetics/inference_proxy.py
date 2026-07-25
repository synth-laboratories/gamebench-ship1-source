"""Inference proxy shim for frogs-singleplayer."""

import os

os.environ.setdefault("GAMEBENCH_CYBERNETICS_ENV_LABEL", "Frogs symbolic policy")

from shared.exotic_cybernetics.inference_proxy import *  # noqa: F403
