#!/usr/bin/env python3
"""Fail when public artifacts contain local-path or email leaks."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.privacy import *  # noqa: F403
from publicdata_publish.privacy import main


if __name__ == "__main__":
    raise SystemExit(main())
