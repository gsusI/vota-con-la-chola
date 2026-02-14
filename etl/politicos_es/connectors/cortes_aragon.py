from __future__ import annotations

import json
import re
import urllib.request
import http.cookiejar
import ssl
from urllib.parse import urljoin
from urllib.parse import urlsplit
from html import unescape
from pathlib import Path
from typing import Any

from ..config import BASE_HEADERS, SOURCE_CONFIG
from ..fetch import fetch_payload
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


CA_BASE = "https://www.cortesaragon.es"
# Cortes de Aragón XI Legislatura:
# - uiddip list (activos): uidcom=-2
# - uiddip list (han causado baja): uidcom=-99
CA_ACTIVE_URL = (
    f"{CA_BASE}/Quienes-somos.2250.0.html"
    "?no_cache=1&tx_t3comunicacion_pi3%5Bnumleg%5D=11"
    "&tx_t3comunicacion_pi3%5Btipinf%5D=3&tx_t3comunicacion_pi3%5Buidcom%5D=-2#verContenido"
)
CA_INACTIVE_URL = (
    f"{CA_BASE}/Quienes-somos.2250.0.html"
    "?no_cache=1&tx_t3comunicacion_pi3%5Bnumleg%5D=11"
    "&tx_t3comunicacion_pi3%5Btipinf%5D=3&tx_t3comunicacion_pi3%5Buidcom%5D=-99#verContenido"
)


def decode_ca_html(payload: bytes, content_type: str | None) -> str:
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


def get_ca_html_with_bot_cookie(url: str, timeout: int) -> tuple[bytes, str | None]:
    """Fetch HTML from cortesaragon.es using its JS redirect + cookie-based bot mitigation.

    Flow:
    1) GET url -> HTML with <script>window.location.href='/redirect_.../path'</script>
    2) GET https://www.cortesaragon.es/redirect_.../path -> 307 to original + sets bot_mitigation_cookie
    3) GET url again -> real HTML
    """
    jar = http.cookiejar.CookieJar()
    parsed = urlsplit(url)
    urls_to_try = [url]
    if parsed.scheme == "https":
        urls_to_try.append(f"http://{parsed.netloc}{parsed.path}{'?' + parsed.query if parsed.query else ''}")

    for current_url in urls_to_try:
        current_scheme = urlsplit(current_url).scheme
        ctx = ssl._create_unverified_context()  # noqa: S501
        opener = urllib.request.build_opener(
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(context=ctx),
            urllib.request.HTTPCookieProcessor(jar),
        )

        def open_bytes(target: str) -> tuple[bytes, str | None]:
            req = urllib.request.Request(target, headers=dict(BASE_HEADERS))
            with opener.open(req, timeout=timeout) as resp:
                return resp.read(), resp.headers.get("Content-Type")

        try:
            payload, ct = open_bytes(current_url)
            html = decode_ca_html(payload, ct)
            m = re.search(r"window\.location\.href='([^']+)'", html, flags=re.I)
            if m:
                redirect_path = m.group(1)
                if redirect_path.startswith("/redirect_"):
                    # Hit redirect to set the final cookie, then retry original.
                    redirect_url = urljoin(current_url, redirect_path)
                    _ = open_bytes(redirect_url)
                    payload, ct = open_bytes(current_url)
            return payload, ct
        except Exception:
            if current_url != urls_to_try[-1]:
                continue
            raise


def normalize_ca_group(label: str) -> str:
    text = normalize_ws(label)
    if not text:
        return ""
    # Often: "G.P. Socialista" or "Presidenta (GPVOX)" or "Vicepresidente Primero (GPPCA)"
    if "G.P." in text:
        idx = text.find("G.P.")
        return normalize_ws(text[idx:])
    m = re.search(r"\((GP[A-Z0-9]+)\)\s*$", text)
    if m:
        return normalize_ws(m.group(1))
    return text


def parse_ca_deputies(list_html: str, *, min_expected: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for m in re.finditer(
        r'<div class="team-title">\s*<h4[^>]*>.*?uiddip%5D=(?P<uid>\d+)[^"]*".*?>(?P<name>[^<]+)</a>.*?</h4>\s*<span>(?P<label>[^<]+)',
        list_html,
        flags=re.I | re.S,
    ):
        uid = m.group("uid")
        if uid in seen:
            continue
        seen.add(uid)
        name = normalize_ws(unescape(strip_tags(m.group("name"))))
        label = normalize_ws(unescape(strip_tags(m.group("label"))))
        group = normalize_ca_group(label)

        records.append(
            {
                "source_record_id": f"uiddip:{uid};leg:11",
                "uiddip": uid,
                "full_name": name,
                "group_name": group,
                "label": label,
            }
        )

    if not records:
        raise RuntimeError("No se encontraron diputados en Cortes de Aragon (lista XI)")
    if len(records) < min_expected:
        raise RuntimeError(
            f"Extraccion sospechosa: solo {len(records)} diputados (min esperado: {min_expected})"
        )
    return records


def build_cortes_aragon_records(timeout: int) -> list[dict[str, Any]]:
    payload, ct = get_ca_html_with_bot_cookie(CA_ACTIVE_URL, timeout)
    active_html = decode_ca_html(payload, ct)
    active = parse_ca_deputies(active_html, min_expected=50)
    for r in active:
        r["is_active"] = True

    payload, ct = get_ca_html_with_bot_cookie(CA_INACTIVE_URL, timeout)
    inactive_html = decode_ca_html(payload, ct)
    inactive = parse_ca_deputies(inactive_html, min_expected=1)
    for r in inactive:
        r["is_active"] = False

    # Merge (prefer active if a record ever appears in both lists).
    merged: dict[str, dict[str, Any]] = {}
    for r in inactive:
        merged[str(r.get("source_record_id") or "")] = r
    for r in active:
        merged[str(r.get("source_record_id") or "")] = r
    return [merged[k] for k in sorted(merged.keys()) if k]


class CortesAragonDiputadosConnector(BaseConnector):
    source_id = "cortes_aragon_diputados"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or CA_ACTIVE_URL

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
            records = build_cortes_aragon_records(timeout)
            payload_obj = {
                "source": "cortesaragon_html",
                "active_list_url": CA_ACTIVE_URL,
                "inactive_list_url": CA_INACTIVE_URL,
                "records": records,
            }
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
        is_active = bool(record.get("is_active", True))

        source_record_id = pick_value(record, ("source_record_id", "uiddip", "id"))
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
            "institution_territory_code": "ES-AR",
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
