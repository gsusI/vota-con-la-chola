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
    normalize_ws,
    now_utc_iso,
    pick_value,
    sha256_bytes,
    split_spanish_name,
    stable_json,
)
from .base import BaseConnector


PV_BASE = "https://www.legebiltzarra.eus"
PV_LIST_URL = f"{PV_BASE}/comparla/c_comparla_alf_ACT.html"


def parse_dot_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value)
    if not m:
        m = re.search(r"(\d{1,2})\s+(\d{1,2})\s+(\d{4})", value)
    if not m:
        return None
    d = int(m.group(1))
    mo = int(m.group(2))
    y = int(m.group(3))
    return f"{y:04d}-{mo:02d}-{d:02d}"


def parse_member_row(tr_html: str) -> dict[str, Any] | None:
    # Identify member id from link.
    m = re.search(r'href\s*=\s*(["\'])(/fichas/c_(\d+)\.html)\1', tr_html, flags=re.I)
    if not m:
        return None
    rel = m.group(2)
    mid = m.group(3)
    detail_url = urljoin(PV_BASE, rel)

    text = normalize_ws(re.sub(r"<[^>]+>", " ", unescape(tr_html)))
    # Example: "Abaroa Cantuariense, Aritz GP EA-NV (14.05.2024 - )"
    group = ""
    start_date = None
    end_date = None

    gm = re.search(r"\bGP\s+([A-Za-zÁÉÍÓÚÑáéíóúñ0-9./ -]+?)\s*\(([^)]*)\)", text, flags=re.I)
    if gm:
        group = normalize_ws(gm.group(1))
        dates = gm.group(2)
        dm = re.search(r"([0-9./-]+)\s*-\s*([0-9./-]*)", dates)
        if dm:
            start_date = parse_dot_date(dm.group(1))
            if dm.group(2):
                end_date = parse_dot_date(dm.group(2))

    # Name: take prefix before "GP".
    name_part = text
    if " GP " in text:
        name_part = text.split(" GP ", 1)[0].strip()
    if "," in name_part:
        family, given = [normalize_ws(p) for p in name_part.split(",", 1)]
        full_name = normalize_ws(f"{given} {family}")
    else:
        full_name = name_part

    return {
        "source_record_id": f"id:{mid};alta:{start_date or ''}",
        "member_id": mid,
        "full_name": full_name,
        "group_name": group,
        "start_date": start_date,
        "end_date": end_date,
        "detail_url": detail_url,
    }


def parse_vasco_detail_profile(html: str) -> dict[str, Any]:
    """Extract optional group/date fields from the profile HTML."""
    text = normalize_ws(re.sub(r"<[^>]+>", " ", unescape(html)))
    result: dict[str, Any] = {}
    if not text:
        return result

    # Common pattern in profile detail pages:
    # "Parlamentario del Grupo Grupo Mixto-Sumar (21.05.2024 - )"
    m = re.search(
        r"Parlamentari[oa]\s+del\s+Grupo\s+([A-Za-zÁÉÍÓÚÑáéíóúñ0-9./ -]+?)\s*\(([^)]*)\)",
        text,
        flags=re.I,
    )
    if not m:
        # Fallback wording sometimes references "grupo parlamentario"
        m = re.search(
            r"Grupo\s+Parlamentari[o|a]\s+([A-Za-zÁÉÍÓÚÑáéíóúñ0-9./ -]+?)\s*\(([^)]*)\)",
            text,
            flags=re.I,
        )
    if m:
        raw_group = normalize_ws(m.group(1))
        if raw_group.lower().startswith("grupo "):
            raw_group = raw_group[6:].strip()
        result["group_name"] = raw_group
        dates = m.group(2)
        dm = re.search(r"([0-9./-]+)\s*-\s*([0-9./-]*)", dates)
        if dm:
            result["start_date"] = parse_dot_date(dm.group(1))
            if dm.group(2):
                result["end_date"] = parse_dot_date(dm.group(2))

    return result


def build_parlamento_vasco_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(PV_LIST_URL, timeout)
    html = payload.decode("utf-8", errors="replace")
    if not (ct or "").lower().startswith("text/html") and "<html" not in html.lower():
        raise RuntimeError(f"Respuesta inesperada para listado: content_type={ct!r}")

    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.I | re.S)
    records: list[dict[str, Any]] = []
    for tr in trs:
        rec = parse_member_row(tr)
        if rec:
            # Fill group/start/end from profile when list row is incomplete.
            if not rec.get("group_name") or not rec.get("start_date"):
                detail_url = rec["detail_url"]
                if "_SM.html" not in detail_url:
                    profile_url = detail_url.replace(".html", "_SM.html")
                else:
                    profile_url = detail_url
                try:
                    payload, _ = http_get_bytes(profile_url, timeout)
                    profile = parse_vasco_detail_profile(payload.decode("utf-8", errors="replace"))
                    if profile.get("group_name") and not rec.get("group_name"):
                        rec["group_name"] = str(profile["group_name"])
                    if profile.get("start_date") and not rec.get("start_date"):
                        rec["start_date"] = str(profile["start_date"])
                    if profile.get("end_date") and not rec.get("end_date"):
                        rec["end_date"] = str(profile["end_date"])
                except Exception:
                    # Keep list-data if profile is unavailable.
                    pass
            records.append(rec)

    # Basque parliament should have 75 members.
    if len(records) < 50:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} parlamentarios parseados")
    return records


class ParlamentoVascoParlamentariosConnector(BaseConnector):
    source_id = "parlamento_vasco_parlamentarios"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or PV_LIST_URL

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
            records = build_parlamento_vasco_records(timeout)
            payload_obj = {"source": "parlamento_vasco_html", "list_url": resolved_url, "records": records}
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
        start_date = parse_dot_date(pick_value(record, ("start_date", "alta", "fecha_inicio"))) or pick_value(
            record, ("start_date",)
        )
        end_date = parse_dot_date(pick_value(record, ("end_date", "baja", "fecha_fin"))) or pick_value(
            record, ("end_date",)
        )

        source_record_id = pick_value(record, ("source_record_id", "member_id", "id"))
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
            "institution_territory_code": "ES-PV",
            "birth_date": None,
            "start_date": start_date,
            "end_date": end_date,
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
