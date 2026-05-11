from __future__ import annotations

from .aemet_indicators import (
    AEMET_DEFAULT_URL,
    SOURCE_CONFIG as AEMET_SOURCE_CONFIG,
    SOURCE_DEFINITIONS as AEMET_SOURCE_DEFINITIONS,
    AemetOpenDataSeriesConnector,
    parse_aemet_records,
)
from .bde_series import (
    BDE_SERIES_DEFAULT_URL,
    SOURCE_CONFIG as BDE_SOURCE_CONFIG,
    SOURCE_DEFINITIONS as BDE_SOURCE_DEFINITIONS,
    BdeSeriesApiConnector,
    parse_bde_records,
)
from .eurostat_indicators import (
    EUROSTAT_DEFAULT_URL,
    SOURCE_CONFIG as EUROSTAT_SOURCE_CONFIG,
    SOURCE_DEFINITIONS as EUROSTAT_SOURCE_DEFINITIONS,
    EurostatSdmxConnector,
    parse_eurostat_records,
)
from .ree_esios_indicators import (
    REE_ESIOS_DEFAULT_URL,
    SOURCE_CONFIG as REE_SOURCE_CONFIG,
    SOURCE_DEFINITIONS as REE_SOURCE_DEFINITIONS,
    ReeEsiosIndicatorsConnector,
    parse_ree_records,
)

SOURCE_DEFINITIONS = (
    *AEMET_SOURCE_DEFINITIONS,
    *BDE_SOURCE_DEFINITIONS,
    *EUROSTAT_SOURCE_DEFINITIONS,
    *REE_SOURCE_DEFINITIONS,
)
SOURCE_CONFIG = {
    **AEMET_SOURCE_CONFIG,
    **BDE_SOURCE_CONFIG,
    **EUROSTAT_SOURCE_CONFIG,
    **REE_SOURCE_CONFIG,
}

__all__ = [
    "AEMET_DEFAULT_URL",
    "BDE_SERIES_DEFAULT_URL",
    "EUROSTAT_DEFAULT_URL",
    "REE_ESIOS_DEFAULT_URL",
    "SOURCE_CONFIG",
    "SOURCE_DEFINITIONS",
    "AemetOpenDataSeriesConnector",
    "BdeSeriesApiConnector",
    "EurostatSdmxConnector",
    "ReeEsiosIndicatorsConnector",
    "parse_aemet_records",
    "parse_bde_records",
    "parse_eurostat_records",
    "parse_ree_records",
]
