from __future__ import annotations

from .boe_legal import (
    BOE_BASE,
    BOE_RSS_URL,
    SOURCE_CONFIG as BOE_SOURCE_CONFIG,
    SOURCE_DEFINITIONS as BOE_SOURCE_DEFINITIONS,
    BoeApiLegalConnector,
    parse_boe_rss_items,
)
from .moncloa_exec import (
    MONCLOA_BASE,
    MONCLOA_REFERENCIAS_INDEX_URL,
    MONCLOA_RSS_TIPO15_URL,
    MONCLOA_RSS_TIPO16_URL,
    SOURCE_CONFIG as MONCLOA_SOURCE_CONFIG,
    SOURCE_DEFINITIONS as MONCLOA_SOURCE_DEFINITIONS,
    MoncloaReferenciasConnector,
    MoncloaRssReferenciasConnector,
    parse_referencias_from_dir,
    parse_rss_from_dir,
)

SOURCE_DEFINITIONS = (*BOE_SOURCE_DEFINITIONS, *MONCLOA_SOURCE_DEFINITIONS)
SOURCE_CONFIG = {**BOE_SOURCE_CONFIG, **MONCLOA_SOURCE_CONFIG}

__all__ = [
    "BOE_BASE",
    "BOE_RSS_URL",
    "MONCLOA_BASE",
    "MONCLOA_REFERENCIAS_INDEX_URL",
    "MONCLOA_RSS_TIPO15_URL",
    "MONCLOA_RSS_TIPO16_URL",
    "SOURCE_CONFIG",
    "SOURCE_DEFINITIONS",
    "BoeApiLegalConnector",
    "MoncloaReferenciasConnector",
    "MoncloaRssReferenciasConnector",
    "parse_boe_rss_items",
    "parse_referencias_from_dir",
    "parse_rss_from_dir",
]
