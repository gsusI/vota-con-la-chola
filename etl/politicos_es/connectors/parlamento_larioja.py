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


LARIOJA_LIST_URL = "https://adminweb.parlamento-larioja.org/composicion-y-organos/diputados"


def decode_larioja_html(payload: bytes, content_type: str | None) -> str:
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


def parse_larioja_diputados(html: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Group blocks contain: <h2>Grupo Parlamentario X</h2> and a list of links to diputado pages.
    for block in re.split(r'<div\s+class="grupo"\s*>', html, flags=re.I)[1:]:
        m_group = re.search(r"<h2[^>]*>(.*?)</h2>", block, flags=re.I | re.S)
        group_name = normalize_ws(unescape(strip_tags(m_group.group(1)))) if m_group else ""
        if not group_name:
            continue

        for m in re.finditer(
            r'<a[^>]*href="(?P<href>https?://adminweb\.parlamento-larioja\.org/composicion-y-organos/legislatura-11/diputados/(?P<slug>[^"/?#]+))"[^>]*>(?P<name>.*?)</a>',
            block,
            flags=re.I | re.S,
        ):
            slug = m.group("slug")
            if not slug or slug in seen:
                continue
            seen.add(slug)
            name = normalize_ws(unescape(strip_tags(m.group("name"))))
            if not name:
                continue
            records.append(
                {
                    "source_record_id": f"slug:{slug};leg:11",
                    "full_name": name,
                    "group_name": group_name,
                    "detail_url": m.group("href"),
                    "slug": slug,
                }
            )

    if not records:
        raise RuntimeError("No se encontraron diputados en el listado de Parlamento de La Rioja")
    if len(records) < 25:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} diputados (esperado ~33)")
    return records


def build_larioja_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(LARIOJA_LIST_URL, timeout)
    html = decode_larioja_html(payload, ct)
    return parse_larioja_diputados(html)


class ParlamentoLaRiojaDiputadosConnector(BaseConnector):
    source_id = "parlamento_larioja_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or LARIOJA_LIST_URL

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
            records = build_larioja_records(timeout)
            payload_obj = {"source": "parlamento_larioja_list", "list_url": resolved_url, "records": records}
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

        group_name = pick_value(record, ("group_name", "grupo", "grup"))

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
            "institution_territory_code": "ES-RI",
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
