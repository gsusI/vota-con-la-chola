"""Compatibility wrapper for reusable Senado voting connector."""

from publicdata_connectors_es.parliamentary.senado_votaciones import *  # noqa: F401,F403
from publicdata_connectors_es.parliamentary.senado_votaciones import (  # noqa: F401
    _enrich_senado_record_with_details,
    _find_local_session_xml,
    _load_session_vote_info,
    _parse_sesion_vote_xml,
    _records_from_tipo12_xml,
    _session_vote_file_url_candidates,
    _tipo12_urls_from_tipo9_xml,
    _to_int,
)
