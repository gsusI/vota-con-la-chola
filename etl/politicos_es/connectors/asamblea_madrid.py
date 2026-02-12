from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..config import SOURCE_CONFIG
from ..fetch import fetch_payload
from ..parsers import parse_asamblea_madrid_ocupaciones_csv
from ..types import Extracted
from ..util import normalize_ws, parse_date_flexible, pick_value, sha256_bytes, stable_json
from .base import BaseConnector


class AsambleaMadridOcupacionesConnector(BaseConnector):
    source_id = "asamblea_madrid_ocupaciones"

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
        records = parse_asamblea_madrid_ocupaciones_csv(fetched["payload"])
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
        full_name = pick_value(record, ("NOMBRE", "nombre", "full_name", "nombre_completo"))
        if not full_name:
            return None

        raw_leg = record.get("legislatura_int")
        if raw_leg is None:
            raw_leg = pick_value(record, ("LEGISLATURA", "legislatura")) or "0"
        try:
            legislatura = int(str(raw_leg).strip())
        except ValueError:
            legislatura = 0
        if legislatura <= 0:
            return None

        group = pick_value(record, ("GRUPO_PARLAMENTARIO", "grupo_parlamentario", "grupo")) or ""
        group = normalize_ws(re.sub(r"\s*\(.*\)\s*$", "", group)).rstrip(".")
        start_date = parse_date_flexible(pick_value(record, ("FECHA_INICIO", "fecha_inicio", "inicio")))
        end_date = parse_date_flexible(pick_value(record, ("FECHA_FIN", "fecha_fin", "fin")))

        source_record_id = pick_value(record, ("id", "ID", "source_record_id"))
        if not source_record_id:
            fingerprint = "|".join(
                (
                    normalize_ws(full_name),
                    normalize_ws(pick_value(record, ("CARGO", "cargo")) or ""),
                    normalize_ws(pick_value(record, ("GRUPO_PARLAMENTARIO", "grupo_parlamentario", "grupo")) or ""),
                    str(legislatura),
                    start_date or "",
                    end_date or "",
                )
            )
            source_record_id = sha256_bytes(fingerprint.encode("utf-8"))[:24]

        role_title = pick_value(record, ("CARGO", "cargo")) or SOURCE_CONFIG[self.source_id]["role_title"]
        role_title = normalize_ws(role_title)
        if role_title.lower() in {"diputado", "diputada"}:
            role_title = "Diputado/a"

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": normalize_ws(full_name),
            "given_name": None,
            "family_name": None,
            "gender": None,
            "party_name": group or None,
            "territory_code": "Comunidad de Madrid",
            "institution_territory_code": "Comunidad de Madrid",
            "birth_date": None,
            "start_date": start_date,
            "end_date": end_date,
            "source_record_id": source_record_id,
            "role_title": role_title or cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "is_active": bool(record.get("is_active")) if "is_active" in record else True,
            "raw_payload": stable_json(record),
        }
