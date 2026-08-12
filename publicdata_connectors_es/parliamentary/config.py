from __future__ import annotations

from typing import Any

from publicdata_core.sources import SourceDefinition, source_config_mapping

SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        source_id="congreso_votaciones",
        name="Congreso - Votaciones (pleno, OpenData)",
        scope="nacional",
        default_url="https://www.congreso.es/es/opendata/votaciones",
        format="html",
        fallback_file="etl/data/raw/samples/congreso_votaciones_sample.json",
        min_records_loaded_strict=1,
        metadata={"level": "nacional", "institution_name": "Congreso de los Diputados"},
    ),
    SourceDefinition(
        source_id="senado_votaciones",
        name="Senado - Votaciones (OpenData)",
        scope="nacional",
        default_url="https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/votaciones/index.html?legis=15",
        format="html",
        fallback_file="etl/data/raw/samples/senado_votaciones_sample.xml",
        min_records_loaded_strict=1,
        metadata={"level": "nacional", "institution_name": "Senado de Espana"},
    ),
    SourceDefinition(
        source_id="senado_iniciativas",
        name="Senado - Iniciativas y mociones (OpenData)",
        scope="nacional",
        default_url="https://www.senado.es/web/ficopendataservlet?tipoFich=9&legis=15",
        format="xml",
        fallback_file="etl/data/raw/samples/senado_iniciativas_sample.xml",
        min_records_loaded_strict=1,
        metadata={"level": "nacional", "institution_name": "Senado de Espana"},
    ),
    SourceDefinition(
        source_id="congreso_iniciativas",
        name="Congreso - Iniciativas (OpenData)",
        scope="nacional",
        default_url="https://www.congreso.es/es/opendata/iniciativas",
        format="html",
        fallback_file="etl/data/raw/samples/congreso_iniciativas_sample.json",
        min_records_loaded_strict=1,
        metadata={"level": "nacional", "institution_name": "Congreso de los Diputados"},
    ),
    SourceDefinition(
        source_id="congreso_intervenciones",
        name="Congreso - Intervenciones (OpenData)",
        scope="nacional",
        default_url="https://www.congreso.es/es/opendata/intervenciones",
        format="html",
        fallback_file="etl/data/raw/samples/congreso_intervenciones_sample.json",
        min_records_loaded_strict=1,
        metadata={"level": "nacional", "institution_name": "Congreso de los Diputados"},
    ),
    SourceDefinition(
        source_id="programas_partidos",
        name="Programas de partidos (manifest-driven)",
        scope="nacional",
        default_url="manifest://programas_partidos",
        format="csv",
        fallback_file="",
        min_records_loaded_strict=1,
        metadata={"level": "nacional", "institution_name": "Programas de partidos"},
    ),
)

SOURCE_CONFIG: dict[str, dict[str, Any]] = source_config_mapping(SOURCE_DEFINITIONS)
