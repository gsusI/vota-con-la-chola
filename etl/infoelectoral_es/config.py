from __future__ import annotations

from typing import Any

DEFAULT_TIMEOUT = 20
DEFAULT_DB = "etl/data/staging/politicos-es.db"
DEFAULT_RAW_DIR = "etl/data/raw"
DEFAULT_SCHEMA = "etl/load/sqlite_schema.sql"

INFOELECTORAL_BASE = "https://infoelectoral.interior.gob.es/min/"

SOURCE_CONFIG: dict[str, dict[str, Any]] = {
    "infoelectoral_descargas": {
        "name": "Infoelectoral - Area de descargas (convocatorias + archivos)",
        "scope": "electoral",
        "default_url": f"{INFOELECTORAL_BASE}convocatorias/tipos/",
        "format": "json",
        # Se usa para tests / alternativa controlada cuando no hay red.
        "fallback_file": "etl/data/raw/samples/infoelectoral_descargas_sample.json",
        # Guardarrail basico: aunque cambie el catalogo, deberia haber tipos.
        "min_records_loaded_strict": 3,
    },
    "infoelectoral_procesos": {
        "name": "Infoelectoral - Procesos electorales celebrados (datos/resultados)",
        "scope": "electoral",
        "default_url": f"{INFOELECTORAL_BASE}procesos/",
        "format": "json",
        # Muestra reducida para pipeline determinista.
        "fallback_file": "etl/data/raw/samples/infoelectoral_procesos_sample.json",
        # Guardarrail basico: debe existir al menos un proceso catalogado.
        "min_records_loaded_strict": 1,
    },
}
