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
    normalize_key_part,
    normalize_ws,
    now_utc_iso,
    parse_date_flexible,
    pick_value,
    sha256_bytes,
    split_spanish_name,
    stable_json,
)
from .base import BaseConnector


PARLAMENT_BASE = "https://www.parlament.cat"
PARLAMENT_CATALUNYA_LIST_URL = (
    "https://www.parlament.cat/web/composicio/ple-parlament/composicio-actual/index.html"
)


def decode_parlament_html(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "charset=" in ct:
        enc = ct.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            pass
    # Parlament pages are often iso-8859-1. Fallbacks keep this resilient.
    try:
        return payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return payload.decode("iso-8859-1", errors="replace")


def clean_parlament_name(raw: str) -> str:
    text = normalize_ws(raw)
    # Strip common honorifics/titles used on the site.
    text = re.sub(r"^(m\.?\s*h\.?\s*)", "", text, flags=re.I)
    text = re.sub(r"^(hble\.?\s*)", "", text, flags=re.I)
    text = re.sub(r"^(sr\.?\s+|sra\.?\s+)", "", text, flags=re.I)
    return normalize_ws(text)


def parse_alta_date(group_text: str) -> str | None:
    # Example: "... Alta: 10.06.2024."
    if not group_text:
        return None

    normalized = normalize_ws(group_text)
    if not normalized:
        return None

    # Common explicit format.
    m = re.search(
        r"\balta:\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
        normalized,
        flags=re.I,
    )
    if m:
        d = int(m.group(1))
        mo = int(m.group(2))
        y = int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"

    # Variants where a date appears after the Alta label with extra punctuation.
    m = re.search(r"\balta\b\D{0,24}(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", normalized, flags=re.I)
    if m:
        d = int(m.group(1))
        mo = int(m.group(2))
        y = int(m.group(3))
        if y < 100:
            y += 2000
        return f"{y:04d}-{mo:02d}-{d:02d}"

    # As a last resort, search for any ISO-like date close to the Alta section.
    m = re.search(r"\balta\b.{0,24}(\d{4}[./-]\d{1,2}[./-]\d{1,2})", normalized, flags=re.I)
    if not m:
        return None

    date_text = normalize_ws(m.group(1)).replace("/", "-")
    return parse_date_flexible(date_text)


def extract_group_name(group_text: str) -> str:
    text = normalize_ws(group_text)
    if not text:
        return ""
    head = text.split(".", 1)[0]
    head = re.sub(r"\bMembre\b.*$", "", head, flags=re.I).strip()
    return normalize_ws(head)


def extract_circumscription(value: str) -> str:
    text = normalize_ws(value)
    text = re.sub(r"^circumscripci[oó]\s+electoral\s+de\s+", "", text, flags=re.I)
    return normalize_ws(text)


def parse_dt_dd(html_text: str) -> dict[str, str]:
    pairs = re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", html_text, flags=re.I | re.S)
    out: dict[str, str] = {}
    for k_html, v_html in pairs:
        k = clean_text(k_html).rstrip(":")
        v = clean_text(v_html)
        if not k:
            continue
        out[normalize_key_part(k)] = v
    return out


def parse_detail_record(p_codi: str, legislatura: str, timeout: int) -> dict[str, Any]:
    detail_url = (
        f"{PARLAMENT_BASE}/web/composicio/diputats-fitxa/index.html?p_codi={p_codi}&p_legislatura={legislatura}"
    )
    payload, ct = http_get_bytes(detail_url, timeout)
    html_text = decode_parlament_html(payload, ct)

    m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, flags=re.I | re.S)
    raw_name = clean_text(unescape(m.group(1))) if m else ""
    full_name = clean_parlament_name(raw_name)

    fields = parse_dt_dd(html_text)
    circ = fields.get(normalize_key_part("Circumscripció")) or fields.get("circumscripcio") or ""
    party = fields.get(normalize_key_part("Partit Polític")) or fields.get("partit politic") or ""
    group = fields.get(normalize_key_part("Grup parlamentari")) or fields.get("grup parlamentari") or ""

    start_date = parse_alta_date(group) or parse_date_flexible(group)
    record = {
        "source_record_id": f"p_codi:{p_codi};leg:{legislatura};alta:{start_date or ''}",
        "p_codi": p_codi,
        "legislatura": legislatura,
        "full_name": full_name,
        "circunscripcion": extract_circumscription(circ) if circ else "",
        "party_name": normalize_ws(party) if party else "",
        "group_name": extract_group_name(group),
        "start_date": start_date,
        "detail_url": detail_url,
    }
    return record


def build_parlament_catalunya_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(PARLAMENT_CATALUNYA_LIST_URL, timeout)
    html_text = decode_parlament_html(payload, ct)

    # Expect links to deputy profile pages with p_codi and p_legislatura.
    matches = re.findall(
        r"/web/composicio/diputats-fitxa/index\.html\?p_codi=(\d+)&amp;p_legislatura=(\d+)",
        html_text,
        flags=re.I,
    )
    if not matches:
        matches = re.findall(
            r"/web/composicio/diputats-fitxa/index\.html\?p_codi=(\d+)&p_legislatura=(\d+)",
            html_text,
            flags=re.I,
        )
    if not matches:
        raise RuntimeError("No se encontraron enlaces a diputados (p_codi) en composicio-actual")

    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for p_codi, leg in matches:
        key = (p_codi, leg)
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)

    records: list[dict[str, Any]] = []
    for p_codi, leg in unique:
        records.append(parse_detail_record(p_codi, leg, timeout))

    # Sanity: Catalonia parliament should be around 135 deputies in a legislature.
    if len(records) < 50:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} diputados parseados")
    return records


class ParlamentCatalunyaDiputatsConnector(BaseConnector):
    source_id = "parlament_catalunya_diputats"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or PARLAMENT_CATALUNYA_LIST_URL

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
            records = build_parlament_catalunya_records(timeout)
            payload_obj = {"source": "parlament_catalunya_html", "list_url": resolved_url, "records": records}
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
        raw_name = pick_value(record, ("full_name", "nombre", "diputat", "diputada", "name"))
        if not raw_name:
            return None
        full_name = clean_parlament_name(raw_name)
        given_name, family_name, full_name = split_spanish_name(full_name)

        party_name = pick_value(record, ("party_name", "partit", "partido", "grupo", "group_name"))
        circ = pick_value(record, ("circunscripcion", "circumscripcio", "circunscripcio electoral"))

        source_record_id = pick_value(record, ("source_record_id", "p_codi", "id"))
        if not source_record_id:
            source_record_id = sha256_bytes(stable_json(record).encode("utf-8"))[:24]

        start_date = pick_value(record, ("start_date", "alta", "fecha_inicio"))
        start_date = parse_date_flexible(start_date) or parse_alta_date(start_date or "")

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": full_name,
            "given_name": given_name,
            "family_name": family_name,
            "gender": None,
            "party_name": normalize_ws(party_name) if party_name else None,
            "territory_code": extract_circumscription(circ) if circ else "",
            "institution_territory_code": "ES-CT",
            "birth_date": None,
            "start_date": start_date,
            "end_date": None,
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
