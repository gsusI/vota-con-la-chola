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


JGPA_BASE = "https://www.jgpa.es"
JGPA_LIST_URL = (
    f"{JGPA_BASE}/diputados-y-diputadas"
    "?p_p_id=jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k"
    "&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&p_p_col_id=column-2&p_p_col_count=1"
    "&p_r_p_2113237475_diputadoId=0&p_r_p_2113237475_legislaturaId=0&p_r_p_2113237475_grupoParlamentarioId=0"
    "&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_redirect=%2Fdiputados-y-diputadas"
    "&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_delta=50"
    "&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_keywords="
    "&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_advancedSearch=false"
    "&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_andOperator=true"
    "&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_resetCur=false"
    "&cur=1"
)


def decode_jgpa_html(payload: bytes, content_type: str | None) -> str:
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


def parse_jgpa_diputados(html: str) -> list[dict[str, Any]]:
    # The page is a Liferay "search container"; ask for delta=50 to get all 45 in one response.
    # Each entry contains:
    # - diputadoId=NNNNN in href
    # - <span class="name block title">Apellido, Nombre ...
    # - <img ... alt='Ir a Grupo Parlamentario X' />
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for m in re.finditer(r"<li class='entry[^']*'>(?P<body>.*?)</li>", html, flags=re.I | re.S):
        body = m.group("body")

        m_id = re.search(r"diputadoId=(\d+)", body, flags=re.I)
        if not m_id:
            continue
        dip_id = m_id.group(1)
        if dip_id == "0" or dip_id in seen:
            continue
        seen.add(dip_id)

        name = ""
        m_name = re.search(
            r'<span[^>]*class="name\s+block\s+title"[^>]*>(?P<name>.*?)</span>',
            body,
            flags=re.I | re.S,
        )
        if m_name:
            # Drop HTML comments and other non-name fragments inside the span.
            name_html = m_name.group("name")
            name_html = name_html.split("<!--", 1)[0]
            name_html = name_html.split("<img", 1)[0]
            name = normalize_ws(unescape(strip_tags(name_html)))

        group = ""
        m_group = re.search(
            r"alt=(?:'|\")Ir a\s+Grupo\s+Parlamentario\s+([^'\"]+)(?:'|\")",
            body,
            flags=re.I,
        )
        if m_group:
            group_raw = normalize_ws(unescape(m_group.group(1)))
            group = group_raw if "grupo" in group_raw.lower() else f"Grupo Parlamentario {group_raw}"

        seat = None
        m_seat = re.search(r"Escaño:\\s*(\\d{1,3})", body, flags=re.I)
        if m_seat:
            try:
                seat = int(m_seat.group(1))
            except ValueError:
                seat = None

        records.append(
            {
                "source_record_id": f"id:{dip_id}",
                "diputado_id": dip_id,
                "full_name": name,
                "group_name": group,
                "seat_number": seat,
            }
        )

    if not records:
        raise RuntimeError("No se encontraron diputados en JGPA (Asturias)")
    return records


def build_jgpa_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(JGPA_LIST_URL, timeout)
    html = decode_jgpa_html(payload, ct)
    records = parse_jgpa_diputados(html)
    if len(records) < 35:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} diputados parseados (esperado ~45)")
    return records


class JuntaGeneralAsturiasDiputadosConnector(BaseConnector):
    source_id = "jgpa_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or JGPA_LIST_URL

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
            records = build_jgpa_records(timeout)
            payload_obj = {"source": "jgpa_diputados_list", "list_url": resolved_url, "records": records}
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
            "institution_territory_code": "ES-AS",
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
