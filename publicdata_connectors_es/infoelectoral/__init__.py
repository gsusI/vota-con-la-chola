from __future__ import annotations

from .config import (
    INFOELECTORAL_BASE,
    INFOELECTORAL_CANDIDATE_CATALOG_URL,
    INFOELECTORAL_DATASET_BASE,
    INFOELECTORAL_ELECTED_CATALOG_URL,
    SOURCE_CONFIG,
    SOURCE_DEFINITIONS,
)
from .candidates import (
    CandidateArchiveMetrics,
    CandidateArchiveSpec,
    CandidateRecord,
    iter_candidate_archive,
)
from .descargas import InfoelectoralDescargasConnector
from .elected_officials import (
    ElectedOfficialRecord,
    ElectedWorkbookSpec,
    WORKBOOKS,
    iter_elected_officials,
)
from .procesos import InfoelectoralProcesosConnector

__all__ = [
    "INFOELECTORAL_BASE",
    "INFOELECTORAL_CANDIDATE_CATALOG_URL",
    "INFOELECTORAL_DATASET_BASE",
    "INFOELECTORAL_ELECTED_CATALOG_URL",
    "SOURCE_CONFIG",
    "SOURCE_DEFINITIONS",
    "InfoelectoralDescargasConnector",
    "InfoelectoralProcesosConnector",
    "CandidateArchiveSpec",
    "CandidateArchiveMetrics",
    "CandidateRecord",
    "ElectedOfficialRecord",
    "ElectedWorkbookSpec",
    "WORKBOOKS",
    "iter_elected_officials",
    "iter_candidate_archive",
]
