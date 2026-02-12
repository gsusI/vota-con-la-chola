from __future__ import annotations

import json
import re
import urllib.parse
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


PIB_LIST_URL = "https://www.parlamentib.es/Representants/Diputats.aspx?criteria=0"
PIB_WEBGTP_BASE = "http://web.parlamentib.es/webgtp/scripts/UnRegPers.asp"


def decode_pib_html(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "charset=" in ct:
        enc = ct.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            pass
    # Both hosts tend to be ISO-8859-1.
    try:
        return payload.decode("iso-8859-1", errors="strict")
    except UnicodeDecodeError:
        return payload.decode("utf-8", errors="replace")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def parse_pib_list_ids(list_html: str) -> list[dict[str, str]]:
    # List uses JS: showDiputado('564','Sr.','Pedro M.','ÁLVAREZ I GELABERT')
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in re.finditer(
        r"showDiputado\(\s*'(?P<autor>\d+)'\s*,\s*'(?P<tract>[^']*)'\s*,\s*'(?P<nom>[^']*)'\s*,\s*'(?P<cognoms>[^']*)'\s*\)",
        list_html,
        flags=re.I,
    ):
        autor = m.group("autor").strip()
        tract = m.group("tract").strip()
        nom = m.group("nom").strip()
        cognoms = m.group("cognoms").strip()
        if not autor:
            continue
        if autor in seen:
            continue
        seen.add(autor)
        records.append({"autor": autor, "tract": tract, "nom": nom, "cognoms": cognoms})
    if not records:
        raise RuntimeError("No se encontraron diputados en el listado del ParlamentIB (showDiputado)")
    return records


def build_webgtp_detail_url(autor: str, tract: str, nom: str, cognoms: str) -> str:
    params = {
        "CFautor": autor,
        "CFTract": tract,
        "CFnom": nom,
        "CFcongnoms": cognoms,
    }
    return f"{PIB_WEBGTP_BASE}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"


def parse_webgtp_roles(detail_html: str) -> list[dict[str, str]]:
    # Parse table rows: [idx, label, value] repeated, group into sections by "Càrrec:".
    roles: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for tr in re.finditer(r"<tr[^>]*valign=['\"]?top['\"]?[^>]*>.*?</tr>", detail_html, flags=re.I | re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr.group(0), flags=re.I | re.S)
        cleaned = [normalize_ws(unescape(strip_tags(c))) for c in cells]
        if len(cleaned) < 3:
            continue
        label = cleaned[1]
        value = cleaned[2]
        if not label:
            continue

        label_key = normalize_key_part(label).rstrip(":")
        if label_key.startswith("carrec"):
            if current:
                roles.append(current)
            current = {"carrec": value}
            continue
        if current is None:
            continue

        if label_key.startswith("legislatura"):
            current["legislatura"] = value
        elif label_key.startswith("organisme"):
            current["organisme"] = value
        elif label_key == "illa":
            current["illa"] = value
        elif label_key.startswith("candidatura"):
            current["candidatura"] = value
        elif label_key.startswith("partit politic"):
            current["partit_politic"] = value
        elif label_key.startswith("inici"):
            current["inici"] = value
        elif label_key.startswith("final"):
            current["final"] = value

    if current:
        roles.append(current)
    return roles


def pick_current_deputy_role(roles: list[dict[str, str]]) -> dict[str, str] | None:
    candidates: list[dict[str, str]] = []
    for r in roles:
        carrec = normalize_ws(r.get("carrec", ""))
        leg = normalize_ws(r.get("legislatura", ""))
        if not carrec or not leg:
            continue
        if not carrec.upper().startswith("DIPUT"):
            continue
        if leg != "11":
            continue
        candidates.append(r)
    if not candidates:
        return None
    # Prefer active (no final), else latest start.
    active = [r for r in candidates if not normalize_ws(r.get("final", ""))]
    if active:
        return active[0]

    def start_key(r: dict[str, str]) -> str:
        return parse_date_flexible(r.get("inici")) or ""

    return sorted(candidates, key=start_key, reverse=True)[0]


def build_parlament_balears_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(PIB_LIST_URL, timeout, insecure_ssl=True)
    list_html = decode_pib_html(payload, ct)
    ids = parse_pib_list_ids(list_html)

    records: list[dict[str, Any]] = []
    for row in ids:
        autor = row["autor"]
        detail_url = build_webgtp_detail_url(autor, row["tract"], row["nom"], row["cognoms"])
        p2, ct2 = http_get_bytes(detail_url, timeout)
        detail_html = decode_pib_html(p2, ct2)
        roles = parse_webgtp_roles(detail_html)
        role = pick_current_deputy_role(roles)
        if role is None:
            # Keep at least the base identity so we can diagnose.
            records.append(
                {
                    "source_record_id": f"autor:{autor};leg:11",
                    "autor": autor,
                    "full_name": normalize_ws(f"{row['nom']} {row['cognoms']}"),
                    "detail_url": detail_url,
                    "note": "missing_deputy_role_leg11",
                }
            )
            continue

        records.append(
            {
                "source_record_id": f"autor:{autor};leg:11",
                "autor": autor,
                "full_name": normalize_ws(f"{row['nom']} {row['cognoms']}"),
                "group_name": role.get("organisme", ""),
                "island": role.get("illa", ""),
                "party_name": role.get("partit_politic", "") or role.get("candidatura", ""),
                "start_date": parse_date_flexible(role.get("inici")),
                "end_date": parse_date_flexible(role.get("final")),
                "detail_url": detail_url,
            }
        )

    # ParlamentIB has 59 seats. Be conservative.
    if len(records) < 45:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} diputados parseados (esperado ~59)")
    return records


class ParlamentBalearsDiputatsConnector(BaseConnector):
    source_id = "parlament_balears_diputats"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or PIB_LIST_URL

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
            records = build_parlament_balears_records(timeout)
            payload_obj = {"source": "parlamentib_html_webgtp", "list_url": resolved_url, "records": records}
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

        party_name = pick_value(record, ("party_name", "partit_politic", "partido", "candidatura"))
        group_name = pick_value(record, ("group_name", "grupo", "grup"))
        island = pick_value(record, ("island", "illa", "isla"))

        start_date = parse_date_flexible(pick_value(record, ("start_date", "inici", "fecha_alta")))
        end_date = parse_date_flexible(pick_value(record, ("end_date", "final", "fecha_baja")))

        source_record_id = pick_value(record, ("source_record_id", "autor", "id"))
        if not source_record_id:
            source_record_id = sha256_bytes(stable_json(record).encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": full_name,
            "given_name": given_name,
            "family_name": family_name,
            "gender": None,
            "party_name": normalize_ws(party_name) if party_name else (normalize_ws(group_name) if group_name else None),
            "territory_code": normalize_ws(island) if island else "",
            "institution_territory_code": "ES-IB",
            "birth_date": parse_date_flexible(pick_value(record, ("birth_date", "fecha_nacimiento"))),
            "start_date": start_date,
            "end_date": end_date,
            "is_active": end_date is None,
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
