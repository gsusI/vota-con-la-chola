"""Compatibility wrapper for the reusable Infoelectoral downloads connector."""

from publicdata_connectors_es.infoelectoral.descargas import (
    InfoelectoralDescargasConnector,
    basic_auth_header,
    extract_ambito,
    parse_api_payload,
)

__all__ = [
    "InfoelectoralDescargasConnector",
    "basic_auth_header",
    "extract_ambito",
    "parse_api_payload",
]
