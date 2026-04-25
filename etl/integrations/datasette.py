"""Helpers for running Datasette against the project SQLite."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TITLE = "Vota con la Chola Explorer"


def ensure_datasette_installed() -> None:
    try:
        __import__("datasette")
    except ImportError as exc:  # pragma: no cover - runtime guard
        raise RuntimeError("Datasette not installed. Run: pip install -r requirements-explorer.txt") from exc


def build_metadata(db_path: Path) -> dict[str, Any]:
    database_name = db_path.stem
    return {
        "title": DEFAULT_TITLE,
        "source": "vota-con-la-chola",
        "source_url": "https://github.com/jesus/vota-con-la-chola",
        "about": "Generic SQLite browse surface powered by Datasette.",
        "databases": {
            database_name: {
                "description": "Thin generic explorer for the project SQLite. Prefer this for schema-first browsing; keep custom app routes for domain drill-downs.",
                "queries": {
                    "foreign_key_check": {
                        "sql": "PRAGMA foreign_key_check;",
                        "description": "Quick integrity check for the loaded snapshot.",
                    },
                    "recent_ingestion_runs": {
                        "sql": "select run_id, source_id, status, records_seen, records_loaded, started_at, finished_at from ingestion_runs order by run_id desc limit 200",
                        "description": "Latest ingestion runs across all sources.",
                    },
                },
            }
        },
    }


def write_metadata(db_path: Path, out_path: Path) -> Path:
    metadata = build_metadata(db_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def datasette_command(db_path: Path, *, host: str, port: int, metadata_path: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "datasette",
        "serve",
        str(db_path),
        "--host",
        host,
        "--port",
        str(int(port)),
        "--metadata",
        str(metadata_path),
        "--setting",
        "default_allow_sql",
        "off",
        "--setting",
        "default_page_size",
        "50",
        "--setting",
        "max_returned_rows",
        "2000",
        "--setting",
        "sql_time_limit_ms",
        "3500",
    ]


def run_datasette(db_path: Path, *, host: str, port: int, metadata_path: Path | None = None) -> int:
    ensure_datasette_installed()
    resolved_metadata_path = metadata_path
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if resolved_metadata_path is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="datasette-config-")
        resolved_metadata_path = Path(temp_dir.name) / "metadata.json"
    write_metadata(db_path, resolved_metadata_path)
    try:
        command = datasette_command(db_path, host=host, port=port, metadata_path=resolved_metadata_path)
        return subprocess.run(command, cwd=str(REPO_ROOT), check=False).returncode
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
