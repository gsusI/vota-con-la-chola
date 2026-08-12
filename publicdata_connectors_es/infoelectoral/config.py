from __future__ import annotations

from publicdata_core.sources import SourceDefinition, source_config_mapping

INFOELECTORAL_BASE = "https://infoelectoral.interior.gob.es/min/"
INFOELECTORAL_DATASET_BASE = "https://descargas.interior.gob.es/datasets/"
INFOELECTORAL_ELECTED_CATALOG_URL = (
    "https://datos.gob.es/es/catalogo/e00003801-resultados-electorales1"
)
INFOELECTORAL_CANDIDATE_CATALOG_URL = (
    "https://infoelectoral.interior.gob.es/es/elecciones-celebradas/"
    "area-de-descargas/index.html"
)

SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        source_id="infoelectoral_descargas",
        name="Infoelectoral - Area de descargas (convocatorias + archivos)",
        scope="electoral",
        default_url=f"{INFOELECTORAL_BASE}convocatorias/tipos/",
        format="json",
        fallback_file="",
        min_records_loaded_strict=3,
    ),
    SourceDefinition(
        source_id="infoelectoral_procesos",
        name="Infoelectoral - Procesos electorales celebrados (datos/resultados)",
        scope="electoral",
        default_url=f"{INFOELECTORAL_BASE}procesos/",
        format="json",
        fallback_file="",
        min_records_loaded_strict=1,
    ),
    SourceDefinition(
        source_id="infoelectoral_elected_officials",
        name="Infoelectoral - cargos electos historicos",
        scope="electoral",
        default_url=INFOELECTORAL_ELECTED_CATALOG_URL,
        format="xlsx",
        # Real-only lane: an unavailable official workbook is a blocker, never
        # a reason to ingest generated identities.
        fallback_file="",
        min_records_loaded_strict=1,
    ),
    SourceDefinition(
        source_id="infoelectoral_candidates",
        name="Infoelectoral - candidaturas nominales historicas",
        scope="electoral",
        default_url=INFOELECTORAL_CANDIDATE_CATALOG_URL,
        format="zip-fixed-width",
        # Real-only lane: no generated candidate fallback is permitted.
        fallback_file="",
        min_records_loaded_strict=1,
    ),
)

SOURCE_CONFIG = source_config_mapping(SOURCE_DEFINITIONS)
