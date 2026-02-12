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


CORTS_BASE = "https://www.cortsvalencianes.es"
CORTS_DIPUTADOS_LIST_URL = "https://www.cortsvalencianes.es/es/composicion/diputados"


def parse_corts_profile_urls(list_html: str) -> list[str]:
    # Example:
    # /es/composicion/diputados/xi/abad_soler_ramon/14e506aa72d70d597b755db69897d454
    rels = sorted(
        set(
            re.findall(
                r'href="(/es/composicion/diputados/([ivxlcdm]+)/[^"/]+/([0-9a-f]{32}))"',
                list_html,
                flags=re.I,
            )
        )
    )
    urls: list[str] = []
    for rel, _leg, _sid in rels:
        urls.append(f"{CORTS_BASE}{unescape(rel)}")
    return urls


def extract_deputy_name(detail_html: str) -> str:
    # The page uses an h2 inside .deputy-name.
    m = re.search(r'<div[^>]*class="deputy-name"[^>]*>.*?<h2[^>]*>(.*?)</h2>', detail_html, re.I | re.S)
    if m:
        return normalize_ws(re.sub(r"<[^>]+>", " ", unescape(m.group(1))))

    # Fallback: pick the first plausible h2 that looks like a name.
    h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", detail_html, flags=re.I | re.S)
    for h2 in h2s:
        t = normalize_ws(re.sub(r"<[^>]+>", " ", unescape(h2)))
        if t and t.lower() not in {
            "navegación principal",
            "menú secundario",
            "a un solo clic",
            "pie de página",
            "ficha del diputado/a",
        }:
            if len(t.split()) >= 2:
                return t
    return ""


def extract_group_name(detail_html: str) -> str:
    m = re.search(r"Grupo parlamentario:\s*<span[^>]*>([^<]+)</span>", detail_html, flags=re.I)
    if m:
        return normalize_ws(unescape(m.group(1)))

    # Fallback: text-only
    text = normalize_ws(re.sub(r"<[^>]+>", " ", detail_html))
    m = re.search(r"Grupo parlamentario:\s*([A-Za-zÀ-ÿ0-9'(). -]+)", text, flags=re.I)
    return normalize_ws(m.group(1)) if m else ""


def extract_province(detail_html: str) -> str:
    # Example: <div class="deputy-membresy">Diputado por Alicante.</div>
    m = re.search(r'<div[^>]*class="deputy-membresy"[^>]*>(.*?)</div>', detail_html, flags=re.I | re.S)
    if not m:
        return ""
    text = normalize_ws(re.sub(r"<[^>]+>", " ", unescape(m.group(1))))
    m2 = re.search(r"\bpor\s+([A-Za-zÀ-ÿ' -]+)\.", text, flags=re.I)
    return normalize_ws(m2.group(1)) if m2 else normalize_ws(text)


def extract_birth_date(detail_html: str) -> str | None:
    # Example text: "Nacido el 04-07-1978 ..."
    text = normalize_ws(re.sub(r"<[^>]+>", " ", detail_html))
    m = re.search(r"\bNacido\s+el\s+(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b", text, flags=re.I)
    if not m:
        return None
    return parse_date_flexible(m.group(1))


def build_corts_valencianes_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(CORTS_DIPUTADOS_LIST_URL, timeout)
    html = payload.decode("utf-8", errors="replace")
    if not (ct or "").lower().startswith("text/html") and "<html" not in html.lower():
        raise RuntimeError(f"Respuesta inesperada para listado: content_type={ct!r}")

    profile_urls = parse_corts_profile_urls(html)
    if not profile_urls:
        raise RuntimeError("No se encontraron perfiles de diputados en el listado de Les Corts")

    records: list[dict[str, Any]] = []
    for url in profile_urls:
        # Capture legislature (roman) and stable id from URL.
        m = re.search(r"/diputados/([ivxlcdm]+)/[^/]+/([0-9a-f]{32})$", url, flags=re.I)
        if not m:
            continue
        leg = m.group(1).upper()
        sid = m.group(2).lower()

        detail_payload, detail_ct = http_get_bytes(url, timeout)
        detail_html = detail_payload.decode("utf-8", errors="replace")
        if not (detail_ct or "").lower().startswith("text/html") and "<html" not in detail_html.lower():
            raise RuntimeError(f"Respuesta inesperada para ficha: content_type={detail_ct!r}")

        full_name = extract_deputy_name(detail_html)
        group_name = extract_group_name(detail_html)
        province = extract_province(detail_html)
        birth_date = extract_birth_date(detail_html)

        records.append(
            {
                "source_record_id": f"leg:{leg};id:{sid}",
                "stable_id": sid,
                "legislatura": leg,
                "full_name": full_name,
                "group_name": group_name,
                "province": province,
                "birth_date": birth_date,
                "detail_url": url,
            }
        )

    if len(records) < 50:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} diputados parseados")
    return records


class CortsValencianesDiputatsConnector(BaseConnector):
    source_id = "corts_valencianes_diputats"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or CORTS_DIPUTADOS_LIST_URL

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
            records = build_corts_valencianes_records(timeout)
            payload_obj = {"source": "corts_valencianes_html", "list_url": resolved_url, "records": records}
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
        full_name = pick_value(record, ("full_name", "nombre", "diputado", "diputada", "name"))
        if not full_name:
            return None
        given_name, family_name, full_name = split_spanish_name(full_name)

        group_name = pick_value(record, ("group_name", "grupo", "grup"))
        province = pick_value(record, ("province", "provincia"))

        source_record_id = pick_value(record, ("source_record_id", "stable_id", "id"))
        if not source_record_id:
            source_record_id = sha256_bytes(stable_json(record).encode("utf-8"))[:24]

        birth_date = parse_date_flexible(pick_value(record, ("birth_date", "fecha_nacimiento")))

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": full_name,
            "given_name": given_name,
            "family_name": family_name,
            "gender": None,
            "party_name": normalize_ws(group_name) if group_name else None,
            "territory_code": normalize_ws(province) if province else "",
            "institution_territory_code": "ES-VC",
            "birth_date": birth_date,
            "start_date": None,
            "end_date": None,
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }

