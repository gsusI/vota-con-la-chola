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


ASAMBLEAEX_BASE = "https://www.asambleaex.es"
ASAMBLEAEX_LIST_URL = f"{ASAMBLEAEX_BASE}/dipslegis"


def decode_asambleaex_html(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "charset=" in ct:
        enc = ct.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            pass
    # The site is typically ISO-8859-1.
    try:
        return payload.decode("iso-8859-1", errors="strict")
    except UnicodeDecodeError:
        return payload.decode("utf-8", errors="replace")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def parse_asambleaex_total_count(html: str) -> int | None:
    # Pagination footer looks like: "1-20 (65)"
    m = re.search(r"\(\s*(\d{1,4})\s*\)\s*</p>", html, flags=re.I)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def parse_asambleaex_list_page(html: str) -> list[dict[str, Any]]:
    # Each record roughly:
    # <li><a class="pn-title" href="verdiputado-351">Apellido, Nombre</a>
    #   <p class="pn-normal">Grupo Parlamentario ... BADAJOZ</p></li>
    items: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<a[^>]*class="pn-title"[^>]*href="verdiputado-(?P<id>\d+)"[^>]*>(?P<name>.*?)</a>\s*<p[^>]*class="pn-normal"[^>]*>(?P<meta>.*?)</p>',
        html,
        flags=re.I | re.S,
    ):
        dip_id = m.group("id")
        name = normalize_ws(unescape(strip_tags(m.group("name"))))
        meta = normalize_ws(unescape(strip_tags(m.group("meta"))))

        group = meta
        province = ""
        # Province is the last token for active list entries (BADAJOZ/CACERES).
        m_prov = re.search(r"\b(BADAJOZ|C[ÁA]CERES)\b\s*$", meta, flags=re.I)
        if m_prov:
            province = normalize_ws(m_prov.group(1))
            group = normalize_ws(meta[: m_prov.start()].rstrip(" ,"))

        items.append(
            {
                "source_record_id": f"id:{dip_id};leg:12",
                "diputado_id": dip_id,
                "full_name": name,
                "group_name": group,
                "province": province,
                "detail_url": f"{ASAMBLEAEX_BASE}/verdiputado-{dip_id}",
            }
        )
    return items


def build_asambleaextremadura_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(ASAMBLEAEX_LIST_URL, timeout)
    html_1 = decode_asambleaex_html(payload, ct)

    total = parse_asambleaex_total_count(html_1) or 0
    # XII Legislatura has 65 seats; the active listing should be close to that.
    if total and total < 50:
        raise RuntimeError(f"Extraccion sospechosa: total={total} diputados (esperado ~65)")

    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_page(html: str) -> None:
        for rec in parse_asambleaex_list_page(html):
            sid = str(rec.get("source_record_id") or "")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            records.append(rec)

    add_page(html_1)

    # Crawl pagination offsets (site uses 20 per page).
    if total:
        for offset in range(21, total + 1, 20):
            url = f"{ASAMBLEAEX_BASE}/dipslegis-12-ALTA-{offset}"
            p, ct2 = http_get_bytes(url, timeout)
            add_page(decode_asambleaex_html(p, ct2))
    else:
        # Fallback: follow explicit page links if count is missing.
        for href in sorted(set(re.findall(r'href="(dipslegis-12-ALTA-\d+)"', html_1, flags=re.I))):
            url = f"{ASAMBLEAEX_BASE}/{unescape(href)}"
            p, ct2 = http_get_bytes(url, timeout)
            add_page(decode_asambleaex_html(p, ct2))

    if len(records) < 50:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} diputados parseados (esperado ~65)")
    return records


class AsambleaExtremaduraDiputadosConnector(BaseConnector):
    source_id = "asamblea_extremadura_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or ASAMBLEAEX_LIST_URL

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
            records = build_asambleaextremadura_records(timeout)
            payload_obj = {"source": "asambleaex_dipslegis", "list_url": resolved_url, "records": records}
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
        province = pick_value(record, ("province", "provincia", "territory_code"))

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
            "territory_code": normalize_ws(province) if province else "",
            "institution_territory_code": "ES-EX",
            "birth_date": parse_date_flexible(pick_value(record, ("birth_date", "fecha_nacimiento"))),
            "start_date": None,
            "end_date": None,
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }

