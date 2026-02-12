from __future__ import annotations

from .connectors import CongresoVotacionesConnector


def get_connectors() -> dict[str, object]:
    connectors = [CongresoVotacionesConnector()]
    return {c.source_id: c for c in connectors}

