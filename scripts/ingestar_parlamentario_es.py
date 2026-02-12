#!/usr/bin/env python3
"""Wrapper CLI.

Keep this path stable because it is referenced by `justfile` and docs.
The implementation lives in `etl.parlamentario_es.cli`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is importable when executing this file directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

