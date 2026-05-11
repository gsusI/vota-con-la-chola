from __future__ import annotations

from publicdata_core.sources import SourceDefinition, source_config_mapping


SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    # add-source:definitions:start
    # add-source:definitions:end
)

SOURCE_CONFIG = source_config_mapping(SOURCE_DEFINITIONS)
