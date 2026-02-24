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
    },
    "senado_votaciones": {
        "name": "Senado - Votaciones (OpenData)",
        "scope": "nacional",
        "default_url": "https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/votaciones/index.html?legis=15",
        "format": "html",  # catalog page is HTML; vote references are XML (tipoFich=12)
        "level": "nacional",
        "institution_name": "Senado de Espana",
        "min_records_loaded_strict": 1,
        "fallback_file": "etl/data/raw/samples/senado_votaciones_sample.xml",
    },
    "senado_iniciativas": {
        "name": "Senado - Iniciativas y mociones (OpenData)",
        "scope": "nacional",
        "default_url": "https://www.senado.es/web/ficopendataservlet?tipoFich=9&legis=15",
        "format": "xml",  # lista de iniciativas legislativas con referencias de votacion
        "level": "nacional",
        "institution_name": "Senado de Espana",
        "min_records_loaded_strict": 1,
        "fallback_file": "etl/data/raw/samples/senado_iniciativas_sample.xml",
    },
    "congreso_iniciativas": {
        "name": "Congreso - Iniciativas (OpenData)",
        "scope": "nacional",
        "default_url": "https://www.congreso.es/es/opendata/iniciativas",
        "format": "html",  # catalog page is HTML; exports are JSON/CSV/XML
        "level": "nacional",
        "institution_name": "Congreso de los Diputados",
        "min_records_loaded_strict": 1,
        "fallback_file": "etl/data/raw/samples/congreso_iniciativas_sample.json",
    },
    "congreso_intervenciones": {
        "name": "Congreso - Intervenciones (OpenData)",
        "scope": "nacional",
        "default_url": "https://www.congreso.es/es/opendata/intervenciones",
        "format": "html",  # catalog page is HTML; exports are JSON
        "level": "nacional",
        "institution_name": "Congreso de los Diputados",
        "min_records_loaded_strict": 1,
        "fallback_file": "etl/data/raw/samples/congreso_intervenciones_sample.json",
    },
    "programas_partidos": {
        "name": "Programas de partidos (manifest-driven)",
        "scope": "nacional",
        "default_url": "manifest://programas_partidos",
        "format": "csv",
        "level": "nacional",
        "institution_name": "Programas de partidos",
        "min_records_loaded_strict": 1,
        "fallback_file": "etl/data/raw/samples/programas_partidos_sample.csv",
    },
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
