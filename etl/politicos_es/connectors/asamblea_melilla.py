from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from typing import Any

from ..config import SOURCE_CONFIG
from ..fetch import fetch_payload
from ..http import http_get_bytes
from ..parsers import parse_json_source
from ..raw import fallback_payload_from_sample, raw_output_path
from ..types import Extracted
from ..util import normalize_ws, now_utc_iso, parse_date_flexible, pick_value, sha256_bytes, split_spanish_name, stable_json
from .base import BaseConnector

MELILLA_ASSEMBLEA_URL = "https://sede.melilla.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_MIEMBROS"
DATASET_RE = re.compile(r"var\s+dataset_PTS2_MIEMBROS\s*=\s*(\[.*?\]);", re.S)


def decode_melilla_html(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "charset=" in ct:
        enc = ct.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            pass
    return payload.decode("utf-8", errors="replace")


def decode_escaped_json(payload: str) -> str:
    return (
        payload.replace("\\u003c", "<")
        .replace("\\u003e", ">")
        .replace("\\u002f", "/")
        .replace("\\u0026nbsp;", " ")
        .replace("\\u0026", "&")
    )


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def parse_pub_date(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    year = value.get("year")
    month = value.get("month")
    day = value.get("day")
    try:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except (TypeError, ValueError):
        return None


def parse_party_from_description(raw: str | None) -> str | None:
    if not raw:
        return None
    text = normalize_ws(unescape(strip_tags(str(raw))))
    if not text:
        return None

    if re.search(r"diputado\s+no\s+adscrito", text, flags=re.I):
        return None

    for pattern in (
        r"Grupo\s+Politico\s+([^()]{1,120})\s*\(([^()]{1,32})\)",
        r"Grupo\s+Pol[ií]tico\s+([^()]{1,120})\s*\(([^()]{1,32})\)",
        r"Grupo\s+Parlamentario\s+([^()]{1,120})\s*\(([^()]{1,32})\)",
    ):
        m = re.search(pattern, text, flags=re.I)
        if m:
            name = normalize_ws(m.group(1))
            abbr = normalize_ws(m.group(2))
            if name and abbr:
                return f"{name} ({abbr})"
            return name or abbr

    m = re.search(r"\(([^()]{1,32})\)\s*$", text)
    if m:
        return normalize_ws(m.group(1))
    return None


def parse_name_and_role(raw: str | None) -> tuple[str, str | None]:
    if not raw:
        return "", None

    name_with_meta = normalize_ws(unescape(strip_tags(str(raw))))
    if not name_with_meta:
        return "", None

    m_role = re.search(r"\s*-\s*([^()]{1,100})\s*\([^()]+\)\s*$", name_with_meta)
    role_title = None
    if m_role:
        role_title = normalize_ws(m_role.group(1))
        name_with_meta = normalize_ws(name_with_meta[: m_role.start()])

    m_party = re.search(r"\(([^()]{1,32})\)\s*$", name_with_meta)
    if m_party:
        name_with_meta = normalize_ws(name_with_meta[: m_party.start()])

    return name_with_meta, role_title


def parse_melilla_records(html: str) -> list[dict[str, Any]]:
    m = DATASET_RE.search(html)
    if not m:
        raise RuntimeError("No se encontró dataset_PTS2_MIEMBROS en la página")

    raw_json = decode_escaped_json(m.group(1))
    try:
        members = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("No se pudo decodificar dataset_PTS2_MIEMBROS") from exc

    if not isinstance(members, list):
        raise RuntimeError("dataset_PTS2_MIEMBROS no es un listado JSON")

    records: list[dict[str, Any]] = []
    for item in members:
        if not isinstance(item, dict):
            continue

        dboid = pick_value(item, ("dboid", "id", "record_id"))
        if not dboid:
            continue

        raw_name = pick_value(item, ("externString", "name"))
        full_name, role_title = parse_name_and_role(raw_name)
        if not full_name:
            continue

        remitent = item.get("remitent") if isinstance(item.get("remitent"), dict) else {}
        is_active = bool(remitent.get("isActive", True)) if isinstance(remitent, dict) else True
        party_name = parse_party_from_description(pick_value(item, ("descriptionProc", "description")))
        if not party_name:
            # fallback to party suffix in externString
            ext = normalize_ws(unescape(strip_tags(str(raw_name)))) if raw_name else ""
            m = re.search(r"\(([^()]{1,32})\)\s*$", ext)
            party_name = normalize_ws(m.group(1)) if m else None

        record: dict[str, Any] = {
            "source_record_id": f"melilla:{dboid}",
            "full_name": full_name,
            "role_title": role_title,
            "party_name": party_name,
            "is_active": is_active,
            "start_date": parse_pub_date(item.get("pubDateIni")),
            "end_date": None,
            "description": pick_value(item, ("descriptionProc", "description")),
            "remitent": remitent,
            "tablon": pick_value(item, ("tablon",)),
            "dboid": dboid,
            "raw": pick_value(item, ("externString", "source")),
        }
        records.append(record)

    if not records:
        raise RuntimeError("No se extrajeron miembros de Asamblea de Melilla")

    return records


class AsambleaMelillaDiputadosConnector(BaseConnector):
    source_id = "asamblea_melilla_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or MELILLA_ASSEMBLEA_URL

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
    ) -> Extracted:
        if from_file is not None:
            resolved_url = f"file://{from_file.resolve()}"
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

        resolved_url = self.resolve_url(url_override, timeout)
        try:
            payload, ct = http_get_bytes(
                resolved_url,
                timeout,
                insecure_ssl=True,
            )
            html = decode_melilla_html(payload, ct)
            records = parse_melilla_records(html)

            payload_obj = {"source": "asamblea_melilla_html", "url": resolved_url, "records": records}
            payload_bytes = json.dumps(payload_obj, ensure_ascii=True, sort_keys=True).encode("utf-8")
            fetched_at = now_utc_iso()
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(payload_bytes)
            return Extracted(
                source_id=self.source_id,
                source_url=resolved_url,
                resolved_url=resolved_url,
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(payload_bytes),
                content_type="application/json",
                bytes=len(payload_bytes),
                note="network",
                payload=payload_bytes,
                records=records,
            )
        except Exception as exc:  # noqa: BLE001
            if strict_network:
                raise
            fetched = fallback_payload_from_sample(
                self.source_id,
                raw_dir,
                note=f"network-error-fallback: {type(exc).__name__}: {exc}",
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
        full_name = pick_value(record, ("full_name", "nombre", "name"))
        if not full_name:
            return None
        given_name, family_name, full_name = split_spanish_name(full_name)

        source_record_id = pick_value(record, ("source_record_id", "id"))
        if not source_record_id:
            source_record_id = sha256_bytes(stable_json(record).encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        is_active = bool(record.get("is_active", True))
        role_title = pick_value(record, ("role_title",))
        if not role_title:
            role_title = cfg["role_title"]

        return {
            "full_name": full_name,
            "given_name": given_name,
            "family_name": family_name,
            "gender": None,
            "party_name": normalize_ws(str(record.get("party_name") or "")) or None,
            "territory_code": "",
            "institution_territory_code": "ES-ML",
            "birth_date": parse_date_flexible(pick_value(record, ("birth_date", "fecha_nacimiento"))),
            "start_date": parse_date_flexible(pick_value(record, ("start_date", "fecha_alta"))),
            "end_date": parse_date_flexible(pick_value(record, ("end_date", "fecha_baja"))) if not is_active else None,
            "is_active": is_active,
            "source_record_id": source_record_id,
            "role_title": role_title,
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
