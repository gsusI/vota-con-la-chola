from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..config import SOURCE_CONFIG
from ..fetch import fetch_payload
from ..http import http_get_bytes
from ..parsers import parse_json_source
from ..types import Extracted
from ..util import parse_date_flexible, pick_value, sha256_bytes, split_spanish_name, stable_json, normalize_ws
from .base import BaseConnector


class CongresoDiputadosConnector(BaseConnector):
    source_id = "congreso_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        if url_override:
            return url_override

        catalog_url = SOURCE_CONFIG[self.source_id]["default_url"]
        try:
            html_bytes, _ = http_get_bytes(
                catalog_url,
                timeout,
                headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            )
            html = html_bytes.decode("utf-8", errors="replace")
            candidates = sorted(set(re.findall(r"DiputadosActivos__[0-9]{14}\.json", html)))
            if not candidates:
                return catalog_url
            latest = candidates[-1]
            return f"https://www.congreso.es/webpublica/opendata/diputados/{latest}"
        except Exception:  # noqa: BLE001
            return catalog_url

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
        records = parse_json_source(fetched["payload"])
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
        raw_name = pick_value(record, ("NOMBRE", "nombre"))
        if not raw_name:
            return None
        given_name, family_name, full_name = split_spanish_name(raw_name)

        territory = pick_value(record, ("CIRCUNSCRIPCION", "circunscripcion", "provincia"))
        party_name = pick_value(record, ("FORMACIONELECTORAL", "GRUPOPARLAMENTARIO", "partido"))

        start_date = parse_date_flexible(
            pick_value(record, ("FECHAALTA", "FECHACONDICIONPLENA", "fecha_inicio"))
        )

        source_record_id = pick_value(record, ("CODDIPUTADO", "ID", "id", "codParlamentario"))
        if not source_record_id:
            fingerprint = f"{full_name}|{territory or ''}|{start_date or ''}"
            source_record_id = sha256_bytes(fingerprint.encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": full_name,
            "given_name": given_name,
            "family_name": family_name,
            "gender": pick_value(record, ("SEXO", "sexo", "gender", "genero")),
            "party_name": normalize_ws(party_name) if party_name else None,
            "territory_code": normalize_ws(territory) if territory else "",
            "institution_territory_code": "",
            "birth_date": parse_date_flexible(
                pick_value(record, ("FECHANACIMIENTO", "fecha_nacimiento", "birthDate"))
            ),
            "start_date": start_date,
            "end_date": parse_date_flexible(pick_value(record, ("FECHABAJA", "fecha_fin"))),
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
