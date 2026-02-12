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


PC_BASE = "https://parlamento-cantabria.es"
PC_LIST_URL = f"{PC_BASE}/informacion-general/composicion/11l-pleno-del-parlamento-de-cantabria"


def decode_pc_html(payload: bytes, content_type: str | None) -> str:
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


def parse_pc_list_links(list_html: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()

    # In the "Pleno" table, deputies appear as <a href="/informacion-general/composicion/11l-...">Apellido, Nombre</a>
    for m in re.finditer(
        r'<a\s+href="(?P<href>/informacion-general/composicion/11l-[^"]+)"[^>]*>(?P<name>[^<]+)</a>',
        list_html,
        flags=re.I,
    ):
        href = m.group("href")
        name = normalize_ws(unescape(strip_tags(m.group("name"))))
        if not href or href in seen:
            continue
        # Exclude organ/group pages.
        if any(
            s in href
            for s in (
                "11l-grupo-parlamentario-",
                "11l-pleno-",
                "11l-mesa-",
                "11l-junta-",
                "11l-diputacion-",
            )
        ):
            continue
        if len(name.split()) < 2:
            continue
        seen.add(href)
        links.append(href)

    if not links:
        raise RuntimeError("No se encontraron links de diputados en Parlamento Cantabria (Pleno XI)")
    return links


def parse_pc_detail(detail_html: str) -> dict[str, Any]:
    # Node id appears as: <article id="node-1914073" ... about="/informacion-general/composicion/11l-...">
    node_id = ""
    m_node = re.search(r'<article[^>]*\bid="node-(\d+)"', detail_html, flags=re.I)
    if m_node:
        node_id = m_node.group(1)

    title = ""
    m_title = re.search(r"<title>(.*?)</title>", detail_html, flags=re.I | re.S)
    if m_title:
        title = normalize_ws(unescape(strip_tags(m_title.group(1))))
    full_name = title.split("|", 1)[0].strip() if title else ""
    full_name = re.sub(r"^\(\s*11L\s*\)\s*", "", full_name, flags=re.I).strip()

    group = ""
    m_group = re.search(
        r'<a[^>]*href="/informacion-general/composicion/11l-grupo-parlamentario-[^"]+"[^>]*>(.*?)</a>',
        detail_html,
        flags=re.I | re.S,
    )
    if m_group:
        group = normalize_ws(unescape(strip_tags(m_group.group(1))))

    return {"node_id": node_id, "full_name": full_name, "group_name": group}


def build_parlamento_cantabria_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(PC_LIST_URL, timeout)
    list_html = decode_pc_html(payload, ct)
    hrefs = parse_pc_list_links(list_html)

    records: list[dict[str, Any]] = []
    for href in hrefs:
        url = f"{PC_BASE}{href}"
        p2, ct2 = http_get_bytes(url, timeout)
        detail_html = decode_pc_html(p2, ct2)
        detail = parse_pc_detail(detail_html)
        node_id = detail.get("node_id") or ""
        source_record_id = f"node:{node_id};leg:11" if node_id else f"url:{href};leg:11"
        records.append(
            {
                "source_record_id": source_record_id,
                "full_name": detail.get("full_name") or "",
                "group_name": detail.get("group_name") or "",
                "node_id": node_id,
                "detail_url": url,
            }
        )

    if len(records) < 25:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} diputados (esperado ~35)")
    return records


class ParlamentoCantabriaDiputadosConnector(BaseConnector):
    source_id = "parlamento_cantabria_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or PC_LIST_URL

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
            records = build_parlamento_cantabria_records(timeout)
            payload_obj = {"source": "parlamento_cantabria_html", "list_url": resolved_url, "records": records}
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

        source_record_id = pick_value(record, ("source_record_id", "node_id", "id"))
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
            "institution_territory_code": "ES-CB",
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
