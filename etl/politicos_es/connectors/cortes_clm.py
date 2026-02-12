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
    clean_text,
    normalize_ws,
    now_utc_iso,
    parse_date_flexible,
    pick_value,
    sha256_bytes,
    split_spanish_name,
    stable_json,
)
from .base import BaseConnector


CCLM_BASE = "https://www.cortesclm.es"
CCLM_LIST_URL = f"{CCLM_BASE}/web2/paginas/resul_diputados.php?legislatura=11"
CCLM_DETAIL_URL = f"{CCLM_BASE}/web2/paginas/detalle_diputado.php"


def decode_cclm_html(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "charset=" in ct:
        enc = ct.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            pass
    # Their legacy PHP pages are often iso-8859-1.
    try:
        return payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return payload.decode("iso-8859-1", errors="replace")


def parse_cclm_list_rows(list_html: str) -> list[dict[str, Any]]:
    # Rows look like:
    # <tr><td><p><a href="javascript:abrirventana(578,11);">...</a></p></td>
    # <td><p>Toledo</p></td> ... <td><p ...> &nbsp;&nbsp;GPS</p></td></tr>
    pattern = re.compile(
        r"<tr>\s*<td>\s*<p>\s*<a\s+href=\"javascript:abrirventana\((\d+),\s*(\d+)\);\">(.*?)</a>.*?</td>\s*"
        r"<td>\s*<p>(.*?)</p>\s*</td>\s*"
        r"<td>\s*<p>(.*?)</p>\s*</td>\s*"
        r"<td>\s*<p[^>]*>(.*?)</p>\s*</td>\s*</tr>",
        flags=re.I | re.S,
    )
    rows: list[dict[str, Any]] = []
    for dip_id, leg, name_html, prov_html, leg_html, group_html in pattern.findall(list_html):
        full_name = clean_text(unescape(name_html))
        provincia = clean_text(unescape(prov_html))
        group_short = clean_text(unescape(group_html))
        leg_text = clean_text(unescape(leg_html))
        rows.append(
            {
                "id": str(dip_id),
                "legislatura": str(leg),
                "legislatura_text": leg_text,
                "full_name": full_name,
                "provincia": provincia,
                "group_acronym": group_short,
                "detail_url": f"{CCLM_DETAIL_URL}?id={dip_id}",
                "source_record_id": f"id:{dip_id};leg:{leg}",
            }
        )
    return rows


def parse_cclm_detail(dip_id: str, timeout: int) -> dict[str, Any]:
    url = f"{CCLM_DETAIL_URL}?id={dip_id}"
    payload, ct = http_get_bytes(url, timeout)
    html = decode_cclm_html(payload, ct)

    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I | re.S)
    full_name = clean_text(unescape(m.group(1))) if m else ""

    # Group is usually in a div id="grupo": <h3>GRUPO PARLAMENTARIO ...</h3>
    m2 = re.search(r'id=["\']grupo["\'][^>]*>.*?<h3[^>]*>(.*?)</h3>', html, flags=re.I | re.S)
    group_name = clean_text(unescape(m2.group(1))) if m2 else ""

    # Find earliest "Fecha Alta" in tables (dd/mm/yyyy). The page includes many dates;
    # using the minimum is a robust approximation for "start of activity" in the legislature.
    dates = []
    for d, mo, y in re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b", html):
        iso = parse_date_flexible(f"{d}/{mo}/{y}")
        if iso:
            dates.append(iso)
    start_date = min(dates) if dates else None

    email = None
    m3 = re.search(r'href=["\']mailto:([^"\']+)["\']', html, flags=re.I)
    if m3:
        email = normalize_ws(unescape(m3.group(1)))

    return {
        "id": dip_id,
        "full_name_detail": full_name,
        "group_name": group_name,
        "start_date": start_date,
        "email": email,
        "detail_url": url,
    }


def build_cclm_diputados_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(CCLM_LIST_URL, timeout)
    html = decode_cclm_html(payload, ct)
    base_rows = parse_cclm_list_rows(html)
    if not base_rows:
        raise RuntimeError("No se pudieron parsear filas del listado de diputados (Cortes CLM)")

    records: list[dict[str, Any]] = []
    for row in base_rows:
        dip_id = str(row["id"])
        detail = parse_cclm_detail(dip_id, timeout)
        merged = dict(row)
        merged.update(detail)
        records.append(merged)

    # Castilla-La Mancha parliament has 33 seats; sanity guard against blank pages.
    if len(records) < 20:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} diputados parseados")
    return records


class CortesClmDiputadosConnector(BaseConnector):
    source_id = "cortes_clm_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or CCLM_LIST_URL

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
            records = build_cclm_diputados_records(timeout)
            payload_obj = {"source": "cortes_clm_html", "list_url": resolved_url, "records": records}
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
        full_name = pick_value(record, ("full_name_detail", "full_name", "nombre", "name"))
        if not full_name:
            return None
        given_name, family_name, full_name = split_spanish_name(full_name)

        group_name = pick_value(record, ("group_name", "grupo", "group", "group_acronym"))
        provincia = pick_value(record, ("provincia", "province", "circunscripcion"))

        source_record_id = pick_value(record, ("source_record_id", "id"))
        if not source_record_id:
            source_record_id = sha256_bytes(stable_json(record).encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": full_name,
            "given_name": given_name,
            "family_name": family_name,
            "gender": None,
            "party_name": normalize_ws(group_name) if group_name else None,
            "territory_code": normalize_ws(provincia) if provincia else "",
            "institution_territory_code": "ES-CM",
            "birth_date": parse_date_flexible(pick_value(record, ("birth_date", "fecha_nacimiento"))),
            "start_date": parse_date_flexible(pick_value(record, ("start_date", "fecha_alta"))) or None,
            "end_date": None,
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }

