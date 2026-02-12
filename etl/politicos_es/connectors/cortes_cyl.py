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


CCYL_BASE = "https://www.ccyl.es"
CCYL_LIST_URL = f"{CCYL_BASE}/Organizacion/PlenoAlfabetico"


def decode_ccyl_html(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "charset=" in ct:
        enc = ct.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            pass
    # Site is consistently UTF-8 but keep a safe fallback.
    try:
        return payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return payload.decode("iso-8859-1", errors="replace")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def parse_ccyl_procuradores_list(html: str) -> list[dict[str, Any]]:
    # Links look like:
    # /Organizacion/Procurador?Legislatura=11&amp;CodigoPersona=P11034
    anchor_pattern = re.compile(
        r'<a[^>]+href\s*=\s*(["\'])(?P<href>[^"\']+)\1[^>]*>(?P<label>.*?)</a>',
        flags=re.I | re.S,
    )
    leg_pattern = re.compile(r"Legislatura=(?P<leg>\d+).*?CodigoPersona=(?P<persona>[A-Z0-9]+)", flags=re.I)

    seen: set[tuple[str, str]] = set()
    records: list[dict[str, Any]] = []

    matches = list(anchor_pattern.finditer(html))
    for idx, m in enumerate(matches):
        href_raw = unescape(m.group("href"))
        mm = leg_pattern.search(href_raw.replace("&amp;", "&"))
        if not mm:
            continue
        leg = mm.group("leg")
        persona = mm.group("persona")
        key = (leg, persona)
        if key in seen:
            continue
        seen.add(key)

        # Keep a context window around the anchor to recover sibling fields
        # while avoiding spill-over from adjacent rows.
        next_anchor = matches[idx + 1].start() if idx + 1 < len(matches) else len(html)
        safe_end = max(m.end(), next_anchor)
        start = m.start()
        end = min(len(html), safe_end)
        window = html[start:end]

        # Name is in <p class="cc_org_Procurador"> ... </p>
        name = normalize_ws(m.group("label"))
        name = normalize_ws(re.sub(r"<[^>]+>", " ", unescape(name)))
        m_name = re.search(r'<p[^>]*class="cc_org_Procurador"[^>]*>(.*?)</p>', window, flags=re.I | re.S)
        if m_name:
            name = normalize_ws(unescape(strip_tags(m_name.group(1))))

        if not name:
            # Fallback: text directly in anchor often already contains the name.
            text_name = normalize_ws(re.sub(r"<[^>]+>", " ", unescape(m.group("label"))))
            if text_name:
                name = text_name

        group = ""
        m_group = re.search(
            r'<span[^>]*class="cc_org_ProcuradorGrupoParlamentario"[^>]*>(.*?)</span>',
            window,
            flags=re.I | re.S,
        )
        if m_group:
            group = normalize_ws(unescape(strip_tags(m_group.group(1))))
        else:
            m_group_alt = re.search(
                r"(?:grupo|grup)\s*parlamentario\s*:?\s*([^<\n\r]+)",
                normalize_ws(re.sub(r"<[^>]+>", " ", window)),
                flags=re.I,
            )
            if m_group_alt:
                group = normalize_ws(m_group_alt.group(1))
                group = re.sub(r"\s+provincia[^\w].*$", "", group, flags=re.I)

        province = ""
        m_prov = re.search(
            r'<span[^>]*class="cc_org_ProcuradorGrupoProvincia"[^>]*>(.*?)</span>',
            window,
            flags=re.I | re.S,
        )
        if m_prov:
            province = normalize_ws(unescape(strip_tags(m_prov.group(1))))
        else:
            m_prov_alt = re.search(
                r"(?:provincia|província)\s*:?\s*([^<\n\r]+)",
                normalize_ws(re.sub(r"<[^>]+>", " ", window)),
                flags=re.I,
            )
            if m_prov_alt:
                province = normalize_ws(m_prov_alt.group(1))

        href = unescape(href_raw)
        detail_url = f"{CCYL_BASE}{href}"
        records.append(
            {
                "source_record_id": f"leg:{leg};persona:{persona}",
                "legislatura": leg,
                "codigo_persona": persona,
                "full_name": name,
                "group_name": group,
                "province": province,
                "detail_url": detail_url,
            }
        )

    if not records:
        raise RuntimeError("No se encontraron procuradores en PlenoAlfabetico (Cortes CyL)")
    return records


def build_cortes_cyl_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(CCYL_LIST_URL, timeout)
    html = decode_ccyl_html(payload, ct)
    records = parse_ccyl_procuradores_list(html)
    # Current legislature has 81 procuradores; be conservative.
    if len(records) < 70:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} procuradores parseados (esperado ~81)")
    return records


class CortesCylProcuradoresConnector(BaseConnector):
    source_id = "cortes_cyl_procuradores"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or CCYL_LIST_URL

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
            records = build_cortes_cyl_records(timeout)
            payload_obj = {"source": "ccyl_pleno_alfabetico", "list_url": resolved_url, "records": records}
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

        source_record_id = pick_value(record, ("source_record_id", "codigo_persona", "id"))
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
            "institution_territory_code": "ES-CL",
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
