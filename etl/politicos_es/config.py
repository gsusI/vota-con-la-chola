from __future__ import annotations

from pathlib import Path
from typing import Any

from publicdata_connectors_es.government import SOURCE_CONFIG as GOVERNMENT_SOURCE_CONFIG
from publicdata_connectors_es.contrib import SOURCE_CONFIG as CONTRIB_SOURCE_CONFIG
from publicdata_connectors_es.money import SOURCE_CONFIG as MONEY_SOURCE_CONFIG
from publicdata_connectors_es.org import SOURCE_CONFIG as ORG_SOURCE_CONFIG
from publicdata_connectors_es.outcomes import SOURCE_CONFIG as OUTCOME_SOURCE_CONFIG
from publicdata_connectors_es.representatives import SOURCE_CONFIG as REPRESENTATIVE_SOURCE_CONFIG

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SCHEMA = Path("etl/load/sqlite_schema.sql")
DEFAULT_RAW_DIR = Path("etl/data/raw")
DEFAULT_TIMEOUT = 45

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

SPAIN_COUNTRY_NAMES = {"spain", "espana", "españa", "es"}

# Minimal metadata per source. Extraction/normalization live in connector modules.
SOURCE_CONFIG: dict[str, dict[str, Any]] = {
    **REPRESENTATIVE_SOURCE_CONFIG,
    **GOVERNMENT_SOURCE_CONFIG,
    **ORG_SOURCE_CONFIG,
    # AI-OPS-09 source_id naming contract (money/outcomes expansion).
    # Keep these ids stable: tracker mapping and strict-gate reconciliation depend on them.
    **MONEY_SOURCE_CONFIG,
    # Canonical mapped action sources for policy_events (output layer, no direct connector).
    "placsp_contratacion": {
        "name": "Contratacion publica (canonico policy_events)",
        "scope": "dinero",
        "default_url": "https://contrataciondelestado.es/",
        "format": "json",
        "min_records_loaded_strict": 0,
        "fallback_file": "",
    },
    "bdns_subvenciones": {
        "name": "Subvenciones publicas (canonico policy_events)",
        "scope": "dinero",
        "default_url": "https://www.pap.hacienda.gob.es/bdnstrans/GE/es/convocatorias",
        "format": "json",
        "min_records_loaded_strict": 0,
        "fallback_file": "",
    },
    **OUTCOME_SOURCE_CONFIG,
    **CONTRIB_SOURCE_CONFIG,
}
