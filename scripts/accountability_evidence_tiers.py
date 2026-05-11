"""Shared evidence-tier rules for accountability ledger backfills."""

from __future__ import annotations

from etl.politicos_es.util import normalize_key_part


PRIMARY_RECORD_TIER = 1
OFFICIAL_STRUCTURED_TIER = 2
OFFICIAL_COMMUNICATION_TIER = 3


def _key_is_or_startswith(key: str, prefixes: tuple[str, ...]) -> bool:
    return any(key == prefix or key.startswith(f"{prefix} ") for prefix in prefixes)


def infer_accountability_evidence_tier(
    *,
    source_id: str = "",
    source_url: str = "",
    source_title: str = "",
    instrument_code: str = "",
) -> int | None:
    """Return roadmap evidence tier for common Spanish public-data source families."""
    source_id_key = normalize_key_part(source_id)
    instrument_key = normalize_key_part(instrument_code)
    haystack = normalize_key_part(f"{source_id} {source_url} {source_title} {instrument_code}")

    if (
        _key_is_or_startswith(source_id_key, ("boe", "placsp", "bdns", "snpsap"))
        or source_id_key in {"congreso votaciones", "senado votaciones", "congreso iniciativas", "senado iniciativas"}
        or _key_is_or_startswith(instrument_key, ("boe",))
        or instrument_key in {"public contracting", "public subsidy"}
        or any(
            token in haystack
            for token in (
                "boees",
                "boe_es",
                "contrataciondelestadoes",
                "contrataciondelestado_es",
                "infosubvencioneses",
                "infosubvenciones_es",
                "bdnstrans",
                "pap_hacienda_gob_es_bdnstrans",
            )
        )
    ):
        return PRIMARY_RECORD_TIER

    if _key_is_or_startswith(source_id_key, ("moncloa",)) or "lamoncloagobes" in haystack or "lamoncloa_gob_es" in haystack:
        return OFFICIAL_COMMUNICATION_TIER

    if any(token in haystack for token in ("gobes", "gob_es", "agenciatributaria", "sede_agenciatributaria", "hacienda")):
        return OFFICIAL_STRUCTURED_TIER

    return None
