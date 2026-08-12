"""Bounded discovery and gap accounting for official PLACSP archives."""

from __future__ import annotations

import hashlib
import re
import ssl
import urllib.request
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from publicdata_core.util import now_utc_iso

DEFAULT_CATALOG_URL = (
    "https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/"
    "Paginas/licitacionescontratante.aspx"
)
DEFAULT_START_YEAR = 2012
DEFAULT_MAX_CATALOG_BYTES = 5 * 1024 * 1024
_ARCHIVE_RE = re.compile(
    r"licitacionesPerfilesContratanteCompleto3_(?P<period>\d{4}|\d{6})\.zip$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PlacspArchiveLink:
    period: str
    source_url: str
    archive_kind: str


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "a":
            return
        for key, value in attrs:
            if key.casefold() == "href" and value:
                self.hrefs.append(value.strip())


def parse_catalog_links(html_text: str, *, catalog_url: str) -> list[PlacspArchiveLink]:
    parser = _LinkParser()
    parser.feed(html_text)
    by_period: dict[str, PlacspArchiveLink] = {}
    for href in parser.hrefs:
        source_url = urljoin(catalog_url, href)
        parsed_url = urlparse(source_url)
        match = _ARCHIVE_RE.search(parsed_url.path)
        if match is None:
            continue
        if parsed_url.scheme != "https":
            raise ValueError("PLACSP catalog contains a non-HTTPS archive URL")
        period = match.group("period")
        link = PlacspArchiveLink(
            period=period,
            source_url=source_url,
            archive_kind="annual" if len(period) == 4 else "monthly",
        )
        existing = by_period.get(period)
        if existing is not None and existing.source_url != source_url:
            raise ValueError(f"PLACSP catalog has conflicting URLs for period {period}")
        by_period[period] = link
    return [by_period[period] for period in sorted(by_period)]


def _fetch_catalog(
    catalog_url: str,
    *,
    timeout: int,
    max_bytes: int,
    ca_bundle: Path | None,
) -> tuple[bytes, str]:
    if not catalog_url.startswith("https://"):
        raise ValueError("PLACSP catalog URL must use HTTPS")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    context = ssl.create_default_context(cafile=str(ca_bundle) if ca_bundle else None)
    request = urllib.request.Request(
        catalog_url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "vota-con-la-chola-public-data/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            raise ValueError("PLACSP catalog exceeds max_bytes")
        payload = response.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise ValueError("PLACSP catalog exceeds max_bytes")
        charset = response.headers.get_content_charset() or "utf-8"
    return payload, charset


def build_catalog_report(
    html_bytes: bytes,
    *,
    catalog_url: str,
    charset: str = "utf-8",
    as_of_date: date,
    start_year: int = DEFAULT_START_YEAR,
) -> dict[str, object]:
    if start_year < DEFAULT_START_YEAR or start_year > as_of_date.year:
        raise ValueError("start_year must be between 2012 and as_of year")
    links = parse_catalog_links(
        html_bytes.decode(charset, errors="replace"),
        catalog_url=catalog_url,
    )
    annual = {int(link.period): link for link in links if len(link.period) == 4}
    monthly = {
        (int(link.period[:4]), int(link.period[4:])): link
        for link in links
        if len(link.period) == 6
    }
    expected_annual = list(range(start_year, as_of_date.year))
    expected_monthly = [
        (as_of_date.year, month) for month in range(1, as_of_date.month + 1)
    ]
    missing_annual = [str(year) for year in expected_annual if year not in annual]
    missing_monthly = [
        f"{year}{month:02d}"
        for year, month in expected_monthly
        if (year, month) not in monthly
    ]
    selected = [annual[year] for year in expected_annual if year in annual]
    selected.extend(
        monthly[(year, month)]
        for year, month in expected_monthly
        if (year, month) in monthly
    )
    selected.sort(key=lambda link: link.period)
    checks = {
        "archive_links_found": bool(links),
        "closed_years_gap_free": not missing_annual,
        "current_year_months_gap_free": not missing_monthly,
        "selected_periods_unique": len({link.period for link in selected})
        == len(selected),
        "selected_urls_https": all(link.source_url.startswith("https://") for link in selected),
        "history_starts_at_requested_year": bool(selected)
        and selected[0].period == str(start_year),
    }
    status = "ok" if all(checks.values()) else "degraded"
    return {
        "schema_version": "placsp_archive_catalog_v1",
        "status": status,
        "catalog_url": catalog_url,
        "as_of_date": as_of_date.isoformat(),
        "discovered_at": now_utc_iso(),
        "catalog_content_sha256": hashlib.sha256(html_bytes).hexdigest(),
        "catalog_bytes": len(html_bytes),
        "selection_strategy": "closed_year_annual_plus_current_year_monthly",
        "start_year": start_year,
        "discovered": {
            "archive_links": len(links),
            "annual_links": len(annual),
            "monthly_links": len(monthly),
        },
        "expected": {
            "closed_year_annual_archives": len(expected_annual),
            "current_year_monthly_archives": len(expected_monthly),
            "selected_archives": len(expected_annual) + len(expected_monthly),
        },
        "missing": {
            "annual_periods": missing_annual,
            "monthly_periods": missing_monthly,
        },
        "archives": [
            {
                "period": link.period,
                "archive_kind": link.archive_kind,
                "source_url": link.source_url,
            }
            for link in selected
        ],
        "checks": checks,
        "limitations": [
            "Current-year monthly archives are mutable until their month closes.",
            "Catalog discovery proves expected archive links, not downloaded content completeness.",
            "Annual archives may contain repeated revisions; record-version reconciliation remains mandatory.",
        ],
    }


def discover_catalog(
    *,
    catalog_url: str = DEFAULT_CATALOG_URL,
    as_of_date: date,
    start_year: int = DEFAULT_START_YEAR,
    timeout: int = 30,
    max_bytes: int = DEFAULT_MAX_CATALOG_BYTES,
    ca_bundle: Path | None = None,
) -> dict[str, object]:
    payload, charset = _fetch_catalog(
        catalog_url,
        timeout=timeout,
        max_bytes=max_bytes,
        ca_bundle=ca_bundle,
    )
    report = build_catalog_report(
        payload,
        catalog_url=catalog_url,
        charset=charset,
        as_of_date=as_of_date,
        start_year=start_year,
    )
    report["transport_security"] = (
        "verified_custom_ca" if ca_bundle else "verified_system_ca"
    )
    return report
