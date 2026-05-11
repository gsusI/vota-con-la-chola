from __future__ import annotations

from publicdata_core.sources import SourceDefinition, source_config_mapping

INFOELECTORAL_BASE = "https://infoelectoral.interior.gob.es/min/"

SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        source_id="infoelectoral_descargas",
        name="Infoelectoral - Area de descargas (convocatorias + archivos)",
        scope="electoral",
        default_url=f"{INFOELECTORAL_BASE}convocatorias/tipos/",
        format="json",
        fallback_file="etl/data/raw/samples/infoelectoral_descargas_sample.json",
        min_records_loaded_strict=3,
    ),
    SourceDefinition(
        source_id="infoelectoral_procesos",
        name="Infoelectoral - Procesos electorales celebrados (datos/resultados)",
        scope="electoral",
        default_url=f"{INFOELECTORAL_BASE}procesos/",
        format="json",
        fallback_file="etl/data/raw/samples/infoelectoral_procesos_sample.json",
        min_records_loaded_strict=1,
    ),
)

SOURCE_CONFIG = source_config_mapping(SOURCE_DEFINITIONS)
