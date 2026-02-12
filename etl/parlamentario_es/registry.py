from __future__ import annotations

from .connectors import (
    CongresoIniciativasConnector,
    CongresoVotacionesConnector,
    SenadoIniciativasConnector,
    SenadoVotacionesConnector,
)
from .connectors.base import BaseConnector


def get_connectors() -> dict[str, BaseConnector]:
    connectors: list[BaseConnector] = [
        CongresoVotacionesConnector(),
        CongresoIniciativasConnector(),
        SenadoIniciativasConnector(),
        SenadoVotacionesConnector(),
    ]
    return {c.source_id: c for c in connectors}
