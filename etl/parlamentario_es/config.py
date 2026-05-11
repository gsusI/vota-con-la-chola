from __future__ import annotations

from pathlib import Path
from typing import Any

from publicdata_connectors_es.parliamentary import SOURCE_CONFIG as PARLIAMENTARY_SOURCE_CONFIG

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SCHEMA = Path("etl/load/sqlite_schema.sql")
DEFAULT_RAW_DIR = Path("etl/data/raw")
DEFAULT_TIMEOUT = 45

# Sources for parliamentary evidence (votes, initiatives, etc).
SOURCE_CONFIG: dict[str, dict[str, Any]] = {
    **PARLIAMENTARY_SOURCE_CONFIG,
    # Derived/backfill source: documents referenced by initiatives (BOCG/DS PDFs/HTML).
    "parl_initiative_docs": {
        "name": "Parlamento - Documentos de iniciativas (BOCG/Diario de Sesiones)",
        "scope": "nacional",
        "default_url": "manifest://parl_initiative_docs",
        "format": "bin",
        "level": "nacional",
        "institution_name": "Cortes Generales",
        "min_records_loaded_strict": 1,
        "fallback_file": "",
    },
}
