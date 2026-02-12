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
from ..util import (
    normalize_ws,
    now_utc_iso,
    parse_date_flexible,
    pick_value,
    sha256_bytes,
    split_spanish_name,
    stable_json,
)
from .base import BaseConnector


ARM_BASE = "https://www.asambleamurcia.es"
ARM_LIST_URL = f"{ARM_BASE}/diputados"


def decode_arm_html(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "charset=" in ct:
        enc = ct.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            pass
    return payload.decode("utf-8", errors="replace")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def parse_arm_list_ids(list_html: str) -> list[tuple[str, str, bool]]:
    # Page contains two sections: current deputies and a section headed "Han causado baja".
    parts = re.split(r"Han\s+causado\s+baja", list_html, flags=re.I)
    active_html = parts[0]
    inactive_html = parts[1] if len(parts) > 1 else ""

    found: list[tuple[str, str, bool]] = []
    seen: set[str] = set()

    def add_part(html: str, is_active: bool) -> None:
        for m in re.finditer(r'href="/diputado/(?P<id>\d+)/(?P<slug>[^"?#]+)"', html, flags=re.I):
            dip_id = m.group("id")
            slug = m.group("slug")
            if dip_id in seen:
                continue
            seen.add(dip_id)
            found.append((dip_id, slug, is_active))

    add_part(active_html, True)
    add_part(inactive_html, False)

    if not found:
        raise RuntimeError("No se encontraron diputados en listado de Asamblea Murcia (/diputados)")
    return found


def parse_arm_detail(dip_id: str, slug: str, is_active: bool, timeout: int) -> dict[str, Any]:
    url = f"{ARM_BASE}/diputado/{dip_id}/{slug}"
    payload, ct = http_get_bytes(url, timeout, insecure_ssl=True)
    html = decode_arm_html(payload, ct)

    # Name is typically in <title>.
    title = ""
    m_title = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
    if m_title:
        title = normalize_ws(unescape(strip_tags(m_title.group(1))))
    full_name = ""
    if title and "|" in title:
        full_name = normalize_ws(title.split("|", 1)[0])
    if not full_name:
        # Fallback: use slug as last resort.
        full_name = normalize_ws(slug.replace("-", " "))

    group = ""
    # First bullet under "Trayectoria parlamentaria" tends to be:
    # <li>Diputada del Grupo Parlamentario Socialista</li>
    m_group = re.search(r"Diputad[oa]\s+del\s+Grupo\s+Parlamentario\s+([^<]+)</li>", html, flags=re.I)
    if m_group:
        group_raw = normalize_ws(m_group.group(1))
        group = group_raw if "grupo" in group_raw.lower() else f"Grupo Parlamentario {group_raw}"

    return {
        "source_record_id": f"id:{dip_id};leg:11",
        "diputado_id": dip_id,
        "slug": slug,
        "full_name": full_name,
        "group_name": group,
        "is_active": is_active,
        "detail_url": url,
    }


def build_asamblea_murcia_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(ARM_LIST_URL, timeout, insecure_ssl=True)
    list_html = decode_arm_html(payload, ct)
    ids = parse_arm_list_ids(list_html)

    records = [parse_arm_detail(dip_id, slug, is_active, timeout) for dip_id, slug, is_active in ids]
    if len(records) < 35:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} diputados parseados (esperado ~45)")
    return records


class AsambleaMurciaDiputadosConnector(BaseConnector):
    source_id = "asamblea_murcia_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or ARM_LIST_URL

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
            records = build_asamblea_murcia_records(timeout)
            payload_obj = {"source": "asambleamurcia_html", "list_url": resolved_url, "records": records}
            payload = json.dumps(payload_obj, ensure_ascii=True, sort_keys=True).encode("utf-8")
            fetched_at = now_utc_iso()
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(payload)
            return Extracted(
                source_id=self.source_id,
                source_url=resolved_url,
                resolved_url=resolved_url,
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(payload),
                content_type="application/json",
                bytes=len(payload),
                note="network",
                payload=payload,
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

        group_name = pick_value(record, ("group_name", "grupo", "grup", "party_name"))

        source_record_id = pick_value(record, ("source_record_id", "diputado_id", "id"))
        if not source_record_id:
            source_record_id = sha256_bytes(stable_json(record).encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": full_name,
            "given_name": given_name,
            "family_name": family_name,
            "gender": None,
            "party_name": normalize_ws(group_name) if group_name else None,
            "territory_code": "",
            "institution_territory_code": "ES-MC",
            "birth_date": parse_date_flexible(pick_value(record, ("birth_date", "fecha_nacimiento"))),
            "start_date": None,
            "end_date": None,
            "is_active": bool(record.get("is_active", True)),
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
