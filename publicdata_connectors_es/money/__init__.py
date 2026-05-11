from __future__ import annotations

from .bdns_subsidies import (
    BDNS_BASE,
    BDNS_DEFAULT_URL,
    SOURCE_CONFIG as BDNS_SOURCE_CONFIG,
    SOURCE_DEFINITIONS as BDNS_SOURCE_DEFINITIONS,
    BdnsApiSubvencionesConnector,
    BdnsAutonomicoConnector,
    parse_bdns_records,
)
from .placsp_contracts import (
    PLACSP_BASE,
    PLACSP_DEFAULT_URL,
    SOURCE_CONFIG as PLACSP_SOURCE_CONFIG,
    SOURCE_DEFINITIONS as PLACSP_SOURCE_DEFINITIONS,
    PlacspAutonomicoConnector,
    PlacspSindicacionConnector,
    parse_placsp_atom_entries,
)

SOURCE_DEFINITIONS = (*BDNS_SOURCE_DEFINITIONS, *PLACSP_SOURCE_DEFINITIONS)
SOURCE_CONFIG = {**BDNS_SOURCE_CONFIG, **PLACSP_SOURCE_CONFIG}

__all__ = [
    "BDNS_BASE",
    "BDNS_DEFAULT_URL",
    "PLACSP_BASE",
    "PLACSP_DEFAULT_URL",
    "SOURCE_CONFIG",
    "SOURCE_DEFINITIONS",
    "BdnsApiSubvencionesConnector",
    "BdnsAutonomicoConnector",
    "PlacspAutonomicoConnector",
    "PlacspSindicacionConnector",
    "parse_bdns_records",
    "parse_placsp_atom_entries",
]
