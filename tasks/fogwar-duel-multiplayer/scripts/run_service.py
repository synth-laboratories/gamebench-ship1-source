#!/usr/bin/env python3
"""Start the Fog Duel Lite Python JSON-lines service on stdin/stdout."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gold_python.service import serve

serve()
