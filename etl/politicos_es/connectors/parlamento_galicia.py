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


PG_BASE = "https://www.parlamentodegalicia.gal"
PG_LIST_URL = f"{PG_BASE}/Composicion/Deputados"


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def decode_pg_html(payload: bytes) -> str:
    # These pages are served as utf-8 in our captures.
    return payload.decode("utf-8", errors="replace")


def html_looks_blocked(html: str) -> bool:
    h = html.lower()
    if "errors.edgesuite.net" in h:
        return True
    if "<title>access denied" in h:
        return True
    if "<title>error" in h and "edgesuite" in h:
        return True
    return False


def parse_pg_profile_html(html: str, *, detail_url: str | None = None) -> dict[str, Any] | None:
    if html_looks_blocked(html):
        return None

    # Extract deputy id from meta og:url or the detail_url.
    deputy_id = ""
    m = re.search(r'property="og:url"[^>]*content="[^"]*/Deputados/(\d+)/', html, flags=re.I)
    if m:
        deputy_id = m.group(1)
    if not deputy_id and detail_url:
        m2 = re.search(r"/Deputados/(\d+)/", detail_url)
        if m2:
            deputy_id = m2.group(1)

    # Name: h1 contains the human name.
    full_name = ""
    m_name = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I | re.S)
    if m_name:
        full_name = clean_text(unescape(m_name.group(1)))
    if not full_name:
        m_title = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
        if m_title:
            t = normalize_ws(unescape(strip_tags(m_title.group(1))))
            # "Información do deputad@: Name - Parlamento de Galicia"
            if " - " in t:
                t = t.split(" - ", 1)[0].strip()
            if ":" in t:
                t = t.split(":", 1)[1].strip()
            full_name = t
    full_name = normalize_ws(full_name)
    if not full_name:
        return None

    # Group: first paragraph after the birth line typically.
    group_name = ""
    m_group = re.search(r"<p>\s*(Grupo\s+Parlamentario[^<]+)</p>", html, flags=re.I)
    if m_group:
        group_name = normalize_ws(clean_text(m_group.group(1)))

    # Contact / media
    email = None
    m_email = re.search(r'href=["\']mailto:([^"\']+)["\']', html, flags=re.I)
    if m_email:
        email = normalize_ws(unescape(m_email.group(1)))

    phone = None
    m_phone = re.search(r'href=["\']tel:([^"\']+)["\']', html, flags=re.I)
    if m_phone:
        phone = normalize_ws(unescape(m_phone.group(1)))

    photo_url = None
    m_photo = re.search(
        r'<img[^>]+src=["\']([^"\']*?/images/composicion/Deputados/[^"\']+)["\']',
        html,
        flags=re.I,
    )
    if m_photo:
        photo_url = urljoin(PG_BASE, m_photo.group(1))

    group_logo_url = None
    m_gl = re.search(r'<img[^>]+src=["\']([^"\']*?/images/xeral/grupos/[^"\']+)["\']', html, flags=re.I)
    if m_gl:
        group_logo_url = urljoin(PG_BASE, m_gl.group(1))

    # Circunscripcion: label + next value.
    circ = ""
    m_c = re.search(
        r"Circunscrici[oó]n\s+electoral:\s*</strong>\s*</p>.*?<div[^>]*class=\"col-10\"[^>]*>\s*([^<]+)",
        html,
        flags=re.I | re.S,
    )
    if m_c:
        circ = normalize_ws(clean_text(m_c.group(1)))

    # Birth info: free text like "As Nogais - 1957" (not a full date).
    birth_text = ""
    m_birth = re.search(r'<p[^>]*class="text-secondary-darker"[^>]*>(.*?)</p>', html, flags=re.I | re.S)
    if m_birth:
        birth_text = normalize_ws(clean_text(m_birth.group(1)))

    # Bio: keep a cleaned long paragraph if present.
    bio_text = ""
    m_bio = re.search(r"</p>\s*<p>\s*([^<]{80,}.*?)</p>", html, flags=re.I | re.S)
    if m_bio:
        candidate = normalize_ws(clean_text(unescape(m_bio.group(1))))
        if candidate and "grupo parlamentario" not in candidate.lower():
            bio_text = candidate

    source_record_id = f"dip:{deputy_id}" if deputy_id else ""
    if not source_record_id and detail_url:
        source_record_id = f"url:{detail_url}"
    if not source_record_id:
        source_record_id = sha256_bytes(stable_json({"name": full_name, "group": group_name}).encode("utf-8"))[:24]

    return {
        "source_record_id": source_record_id,
        "deputy_id": deputy_id,
        "full_name": full_name,
        "group_name": group_name,
        "circunscripcion": circ,
        "birth_text": birth_text,
        "email": email,
        "phone": phone,
        "photo_url": photo_url,
        "group_logo_url": group_logo_url,
        "bio_text": bio_text,
        "detail_url": detail_url,
    }


