"""Shared pytest hooks.

Real-data tests read gitignored local artifacts (``etl/data/staging/*.db``,
``etl/data/raw/official-captures/**``, ...). In a fresh clone or CI those
artifacts do not exist, so such a test is reported as *skipped* (with the
missing path) instead of failed. Only failures whose error message names a
missing ``etl/data/`` path are converted; every other failure still fails.

Set ``VCLC_REQUIRE_REAL_DATA=1`` to keep these as hard failures (maintainer
machines with the full local corpus).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DATA_PATH_RE = re.compile(r"etl/data/[^\s'\"`:,;()\[\]]+")


def _missing_local_data_path(error_lines: list[str]) -> str | None:
    for line in error_lines:
        for match in LOCAL_DATA_PATH_RE.finditer(line):
            candidate = match.group(0).rstrip(".")
            if not (REPO_ROOT / candidate).exists():
                return candidate
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if not report.failed or call.excinfo is None or os.environ.get("VCLC_REQUIRE_REAL_DATA") == "1":
        return
    # Only inspect the exception/assertion lines ("E   ..."), not test source lines.
    error_lines = [line for line in str(report.longrepr).splitlines() if line.startswith("E ")]
    missing = _missing_local_data_path(error_lines)
    if missing is None:
        return
    report.outcome = "skipped"
    report.longrepr = (str(item.path), item.location[1] or 0, f"Skipped: requires local real data missing here: {missing}")


QUARANTINE_FILE = Path(__file__).with_name("ci_quarantine.txt")


def pytest_collection_modifyitems(config, items):
    """With VCLC_CI_QUARANTINE=1, deselect the node ids listed in tests/ci_quarantine.txt.

    Entries name a reason; stale entries fail the run so the list only shrinks.
    """
    if os.environ.get("VCLC_CI_QUARANTINE") != "1":
        return
    quarantined = {
        line.split("#", 1)[0].strip() for line in QUARANTINE_FILE.read_text(encoding="utf-8").splitlines()
    } - {""}
    collected = {item.nodeid for item in items}
    stale = sorted(quarantined - collected)
    if stale:
        raise pytest.UsageError("Stale entries in tests/ci_quarantine.txt (remove them): " + ", ".join(stale))
    deselected = [item for item in items if item.nodeid in quarantined]
    items[:] = [item for item in items if item.nodeid not in quarantined]
    config.hook.pytest_deselected(items=deselected)
