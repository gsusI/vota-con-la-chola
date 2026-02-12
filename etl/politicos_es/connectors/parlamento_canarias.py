from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import SOURCE_CONFIG
from ..fetch import fetch_payload
from ..parsers import parse_json_source
from ..types import Extracted
from ..util import normalize_ws, parse_date_flexible, pick_value, sha256_bytes, stable_json
from .base import BaseConnector


PARCAN_LIST_URL = "https://parcan.es/api/diputados/por_legislatura/11/?format=json"


class ParlamentoCanariasDiputadosConnector(BaseConnector):
    source_id = "parlamento_canarias_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or PARCAN_LIST_URL

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
    ) -> Extracted:
        resolved_url = self.resolve_url(url_override, timeout)
        source_url = f"file://{from_file.resolve()}" if from_file is not None else resolved_url
        fetched = fetch_payload(
            source_id=self.source_id,
            source_url=source_url,
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
        miembro = pick_value(record, ("miembro", "id", "miembro_id"))
        legislatura = pick_value(record, ("legislatura", "leg"))

        given = pick_value(record, ("nombre", "given_name", "name")) or ""
        a1 = pick_value(record, ("apellido1", "apellido_1", "first_surname")) or ""
        a2 = pick_value(record, ("apellido2", "apellido_2", "second_surname")) or ""
        family = normalize_ws(f"{a1} {a2}").strip()
        full_name = normalize_ws(f"{given} {family}").strip()
        if not full_name:
            return None

        group_alias = pick_value(record, ("alias_grupo", "siglas", "grupo_siglas"))
        group_name = pick_value(record, ("grupo", "grupo_nombre", "party_name"))
        party_name = group_alias or group_name

        circ = pick_value(record, ("circunscripcion", "circunscripción", "provincia", "isla"))

        start_date = parse_date_flexible(pick_value(record, ("alta_cargo", "start_date", "fecha_alta")))
        end_date = parse_date_flexible(pick_value(record, ("baja_cargo", "end_date", "fecha_baja")))

        source_record_id = pick_value(record, ("source_record_id",))
        if not source_record_id:
            if miembro and legislatura:
                source_record_id = f"miembro:{miembro};leg:{legislatura}"
            elif miembro:
                source_record_id = f"miembro:{miembro}"
            else:
                source_record_id = sha256_bytes(stable_json(record).encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": full_name,
            "given_name": normalize_ws(given) or None,
            "family_name": family or None,
            "gender": None,
            "party_name": normalize_ws(party_name) if party_name else None,
            "territory_code": normalize_ws(circ) if circ else "",
            "institution_territory_code": "ES-CN",
            "birth_date": parse_date_flexible(pick_value(record, ("birth_date", "fecha_nacimiento"))),
            "start_date": start_date,
            "end_date": end_date,
            "is_active": end_date is None,
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }

