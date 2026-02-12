from __future__ import annotations

from .connectors import InfoelectoralDescargasConnector


def get_connectors() -> dict[str, InfoelectoralDescargasConnector]:
    connectors = [
        InfoelectoralDescargasConnector(),
    ]
    return {c.source_id: c for c in connectors}