def parse_pg_list_links(list_html: str) -> list[str]:
    hrefs: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r'href="(?P<href>/Composicion/Deputados/\d+/[^"]+)"', list_html, flags=re.I):
        href = m.group("href")
        if href in seen:
            continue
        seen.add(href)
        hrefs.append(href)
    if not hrefs:
        raise RuntimeError("No se encontraron links de diputados en Parlamento de Galicia (listado)")
    return hrefs


def build_parlamento_galicia_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(PG_LIST_URL, timeout)
    _ = ct
    list_html = decode_pg_html(payload)
    if html_looks_blocked(list_html):
        raise RuntimeError("Listado bloqueado (WAF)")

    hrefs = parse_pg_list_links(list_html)
    records: list[dict[str, Any]] = []
    for href in hrefs:
        url = urljoin(PG_BASE, href)
        p2, _ct2 = http_get_bytes(url, timeout)
        detail_html = decode_pg_html(p2)
        rec = parse_pg_profile_html(detail_html, detail_url=url)
        if rec:
            records.append(rec)

    if len(records) < 50:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} diputados parseados")
    return records


def records_from_html_dir(dir_path: Path) -> list[dict[str, Any]]:
    html_files = sorted([p for p in dir_path.glob("*.html") if p.is_file()])
    if not html_files:
        raise RuntimeError(f"Directorio sin .html: {dir_path}")

    records: list[dict[str, Any]] = []
    for p in html_files:
        html = p.read_text(encoding="utf-8", errors="replace")
        rec = parse_pg_profile_html(html, detail_url=None)
        if rec is None:
            continue
        rec["html_path"] = str(p)
        records.append(rec)
    if not records:
        raise RuntimeError(f"No se pudieron parsear perfiles desde: {dir_path}")
    return records


class ParlamentoGaliciaDeputadosConnector(BaseConnector):
    source_id = "parlamento_galicia_deputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or PG_LIST_URL

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
    ) -> Extracted:
        if from_file is not None:
            # Support either:
            # - JSON samples (used by tests)
            # - a directory containing many captured HTML profile pages
            if from_file.is_dir():
                records = records_from_html_dir(from_file)
                payload_obj = {
                    "source": "parlamento_galicia_profiles_dir",
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
            records = build_parlamento_galicia_records(timeout)
            payload_obj = {"source": "parlamento_galicia_html", "list_url": resolved_url, "records": records}
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
        circ = pick_value(record, ("circunscripcion", "circunscricion", "circunscripción", "provincia"))

        source_record_id = pick_value(record, ("source_record_id", "deputy_id", "id"))
        if not source_record_id:
            source_record_id = sha256_bytes(stable_json(record).encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        # Galicia pages don't provide a reliable start/end date per mandate in a stable field.
        return {
            "full_name": full_name,
            "given_name": given_name,
            "family_name": family_name,
            "gender": None,
            "party_name": normalize_ws(group_name) if group_name else None,
            "territory_code": normalize_ws(circ) if circ else "",
            "institution_territory_code": "ES-GA",
            "birth_date": parse_date_flexible(pick_value(record, ("birth_date", "fecha_nacimiento"))),
            "start_date": parse_date_flexible(pick_value(record, ("start_date", "fecha_alta"))),
            "end_date": parse_date_flexible(pick_value(record, ("end_date", "fecha_baja"))),
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
