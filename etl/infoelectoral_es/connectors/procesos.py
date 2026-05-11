"""Compatibility wrapper for the reusable Infoelectoral process connector."""

from publicdata_connectors_es.infoelectoral.procesos import (
    InfoelectoralProcesosConnector,
    basic_auth_header,
    parse_api_payload,
)

__all__ = [
    "InfoelectoralProcesosConnector",
    "basic_auth_header",
    "parse_api_payload",
]
