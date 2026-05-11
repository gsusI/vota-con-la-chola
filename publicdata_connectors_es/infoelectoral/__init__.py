from __future__ import annotations

from .config import INFOELECTORAL_BASE, SOURCE_CONFIG, SOURCE_DEFINITIONS
from .descargas import InfoelectoralDescargasConnector
from .procesos import InfoelectoralProcesosConnector

__all__ = [
    "INFOELECTORAL_BASE",
    "SOURCE_CONFIG",
    "SOURCE_DEFINITIONS",
    "InfoelectoralDescargasConnector",
    "InfoelectoralProcesosConnector",
]
