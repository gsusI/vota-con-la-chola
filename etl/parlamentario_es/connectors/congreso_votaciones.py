from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

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
LEGS_SELECT_RE = re.compile(
    r'<select[^>]*id="_votaciones_legislatura"[^>]*>(?P<body>.*?)</select>',
    re.I | re.S,
)
OPTION_VALUE_RE = re.compile(r'<option[^>]*value="(?P<v>\d+)"', re.I)
OPTION_SELECTED_VALUE_RE = re.compile(r'<option(?P<attrs>[^>]*)>', re.I)
DIAS_VOTACIONES_RE = re.compile(r"var\s+diasVotaciones\s*=\s*\[(?P<body>[^\]]*)\]", re.I | re.S)


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


def _romanize(num: int) -> str:
    if num <= 0:
        return str(num)
    vals = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    out = []
    n = num
    for v, s in vals:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


def _extract_legislatures_from_html(html: str) -> list[int]:
    m = LEGS_SELECT_RE.search(html)
    if not m:
        return []
    body = m.group("body")
    vals = [int(mm.group("v")) for mm in OPTION_VALUE_RE.finditer(body)]
    seen: set[int] = set()
    out: list[int] = []
    for v in vals:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _extract_selected_legislature(html: str) -> int | None:
    m = LEGS_SELECT_RE.search(html)
    if not m:
        return None
    body = m.group("body")
    for mm in OPTION_SELECTED_VALUE_RE.finditer(body):
        attrs = mm.group("attrs")
        attrs_low = attrs.lower()
        if "selected" not in attrs_low:
            continue
        vm = re.search(r'value="(?P<v>\d+)"', attrs, flags=re.I)
        if vm:
            return int(vm.group("v"))
    return None


def _extract_vote_days_from_html(html: str) -> list[str]:
    m = DIAS_VOTACIONES_RE.search(html)
    if not m:
        return []
    body = m.group("body")
    out: list[str] = []
    for item in body.split(","):
        txt = normalize_ws(item)
        if not txt:
            continue
        if txt.isdigit() and len(txt) == 8:
            out.append(txt)
    return out


def _format_ymd_as_ddmmyyyy(ymd: str) -> str:
    return f"{ymd[6:8]}/{ymd[4:6]}/{ymd[0:4]}"


def _parse_leg_filter(value: Any) -> list[int]:
    txt = normalize_ws(str(value or ""))
    if not txt:
        return []
    out: list[int] = []
    for token in re.split(r"[,\s;]+", txt):
        t = normalize_ws(token)
        if not t:
            continue
        if t.isdigit():
            out.append(int(t))
    return out


def _base_congreso_url(resolved_url: str) -> str:
    parsed = urlparse(resolved_url)
    if parsed.scheme and parsed.netloc:
        path = parsed.path or "/es/opendata/votaciones"
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    return SOURCE_CONFIG["congreso_votaciones"]["default_url"]


def _build_leg_day_url(base_url: str, *, leg_roman: str, target_date_ddmmyyyy: str | None) -> str:
    q: dict[str, str] = {
        "p_p_id": "votaciones",
        "p_p_lifecycle": "0",
        "p_p_state": "normal",
        "p_p_mode": "view",
        "targetLegislatura": leg_roman,
    }
    if target_date_ddmmyyyy:
        q["targetDate"] = target_date_ddmmyyyy
    return f"{base_url}?{urlencode(q)}"


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
        leg_filter = _parse_leg_filter(options.get("congreso_legs"))

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
        base_url = _base_congreso_url(resolved_url)
        discovered_legs = _extract_legislatures_from_html(html)
        selected_leg = _extract_selected_legislature(html)
        target_legs = leg_filter or discovered_legs or [15]
        target_legs = sorted({int(v) for v in target_legs if int(v) > 0}, reverse=True)

        # Discover vote detail URLs by iterating voting days for each legislature.
        catalog_failures: list[str] = []
        discovered_day_pages = 0
        discovered_days_total = 0
        vote_urls: list[str] = []
        seen_urls: set[str] = set()

        for leg in target_legs:
            leg_roman = _romanize(leg)
            leg_url = _build_leg_day_url(base_url, leg_roman=leg_roman, target_date_ddmmyyyy=None)
            leg_html = html if selected_leg == leg else None
            if leg_html is None:
                try:
                    leg_html = http_get_bytes(
                        leg_url,
                        timeout,
                        headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                    )[0].decode("utf-8", errors="replace")
                except Exception as exc:  # noqa: BLE001
                    catalog_failures.append(f"{leg_url} -> {type(exc).__name__}: {exc}")
                    if strict_network:
                        raise
                    continue

            days = _extract_vote_days_from_html(leg_html)
            filtered_days: list[str] = []
            for ymd in days:
                iso = f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"
                if since_date and iso < str(since_date):
                    continue
                if until_date and iso > str(until_date):
                    continue
                filtered_days.append(ymd)
            discovered_days_total += len(filtered_days)

            # Fast path for debug caps: newest days first.
            if isinstance(max_votes, int) and max_votes > 0:
                filtered_days = sorted(filtered_days, reverse=True)
            else:
                filtered_days = sorted(filtered_days)

            for ymd in filtered_days:
                day_url = _build_leg_day_url(base_url, leg_roman=leg_roman, target_date_ddmmyyyy=_format_ymd_as_ddmmyyyy(ymd))
                try:
                    day_html = http_get_bytes(
                        day_url,
                        timeout,
                        headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                    )[0].decode("utf-8", errors="replace")
                except Exception as exc:  # noqa: BLE001
                    catalog_failures.append(f"{day_url} -> {type(exc).__name__}: {exc}")
                    if strict_network:
                        raise
                    continue

                discovered_day_pages += 1
                hrefs = [m.group("href") for m in VOTE_JSON_RE.finditer(day_html)]
                for href in hrefs:
                    u = urljoin(CONGRESO_BASE, href)
                    if u in seen_urls:
                        continue
                    seen_urls.add(u)
                    vote_urls.append(u)

                if isinstance(max_votes, int) and max_votes > 0 and len(vote_urls) >= max_votes:
                    break
            if isinstance(max_votes, int) and max_votes > 0 and len(vote_urls) >= max_votes:
                break

        filtered_urls = list(vote_urls)
        if isinstance(max_votes, int) and max_votes > 0:
            filtered_urls = filtered_urls[:max_votes]

        detail_failures: list[str] = []
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
                detail_failures.append(f"{url} -> {type(exc).__name__}: {exc}")
                if strict_network:
                    raise

        meta = {
            "source": "congreso_votaciones_catalog",
            "list_url": resolved_url,
            "target_legs": target_legs,
            "discovered_days_total": discovered_days_total,
            "day_pages_fetched": discovered_day_pages,
            "vote_urls_discovered": len(vote_urls),
            "vote_urls_filtered": len(filtered_urls),
            "catalog_failures": catalog_failures,
            "detail_failures": detail_failures,
        }
        payload_bytes = stable_json(meta).encode("utf-8")
        raw_path = raw_output_path(raw_dir, self.source_id, "json")
        raw_path.write_bytes(payload_bytes)

        note = "network"
        if catalog_failures or detail_failures:
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
