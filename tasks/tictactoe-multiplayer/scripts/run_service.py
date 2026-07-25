#!/usr/bin/env python3
"""Start the multiplayer Tic-Tac-Toe gold HTTP service."""

from __future__ import annotations

import os

import uvicorn

from gold.service import create_app


def main() -> None:
    host = os.environ.get("GAMEBENCH_TTT_HOST", "127.0.0.1")
    port = int(os.environ.get("GAMEBENCH_TTT_PORT", "8082"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
