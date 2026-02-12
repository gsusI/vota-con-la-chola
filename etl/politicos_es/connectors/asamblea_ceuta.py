from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from typing import Any

from ..config import SOURCE_CONFIG
from ..fetch import fetch_payload
from ..parsers import parse_json_source
from ..raw import fallback_payload_from_sample, raw_output_path
from ..types import Extracted
from ..util import normalize_ws, now_utc_iso, parse_date_flexible, pick_value, sha256_bytes, split_spanish_name, stable_json
from .base import BaseConnector


CEUTA_ASAMBLEA_URL = "https://www.ceuta.es/gobiernodeceuta/index.php/el-gobierno/la-asamblea"


def decode_html(payload: bytes, content_type: str | None) -> str:
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


def clean_name(text: str) -> str:
    s = normalize_ws(unescape(strip_tags(text)))
    if not s:
        return ""
    # Some entries glue abbreviations (e.g. "Dª.Sra."). Separate them first.
    s = re.sub(r"\.(?=[A-Za-zÁÉÍÓÚÑ])", ". ", s)
    s = normalize_ws(s)
    # Fix common missing spaces after abbreviations.
    s = re.sub(r"\bD\.(?=[A-ZÁÉÍÓÚÑ])", "D. ", s)
    s = re.sub(r"\bDª\.(?=[A-ZÁÉÍÓÚÑ])", "Dª. ", s)
    # Drop honorifics/titles at the beginning (may appear repeated / mixed).
    # Order matters: match "Dª" before "D" to avoid leaving a dangling "ª".
    s = re.sub(r"^(?:(?:Excmo|Excma|Ilmo|Ilma|Sra|Sr|Dª|D)\.?\s*)+", "", s, flags=re.I)
    s = s.lstrip(" .ª")
    return normalize_ws(s)


def parse_party_suffix(text: str) -> tuple[str, str | None]:
    s = normalize_ws(text)
    m = re.search(r"\(([^()]{1,16})\)\s*$", s)
    if not m:
        return s, None
    party = normalize_ws(m.group(1))
    base = normalize_ws(s[: m.start()].rstrip(" ."))
    return base, party or None


def party_from_group_title(title: str) -> str | None:
    t = normalize_ws(title).lower()
    if "partido popular" in t:
        return "PP"
    if "socialista obrero" in t:
        return "PSOE"
    if " vox" in f" {t}":
        return "VOX"
    if "movimiento por la dignidad" in t:
        return "MDyC"
    if "ceuta ya" in t:
        return "Ceuta Ya"
    return None


def parse_ceuta_asamblea_records(html: str) -> list[dict[str, Any]]:
    # Extract <h4>Title</h4> + following <ul>...</ul>.
    # The "Ceuta Ya" and "no adscritos" blocks are wrapped inside <aside>, but the pattern still applies.
    # Keyed by normalized full name. Prefer group membership rows over Mesa rows.
    by_name: dict[str, dict[str, Any]] = {}

    for m in re.finditer(
        r"<h4[^>]*>(?P<title>.*?)</h4>\s*(?:<aside>\s*)?<ul>(?P<ul>.*?)</ul>",
        html,
        flags=re.I | re.S,
    ):
        title = normalize_ws(unescape(strip_tags(m.group("title"))))
        ul_html = m.group("ul")
        items = re.findall(r"<li[^>]*>(.*?)</li>", ul_html, flags=re.I | re.S)
        if not items:
            continue

        default_party = party_from_group_title(title)
        section_kind = "mesa" if ("mesa" in title.lower() or "presidente" in title.lower()) else "grupo"
        priority = 2 if section_kind == "grupo" else 1

        for item in items:
            raw_item_text = normalize_ws(unescape(strip_tags(item)))
            base_text, party_suffix = parse_party_suffix(raw_item_text)
            full_name = clean_name(base_text)
            if not full_name:
                continue

            # Prefer the explicit (PP)/(PSOE)/... suffix when present.
            party = party_suffix or default_party

            key_name = full_name.lower()

            # Stable-ish ID without an official person id.
            source_record_id = sha256_bytes(
                stable_json(
                    {
                        "term": "2023-2027",
                        "full_name": full_name,
                        "institution": "Asamblea de Ceuta",
                    }
                ).encode("utf-8")
            )[:24]

            candidate = {
                "source_record_id": f"ceuta:{source_record_id}",
                "full_name": full_name,
                "party_name": party,
                "group_title": title,
                "role_section": title,
                "is_active": True,
                "_priority": priority,
            }
            existing = by_name.get(key_name)
            if existing is None or int(candidate["_priority"]) > int(existing.get("_priority", 0)):
                by_name[key_name] = candidate

    records = [r for r in by_name.values()]
    for r in records:
        r.pop("_priority", None)
    records.sort(key=lambda r: str(r.get("full_name") or ""))

    if not records:
        raise RuntimeError("No se encontraron miembros en Asamblea de Ceuta (legislatura 2023/2027)")
    return records


class AsambleaCeutaDiputadosConnector(BaseConnector):
    source_id = "asamblea_ceuta_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or CEUTA_ASAMBLEA_URL

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
            import urllib.request

            req = urllib.request.Request(resolved_url, headers={"Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = resp.read()
                ct = resp.headers.get("Content-Type")

            html = decode_html(payload, ct)
            records = parse_ceuta_asamblea_records(html)
            payload_obj = {"source": "ceuta_es_html", "url": resolved_url, "records": records}
            out = json.dumps(payload_obj, ensure_ascii=True, sort_keys=True).encode("utf-8")
            fetched_at = now_utc_iso()
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(out)
            return Extracted(
                source_id=self.source_id,
                source_url=resolved_url,
                resolved_url=resolved_url,
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(out),
                content_type="application/json",
                bytes=len(out),
                note="network",
                payload=out,
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

        source_record_id = pick_value(record, ("source_record_id", "id"))
        if not source_record_id:
            source_record_id = sha256_bytes(stable_json(record).encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        is_active = bool(record.get("is_active", True))
        return {
            "full_name": full_name,
            "given_name": given_name,
            "family_name": family_name,
            "gender": None,
            "party_name": normalize_ws(str(record.get("party_name") or "")) or None,
            "territory_code": "",
            "institution_territory_code": "ES-CE",
            "birth_date": parse_date_flexible(pick_value(record, ("birth_date", "fecha_nacimiento"))),
            "start_date": None,
            "end_date": snapshot_date if (snapshot_date and not is_active) else None,
            "is_active": is_active,
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
