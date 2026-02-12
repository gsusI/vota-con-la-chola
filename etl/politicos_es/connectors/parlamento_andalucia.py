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


PA_BASE = "https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento"
PA_LIST_URL = f"{PA_BASE}/composicionyfuncionamiento/diputadosysenadores.do"
PA_DETAIL_URL = f"{PA_BASE}/composicionyfuncionamiento/organosparlamentarios/pleno.do"


def decode_pa_html(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "charset=" in ct:
        enc = ct.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            pass
    try:
        return payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return payload.decode("iso-8859-1", errors="replace")


def parse_pa_list_ids(list_html: str) -> list[tuple[str, str]]:
    # Keep only "current deputies" section: exclude "Listado de renuncias".
    main = re.split(r"Listado\s+de\s+renuncias", list_html, flags=re.I)[0]
    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for href_raw in re.findall(r'href="([^"]+)"', main, flags=re.I):
        href = unescape(href_raw)
        if not re.search(r"accion=Ver\s+Diputados", href, flags=re.I):
            continue
        m_cod = re.search(r"\bcodmie=(\d+)\b", href, flags=re.I)
        m_leg = re.search(r"\bnlegis=(\d+)\b", href, flags=re.I)
        if not (m_cod and m_leg):
            continue
        key = (m_cod.group(1), m_leg.group(1))
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)
    return unique


def parse_pa_detail(codmie: str, nlegis: str, timeout: int) -> dict[str, Any]:
    url = f"{PA_DETAIL_URL}?codmie={codmie}&nlegis={nlegis}&codorg=3"
    payload, ct = http_get_bytes(url, timeout)
    html = decode_pa_html(payload, ct)

    # Name tends to be the first h3 in the ficha.
    h3s = re.findall(r"<h3[^>]*>(.*?)</h3>", html, flags=re.I | re.S)
    full_name = ""
    for h3 in h3s:
        t = normalize_ws(re.sub(r"<[^>]+>", " ", unescape(h3)))
        if t and t.lower() not in {"en la actualidad", "documentación de interés"}:
            if len(t.split()) >= 2:
                full_name = t
                break

    # Group appears as an h2 like "G.P. Socialista".
    group = ""
    for h2 in re.findall(r"<h2[^>]*>(.*?)</h2>", html, flags=re.I | re.S):
        t = normalize_ws(re.sub(r"<[^>]+>", " ", unescape(h2)))
        if t.lower().startswith("g.p."):
            group = t
            break

    # Circunscripción: <span class=negrita>Circunscripción:</span> Málaga
    text = normalize_ws(unescape(re.sub(r"<[^>]+>", " ", html)))
    m = re.search(
        r"Circunscripci[oó]n:\s*([A-Za-zÀ-ÿ' -]+?)(?:\s+Escaño\b|$)",
        text,
        flags=re.I,
    )
    circ = normalize_ws(m.group(1)) if m else ""

    record = {
        "source_record_id": f"codmie:{codmie};leg:{nlegis}",
        "codmie": codmie,
        "nlegis": nlegis,
        "full_name": full_name,
        "group_name": group,
        "circunscripcion": circ,
        "detail_url": url,
    }
    return record


def build_parlamento_andalucia_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = http_get_bytes(PA_LIST_URL, timeout)
    html = decode_pa_html(payload, ct)
    ids = parse_pa_list_ids(html)
    if not ids:
        raise RuntimeError("No se encontraron diputados actuales (codmie/nlegis) en Parlamento de Andalucia")

    records = [parse_pa_detail(codmie, nlegis, timeout) for codmie, nlegis in ids]
    if len(records) < 80:
        raise RuntimeError(f"Extraccion sospechosa: solo {len(records)} diputados parseados")
    return records


class ParlamentoAndaluciaDiputadosConnector(BaseConnector):
    source_id = "parlamento_andalucia_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or PA_LIST_URL

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
            records = build_parlamento_andalucia_records(timeout)
            payload_obj = {"source": "parlamento_andalucia_html", "list_url": resolved_url, "records": records}
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
        circ = pick_value(record, ("circunscripcion", "provincia", "circunscripcio"))

        source_record_id = pick_value(record, ("source_record_id", "codmie", "id"))
        if not source_record_id:
            source_record_id = sha256_bytes(stable_json(record).encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": full_name,
            "given_name": given_name,
            "family_name": family_name,
            "gender": None,
            "party_name": normalize_ws(group_name) if group_name else None,
            "territory_code": normalize_ws(circ) if circ else "",
            "institution_territory_code": "ES-AN",
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
