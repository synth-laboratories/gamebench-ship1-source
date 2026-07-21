"""Inference proxy shim for rogue-singleplayer."""

import os

os.environ.setdefault("GAMEBENCH_CYBERNETICS_ENV_LABEL", "Rogue symbolic policy")

from shared.exotic_cybernetics.inference_proxy import *  # noqa: F403
