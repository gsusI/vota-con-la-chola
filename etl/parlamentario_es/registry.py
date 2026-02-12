from __future__ import annotations

from .connectors import CongresoVotacionesConnector
from .connectors.base import BaseConnector


def get_connectors() -> dict[str, BaseConnector]:
    connectors: list[BaseConnector] = [CongresoVotacionesConnector()]
    return {c.source_id: c for c in connectors}
