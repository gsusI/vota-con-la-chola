#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

import xml.etree.ElementTree as ET

DEFAULT_BASE_URL = "https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/votaciones/index.html"
DEFAULT_OUT_DIR = Path("etl/data/raw/senado_votaciones_xmls")
UA = "Mozilla/5.0 (compatible; etl-script/1.0)"
SENADO_BASE = "https://www.senado.es"
SENADO_TIPO9_URL = f"{SENADO_BASE}/web/ficopendataservlet?tipoFich=9&legis={{leg}}"

LEGS_SELECT_RE = re.compile(r'<select[^>]*id="legis"[^>]*>(?P<body>.*?)</select>', re.I | re.S)
OPTION_RE = re.compile(r'<option[^>]*value="(?P<v>\d+)"[^>]*>(?P<label>.*?)</option>', re.I | re.S)
TIPO12_RE = re.compile(r'href="([^"]*tipoFich=12[^"]*)"', re.I)


def _looks_html(payload: bytes) -> bool:
    if not payload:
        return True
    text = payload.lstrip()[:1024].lower()
    if not text:
        return True
    if text.startswith(b"<!doctype html") or text.startswith(b"<html"):
        return True
    return b"<html" in text


def _looks_xml(payload: bytes) -> bool:
    if not payload or _looks_html(payload):
        return False
    txt = payload.lstrip()[:4].lower()
    return txt.startswith(b"<?xm") or txt.startswith(b"<")


@dataclass
class LegCatalog:
    legislatura: int
    label: str
    urls: list[str]
    direct_count: int
    fallback_count: int
    errors: list[str]


@dataclass
class DownloadItem:
    legislatura: int
    label: str
    url: str
    out_path: str
    status: str
    bytes: int = 0
    sha256: str = ""


def _safe_read_text(url: str, timeout: int, accept: str = "text/html") -> str:
    req = Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return data.decode("utf-8", errors="ignore")


