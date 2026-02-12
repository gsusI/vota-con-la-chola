from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

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


PN_BASE = "https://parlamentodenavarra.es"
PN_LIST_URL = f"{PN_BASE}/es/composicion-organos/parlamentarios-forales"


def decode_pn_html(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "charset=" in ct:
        enc = ct.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            pass
    return payload.decode("utf-8", errors="replace")


def html_looks_blocked(html: str) -> bool:
    h = html.lower()
    if "just a moment" in h:
        return True
    if "performing security verification" in h:
        return True
    if "cdn-cgi/challenge-platform" in h and "_cf_chl_opt" in h:
        return True
    return False


def parse_pn_profile_html(html: str, *, detail_url: str | None = None) -> dict[str, Any] | None:
    if html_looks_blocked(html):
        return None

    # Slug from about="/es/persona/<slug>"
    slug = ""
    m_about = re.search(r'about="(/es/persona/[^"]+)"', html, flags=re.I)
    if m_about:
        slug = m_about.group(1)

    # Name
    full_name = ""
    m_name = re.search(r'<div[^>]*class="nombregrupo_ficha"[^>]*>(.*?)</div>', html, flags=re.I | re.S)
    if m_name:
        full_name = normalize_ws(clean_text(unescape(m_name.group(1))))
    if not full_name:
        m_title = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
        if m_title:
            t = normalize_ws(clean_text(unescape(m_title.group(1))))
            if "|" in t:
                t = t.split("|", 1)[0].strip()
            full_name = t
    if not full_name:
        return None

    # Group: prefer the "G.P. ..." link if present.
    group_name = ""
    m_gp = re.search(r'>\s*(G\.P\.\s*[^<]+)</a>', html, flags=re.I)
    if m_gp:
        group_name = normalize_ws(clean_text(m_gp.group(1)))
    if not group_name:
        m_g2 = re.search(r"Grupo\s+Parlamentario\s+([^<]+)</div>", html, flags=re.I)
        if m_g2:
            group_name = normalize_ws(clean_text(m_g2.group(1)))
            if group_name and not group_name.lower().startswith("g.p."):
                group_name = f"G.P. {group_name}"

    # Start date: find "Fecha de alta" row and read ISO from content attr.
    start_date = None
    m_start = re.search(
        r"Fecha\s+de\s+alta.*?content=\"(\d{4}-\d{2}-\d{2})T",
        html,
        flags=re.I | re.S,
    )
    if m_start:
        start_date = m_start.group(1)

    source_record_id = ""
    if slug:
        source_record_id = f"persona:{slug.split('/es/persona/', 1)[1]}"
    if not source_record_id and detail_url:
        source_record_id = f"url:{detail_url}"
    if not source_record_id:
        source_record_id = sha256_bytes(stable_json({"name": full_name, "group": group_name}).encode("utf-8"))[:24]

    return {
        "source_record_id": source_record_id,
        "full_name": full_name,
        "group_name": group_name,
        "start_date": start_date,
        "detail_url": detail_url,
    }


def parse_pn_list_links(list_html: str) -> list[str]:
    # Links appear as /es/persona/<slug>
    hrefs = re.findall(r'href="(/es/persona/[^"]+)"', list_html, flags=re.I)
    seen: set[str] = set()
    out: list[str] = []
    for h in hrefs:
        if h in seen:
            continue
        seen.add(h)
        out.append(h)
    if not out:
        raise RuntimeError("No se encontraron links de personas en Navarra (listado)")
    return out


def build_parlamento_navarra_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(PN_LIST_URL, timeout)
    list_html = decode_pn_html(payload, ct)
    if html_looks_blocked(list_html):
        raise RuntimeError("Listado bloqueado (Cloudflare)")
    hrefs = parse_pn_list_links(list_html)

    records: list[dict[str, Any]] = []
    for href in hrefs:
        url = urljoin(PN_BASE, href)
        p2, ct2 = http_get_bytes(url, timeout)
        html = decode_pn_html(p2, ct2)
        rec = parse_pn_profile_html(html, detail_url=url)
        if rec:
            records.append(rec)

    if len(records) < 25:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} parlamentarios parseados")
    return records


def records_from_html_dir(dir_path: Path) -> list[dict[str, Any]]:
    html_files = sorted([p for p in dir_path.glob("*.html") if p.is_file()])
    if not html_files:
        raise RuntimeError(f"Directorio sin .html: {dir_path}")

    records: list[dict[str, Any]] = []
    for p in html_files:
        html = p.read_text(encoding="utf-8", errors="replace")
        rec = parse_pn_profile_html(html, detail_url=None)
        if rec is None:
            continue
        rec["html_path"] = str(p)
        records.append(rec)
    if not records:
        raise RuntimeError(f"No se pudieron parsear perfiles desde: {dir_path}")
    return records


class ParlamentoNavarraParlamentariosForalesConnector(BaseConnector):
    source_id = "parlamento_navarra_parlamentarios_forales"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or PN_LIST_URL

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
    ) -> Extracted:
        if from_file is not None:
            if from_file.is_dir():
                records = records_from_html_dir(from_file)
                payload_obj = {
                    "source": "parlamento_navarra_profiles_dir",
                    "dir": str(from_file),
                    "records": records,
                }
                payload = json.dumps(payload_obj, ensure_ascii=True, sort_keys=True).encode("utf-8")
                fetched_at = now_utc_iso()
                raw_path = raw_output_path(raw_dir, self.source_id, "json")
                raw_path.write_bytes(payload)
                return Extracted(
                    source_id=self.source_id,
                    source_url=f"file://{from_file.resolve()}",
                    resolved_url=f"file://{from_file.resolve()}",
                    fetched_at=fetched_at,
                    raw_path=raw_path,
                    content_sha256=sha256_bytes(payload),
                    content_type="application/json",
                    bytes=len(payload),
                    note="from-dir",
                    payload=payload,
                    records=records,
                )

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
            records = build_parlamento_navarra_records(timeout)
            payload_obj = {"source": "parlamento_navarra_html", "list_url": resolved_url, "records": records}
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
        full_name = normalize_ws(full_name)
        given_name, family_name, full_name = split_spanish_name(full_name)

        group_name = pick_value(record, ("group_name", "grupo", "party_name"))
        start_date = parse_date_flexible(pick_value(record, ("start_date", "fecha_alta")))

        source_record_id = pick_value(record, ("source_record_id", "slug", "id"))
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
            "institution_territory_code": "ES-NA",
            "birth_date": parse_date_flexible(pick_value(record, ("birth_date", "fecha_nacimiento"))),
            "start_date": start_date,
            "end_date": parse_date_flexible(pick_value(record, ("end_date", "fecha_baja"))),
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
