from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import SOURCE_CONFIG, SPAIN_COUNTRY_NAMES
from ..fetch import fetch_payload
from ..parsers import parse_europarl_xml
from ..types import Extracted
from ..util import (
    normalize_key_part,
    normalize_ws,
    parse_date_flexible,
    pick_value,
    sha256_bytes,
    split_spanish_name,
    stable_json,
)
from .base import BaseConnector


class EuroparlMepsConnector(BaseConnector):
    source_id = "europarl_meps"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        if url_override:
            return url_override
        return SOURCE_CONFIG[self.source_id]["default_url"]

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
    ) -> Extracted:
        resolved_url = (
            f"file://{from_file.resolve()}" if from_file else self.resolve_url(url_override, timeout)
        )
        fetched = fetch_payload(
            source_id=self.source_id,
            source_url=resolved_url,
            raw_dir=raw_dir,
            timeout=timeout,
            from_file=from_file,
            strict_network=strict_network,
        )
        records = parse_europarl_xml(fetched["payload"])
        return Extracted(
            source_id=self.source_id,
            source_url=fetched["source_url"],
            resolved_url=fetched["resolved_url"],
            fetched_at=fetched["fetched_at"],
            raw_path=fetched["raw_path"],
            content_sha256=fetched["content_sha256"],
            content_type=fetched["content_type"],
            bytes=fetched["bytes"],
            note=fetched.get("note", ""),
            payload=fetched["payload"],
            records=records,
        )

    def normalize(self, record: dict[str, Any], snapshot_date: str | None) -> dict[str, Any] | None:
        given_name = normalize_ws(
            str(pick_value(record, ("name", "givenName", "first_name", "firstName")) or "")
        )
        family_name = normalize_ws(
            str(pick_value(record, ("surname", "family_name", "last_name", "lastName")) or "")
        )
        raw_full_name = pick_value(record, ("fullName", "fullname", "name", "nombre"))
        full_name = normalize_ws(str(raw_full_name)) if raw_full_name else ""

        if not full_name and given_name and family_name:
            full_name = normalize_ws(f"{given_name} {family_name}")
        elif not full_name and given_name:
            full_name = given_name
        elif family_name and raw_full_name == given_name:
            full_name = normalize_ws(f"{given_name} {family_name}")

        if full_name and "," in full_name:
            parsed_given, parsed_family, parsed_full = split_spanish_name(full_name)
            full_name = parsed_full
            if parsed_given and not given_name:
                given_name = parsed_given
            if parsed_family and not family_name:
                family_name = parsed_family

        if not full_name:
            return None

        country = normalize_key_part(pick_value(record, ("country", "pais", "territory_code")) or "")
        if country and country not in SPAIN_COUNTRY_NAMES:
            return None

        source_record_id = pick_value(record, ("id", "memberId", "person_id", "source_record_id"))
        if not source_record_id:
            source_record_id = sha256_bytes(f"{full_name}|ES".encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": normalize_ws(full_name),
            "given_name": given_name or None,
            "family_name": family_name or None,
            "gender": pick_value(record, ("gender", "sexo", "genero")),
            "party_name": pick_value(record, ("politicalGroup", "party", "grupo")),
            "territory_code": "ES",
            "institution_territory_code": "",
            "birth_date": parse_date_flexible(pick_value(record, ("birthDate", "fecha_nacimiento"))),
            "start_date": parse_date_flexible(pick_value(record, ("startDate", "fecha_inicio"))),
            "end_date": parse_date_flexible(pick_value(record, ("endDate", "fecha_fin"))),
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