def _read_binary(url: str, timeout: int) -> tuple[bytes, str | None]:
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/xml,text/xml,*/*"})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        ct = resp.headers.get("Content-Type")
    return data, ct


def _set_legis_query(url: str, leg: int) -> str:
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    q["legis"] = [str(leg)]
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(q, doseq=True), ""))


def _extract_legislatures(page_html: str) -> list[tuple[int, str]]:
    m = LEGS_SELECT_RE.search(page_html)
    if not m:
        return []
    matches = list(OPTION_RE.finditer(m.group("body")))
    seen: set[int] = set()
    out: list[tuple[int, str]] = []
    for mm in matches:
        if not mm.group("v").isdigit():
            continue
        leg = int(mm.group("v"))
        if leg in seen:
            continue
        seen.add(leg)
        label = re.sub(r"\s+", " ", html.unescape(mm.group("label") or "")).strip()
        out.append((leg, label or str(leg)))
    return out


def _extract_urls_from_links(html_text: str, pattern: re.Pattern[str]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for href in pattern.findall(html_text):
        clean = html.unescape(href)
        clean = re.sub(r";jsessionid=[^?]+", "", clean, flags=re.I)
        parsed = urlparse(urljoin(SENADO_BASE, clean))
        parsed = parsed._replace(fragment="")
        full = parsed.geturl()
        if full in seen:
            continue
        seen.add(full)
        urls.append(full)
    return urls


def _tipo12_urls_from_tipo9_xml(payload: bytes) -> list[str]:
    if not payload:
        return []
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return []
    if root.tag != "listaIniciativasLegislativas":
        return []
    out: list[str] = []
    seen: set[str] = set()
    for node in root.findall("./iniciativa"):
        u = node.findtext("./votaciones/fichGenVotaciones/fichUrlVotaciones")
        if not u:
            continue
        full = urljoin(SENADO_BASE, str(u).strip())
        if full in seen:
            continue
        seen.add(full)
        out.append(full)
    return out


def _safe_name(value: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", value).strip("._")


def _filename_for_url(leg: int, label: str, url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    parts = [f"leg{leg:02d}", (label or "leg").replace(" ", "_")]
    for key in ("tipoEx", "numEx", "tipoFich", "legis"):
        val = (qs.get(key) or [""])[0]
        if val:
            parts.append(f"{key}_{val}")
    fingerprint = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    parts.append(fingerprint)
    return f"{_safe_name('_'.join(parts))}.xml"


def _parse_leg_filter(value: Any) -> list[int]:
    txt = (str(value or "").strip())
    if not txt:
        return []
    out: list[int] = []
    for token in re.split(r"[,\s;]+", txt):
        if token.isdigit():
            out.append(int(token))
    return out


def _collect_leg_urls(
    leg_info: tuple[int, str],
    base_url: str,
    timeout: int,
) -> LegCatalog:
    leg, label = leg_info
    errors: list[str] = []
    urls: list[str] = []
    try:
        page_url = _set_legis_query(base_url, leg)
        html_text = _safe_read_text(page_url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return LegCatalog(leg, label, [], 0, 0, [f"{page_url if 'page_url' in locals() else base_url} -> {type(exc).__name__}: {exc}"])

    direct_urls = _extract_urls_from_links(html_text, TIPO12_RE)
    urls.extend(direct_urls)

    fallback_count = 0
    tipo9_url = SENADO_TIPO9_URL.format(leg=leg)
    try:
        payload, ct = _read_binary(tipo9_url, timeout=timeout)
        if ct and "xml" not in ct.lower():
            raise RuntimeError(f"content-type inesperado: {ct}")
        if not _looks_xml(payload):
            raise RuntimeError("response is not XML-like payload")
        derived = _tipo12_urls_from_tipo9_xml(payload)
        for u in derived:
            if u not in urls:
                urls.append(u)
                fallback_count += 1
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{tipo9_url} -> {type(exc).__name__}: {exc}")

    return LegCatalog(leg, label, urls, len(direct_urls), fallback_count, errors)


def _download_one(item: tuple[int, str, str], out_dir: Path, timeout: int) -> DownloadItem:
    leg, label, url = item
    out_path = out_dir / _filename_for_url(leg, label, url)
    try:
        payload, ct = _read_binary(url, timeout=timeout)
        if ct and "xml" not in ct.lower():
            raise RuntimeError(f"content-type inesperado: {ct}")
        if not _looks_xml(payload):
            raise RuntimeError("response is not XML-like payload")
        if not payload:
            return DownloadItem(leg, label, url, str(out_path), "EMPTY")
        out_path.write_bytes(payload)
        h = hashlib.sha256(payload).hexdigest()
        return DownloadItem(
            legislatura=leg,
            label=label,
            url=url,
            out_path=str(out_path),
            status="OK",
            bytes=len(payload),
            sha256=h,
        )
    except (HTTPError, URLError, OSError, ValueError, RuntimeError) as exc:
        return DownloadItem(
            legislatura=leg,
            label=label,
            url=url,
            out_path=str(out_path),
            status=f"ERROR: {type(exc).__name__}: {exc}",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Descarga XMLs de votaciones del Senado desde el catálogo por legislatura")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-workers", type=int, default=20)
    parser.add_argument("--check-only", action="store_true", help="Solo detecta URLs y genera reporte; no descarga")
    parser.add_argument("--legislatures", default="", help="Filtrar legislaturas por número separadas por coma (ej. 15,14)")
    parser.add_argument("--report-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url
    timeout = int(args.timeout)
    workers = max(1, int(args.max_workers))

    out_dir = Path(args.out_dir)
    if not args.check_only:
        out_dir.mkdir(parents=True, exist_ok=True)

    filter_legs = set(_parse_leg_filter(args.legislatures))
    base_html = _safe_read_text(base_url, timeout=timeout)
    legs = _extract_legislatures(base_html)
    if filter_legs:
        if legs:
            legs = [(leg, label) for leg, label in legs if leg in filter_legs]
        else:
            legs = [(leg, str(leg)) for leg in sorted(filter_legs, reverse=True)]
        if not legs:
            print(f"No se encontraron legislaturas para el filtro: {sorted(filter_legs)}")
            return 1
    elif not legs:
        print("WARN: no fue posible detectar legislaturas en el catálogo principal; usando fallback 25..1")
        legs = [(leg, str(leg)) for leg in range(25, 0, -1)]

    discovered: list[LegCatalog] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_collect_leg_urls, leg_info, base_url, timeout) for leg_info in legs]
        for fut in concurrent.futures.as_completed(futures):
            discovered.append(fut.result())

    discovered.sort(key=lambda x: x.legislatura, reverse=True)

    total_urls = sum(len(item.urls) for item in discovered)
    print(f"Legislaturas detectadas: {len(discovered)}")
    for item in discovered:
        if not item.errors and item.urls:
            print(
                f"Leg {item.legislatura:>2} [{item.label}] -> total {len(item.urls)} "
                f"(directos: {item.direct_count}, fallback: {item.fallback_count})"
            )
        elif item.errors and item.urls:
            print(
                f"Leg {item.legislatura:>2} [{item.label}] -> total {len(item.urls)} "
                f"(directos: {item.direct_count}, fallback: {item.fallback_count}) [with warnings: {len(item.errors)}]"
            )
        else:
            print(f"Leg {item.legislatura:>2} [{item.label}] -> 0 URLs")

    if not args.check_only:
        targets: list[tuple[int, str, str]] = []
        for item in discovered:
            for url in item.urls:
                targets.append((item.legislatura, item.label, url))

        if not targets:
            print("No hay XMLs para descargar.")
            return 2

        results: list[DownloadItem] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_download_one, item, out_dir, timeout) for item in targets]
            for fut in concurrent.futures.as_completed(futures):
                results.append(fut.result())

        for item in results:
            print(f"[{item.status}] leg={item.legislatura} file={Path(item.out_path).name} bytes={item.bytes} sha={item.sha256}")

        failed = [item for item in results if item.status != "OK"]
        if failed:
            print(f"Resumen: {len(failed)} fallos de {len(results)} XMLs")
            return 2

        print(f"Resumen: {len(results)} xmls descargados en {out_dir}")
    report_payload: dict[str, Any] = {
        "base_url": base_url,
        "out_dir": str(out_dir),
        "check_only": bool(args.check_only),
        "total_detected_urls": total_urls,
        "legs": [
            {
                "legislatura": item.legislatura,
                "label": item.label,
                "urls": item.urls,
                "direct_count": item.direct_count,
                "fallback_count": item.fallback_count,
                "errors": item.errors,
            }
            for item in discovered
        ],
    }
    if not args.check_only:
        report_payload["downloaded"] = [
            {
                "legislatura": item.legislatura,
                "label": item.label,
                "url": item.url,
                "out_path": item.out_path,
                "status": item.status,
                "bytes": item.bytes,
                "sha256": item.sha256,
            }
            for item in results
        ]

    if args.report_json:
        Path(args.report_json).write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Reporte JSON: {args.report_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
