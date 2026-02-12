from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from etl.politicos_es.util import normalize_ws, now_utc_iso, parse_date_flexible, sha256_bytes, stable_json

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes
from ..raw import raw_output_path
from ..types import Extracted
from .base import BaseConnector


CONGRESO_BASE = "https://www.congreso.es"

# Detail JSON URLs look like:
# /webpublica/opendata/votaciones/Leg15/Sesion159/20260212/Votacion001/VOT_20260212114304.json
VOTE_JSON_RE = re.compile(
    r'(?P<href>/webpublica/opendata/votaciones/Leg(?P<leg>\d+)/Sesion(?P<ses>\d+)/(?P<yyyymmdd>\d{8})/Votacion(?P<vnum>\d{3})/[^"\' ]+\.json)'
)


def _iso_from_ddmmyyyy(value: str | None) -> str | None:
    # Congreso uses "12/2/2026" (no zero padding).
    if not value:
        return None
    text = normalize_ws(value)
    # parse_date_flexible supports %d/%m/%Y but expects 2-digit day/month; normalize.
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if m:
        dd = m.group(1).zfill(2)
        mm = m.group(2).zfill(2)
        yyyy = m.group(3)
        return parse_date_flexible(f"{dd}/{mm}/{yyyy}")
    return parse_date_flexible(text)


class CongresoVotacionesConnector(BaseConnector):
    source_id = "congreso_votaciones"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or SOURCE_CONFIG[self.source_id]["default_url"]

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
        options: dict[str, Any] | None = None,
    ) -> Extracted:
        options = dict(options or {})
        max_votes = options.get("max_votes")
        since_date = options.get("since_date")  # ISO
        until_date = options.get("until_date")  # ISO

        records: list[dict[str, Any]] = []
        content_type = None

        if from_file:
            # Accept:
            # - a single vote JSON file
            # - a directory containing many vote JSON files
            paths: list[Path]
            if from_file.is_dir():
                paths = sorted([p for p in from_file.glob("*.json") if p.is_file()])
                note = "from-dir"
            else:
                paths = [from_file]
                note = "from-file"

            for p in paths:
                payload = json.loads(p.read_bytes())
                info = payload.get("informacion") or {}
                sesion = info.get("sesion")
                numero = info.get("numeroVotacion")
                fecha_iso = _iso_from_ddmmyyyy(info.get("fecha"))
                records.append(
                    {
                        "detail_url": f"file://{p.resolve()}",
                        "legislature": None,
                        "session_number": sesion,
                        "vote_number": numero,
                        "vote_date": fecha_iso,
                        "payload": payload,
                    }
                )

            meta = {
                "source": "congreso_votaciones_from_file",
                "paths": [str(p) for p in paths],
                "records": len(records),
            }
            payload_bytes = stable_json(meta).encode("utf-8")
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(payload_bytes)
            return Extracted(
                source_id=self.source_id,
                source_url=f"file://{from_file.resolve()}",
                resolved_url=f"file://{from_file.resolve()}",
                fetched_at=now_utc_iso(),
                raw_path=raw_path,
                content_sha256=sha256_bytes(payload_bytes),
                content_type=None,
                bytes=len(payload_bytes),
                note=note,
                payload=payload_bytes,
                records=records,
            )

        resolved_url = self.resolve_url(url_override, timeout)
        html_bytes, content_type = http_get_bytes(
            resolved_url,
            timeout,
            headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        )
        html = html_bytes.decode("utf-8", errors="replace")

        hrefs = [m.group("href") for m in VOTE_JSON_RE.finditer(html)]
        # Deduplicate but keep deterministic order.
        vote_urls = []
        seen: set[str] = set()
        for href in hrefs:
            url = urljoin(CONGRESO_BASE, href)
            if url in seen:
                continue
            seen.add(url)
            vote_urls.append(url)

        # Filter by date using the path segment yyyymmdd.
        filtered_urls: list[str] = []
        for url in vote_urls:
            m = re.search(r"/(?P<yyyymmdd>\d{8})/Votacion", url)
            if not m:
                continue
            ymd = m.group("yyyymmdd")
            iso = f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"
            if since_date and iso < str(since_date):
                continue
            if until_date and iso > str(until_date):
                continue
            filtered_urls.append(url)

        if isinstance(max_votes, int) and max_votes > 0:
            filtered_urls = filtered_urls[-max_votes:]

        failures: list[str] = []
        for url in filtered_urls:
            try:
                payload_bytes, ct = http_get_bytes(url, timeout, headers={"Accept": "application/json"})
                if ct and "json" not in ct.lower():
                    # Some endpoints can return PDF/HTML; ignore.
                    raise RuntimeError(f"content_type inesperado: {ct}")
                payload = json.loads(payload_bytes)
                info = payload.get("informacion") or {}
                records.append(
                    {
                        "detail_url": url,
                        "legislature": re.search(r"/Leg(\d+)/", url).group(1) if re.search(r"/Leg(\d+)/", url) else None,
                        "session_number": info.get("sesion"),
                        "vote_number": info.get("numeroVotacion"),
                        "vote_date": _iso_from_ddmmyyyy(info.get("fecha")),
                        "payload": payload,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{url} -> {type(exc).__name__}: {exc}")
                if strict_network:
                    raise

        meta = {
            "source": "congreso_votaciones_catalog",
            "list_url": resolved_url,
            "vote_urls_total": len(vote_urls),
            "vote_urls_filtered": len(filtered_urls),
            "failures": failures,
        }
        payload_bytes = stable_json(meta).encode("utf-8")
        raw_path = raw_output_path(raw_dir, self.source_id, "json")
        raw_path.write_bytes(payload_bytes)

        note = "network"
        if failures:
            note = "network-partial"

        return Extracted(
            source_id=self.source_id,
            source_url=resolved_url,
            resolved_url=resolved_url,
            fetched_at=now_utc_iso(),
            raw_path=raw_path,
            content_sha256=sha256_bytes(payload_bytes),
            content_type=content_type,
            bytes=len(payload_bytes),
            note=note,
            payload=payload_bytes,
            records=records,
        )
