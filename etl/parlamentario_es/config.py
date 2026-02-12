from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SCHEMA = Path("etl/load/sqlite_schema.sql")
DEFAULT_RAW_DIR = Path("etl/data/raw")
DEFAULT_TIMEOUT = 45

# Sources for parliamentary evidence (votes, initiatives, etc).
SOURCE_CONFIG: dict[str, dict[str, Any]] = {
    "congreso_votaciones": {
        "name": "Congreso - Votaciones (pleno, OpenData)",
        "scope": "nacional",
        "default_url": "https://www.congreso.es/es/opendata/votaciones",
        "format": "html",  # catalog page is HTML; detail pages are JSON/XML/PDF
        "level": "nacional",
        "institution_name": "Congreso de los Diputados",
        "min_records_loaded_strict": 1,
        "fallback_file": "etl/data/raw/samples/congreso_votaciones_sample.json",
    }
}

