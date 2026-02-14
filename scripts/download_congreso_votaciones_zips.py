#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urljoin

DEFAULT_BASE_URL = "https://www.congreso.es/es/opendata/votaciones"
DEFAULT_OUT_DIR = Path("etl/data/raw/congreso_votaciones_zips")
UA = "Mozilla/5.0 (compatible; etl-script/1.0)"

SELECT_RE = re.compile(
    r'<select[^>]*id="_votaciones_legislatura"[^>]*>(?P<body>.*?)</select>',
    re.I | re.S,
)
OPTION_RE = re.compile(r'<option[^>]*value="(?P<value>\d+)"[^>]*>(?P<label>.*?)</option>', re.I | re.S)
ZIP_RE = re.compile(r'href="([^"]+/VOT_[^"\s]+\.zip)"', re.I)


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
    out: list[str] = []
    n = num
    for v, s in vals:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


def _safe_read(url: str, timeout: int, accept: str = "text/html") -> str:
    req = Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return data.decode("utf-8", errors="ignore")


def _read_binary(url: str, timeout: int) -> tuple[bytes, str | None]:
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/octet-stream"})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        ct = resp.headers.get("Content-Type")
    return data, ct


def _extract_legislatures(html: str) -> list[tuple[int, str]]:
    mm = SELECT_RE.search(html)
    if not mm:
        return []
    body = mm.group("body")
    out: list[tuple[int, str]] = []
    seen: set[int] = set()
    for m in OPTION_RE.finditer(body):
        v = int(m.group("value"))
        if v in seen:
            continue
        seen.add(v)
        label = re.sub(r"\s+", " ", m.group("label")).strip()
        out.append((v, label))
    return out


def _extract_zip_links(html: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for href in ZIP_RE.findall(html):
        if href in seen:
            continue
        seen.add(href)
        links.append(href)
    return links


def _leg_url(base_url: str, leg: int) -> str:
    return (
        f"{base_url}?p_p_id=votaciones&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view"
        f"&targetLegislatura={_romanize(leg)}"
    )


@dataclass
class ZipItem:
    leg: int
    label: str
    url: str
    filename: str
    status: str
    bytes: int = 0
    sha256: str = ""


def _download_one(item: tuple[int, str, str], out_dir: Path, timeout: int) -> ZipItem:
    leg, label, href = item
    url = urljoin("https://www.congreso.es", href)
    filename = Path(url).name
    out_path = out_dir / filename
    try:
        payload, ct = _read_binary(url, timeout=timeout)
        if not payload:
            return ZipItem(leg=leg, label=label, url=url, filename=filename, status="EMPTY")
        out_path.write_bytes(payload)
        h = hashlib.sha256(payload).hexdigest()
        return ZipItem(leg=leg, label=label, url=url, filename=str(out_path), status="OK", bytes=len(payload), sha256=h)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        return ZipItem(leg=leg, label=label, url=url, filename=filename, status=f"ERROR: {type(exc).__name__}: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Descarga ZIPs de la página de votaciones del Congreso")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--check-only", action="store_true", help="Solo verificar enlaces, sin descargar")
    parser.add_argument("--report-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    if not args.check_only:
        out_dir.mkdir(parents=True, exist_ok=True)

    base_html = _safe_read(args.base_url, timeout=args.timeout)
    legs = _extract_legislatures(base_html)
    if not legs:
        print("No fue posible detectar legislaturas en la página principal.")
        return 1

    discovered: dict[int, list[str]] = {}
    for leg, label in legs:
        page_url = _leg_url(args.base_url, leg)
        try:
            page_html = _safe_read(page_url, timeout=args.timeout)
        except Exception:
            discovered[leg] = []
            continue
        discovered[leg] = _extract_zip_links(page_html)

    rows: list[dict[str, Any]] = []
    for leg, label in legs:
        zips = discovered.get(leg, [])
        if not zips:
            rows.append({
                "legislatura": leg,
                "label": label,
                "zip_count": 0,
                "status": "NO_ZIPS",
            })
            continue
        for href in zips:
            rows.append({
                "legislatura": leg,
                "label": label,
                "url": urljoin("https://www.congreso.es", href),
                "filename": Path(href).name,
                "status": "FOUND",
            })

    print(f"Legislaturas detectadas: {len(legs)}")
    for r in rows:
        status = r["status"]
        if status != "FOUND":
            print(f"Leg {r['legislatura']:>2} [{r['label']}] -> {status}")
        else:
            print(f"Leg {r['legislatura']:>2} [{r['label']}] -> {r['filename']}")

    download_targets = [(int(r["legislatura"]), str(r["label"]), str(r["url"])) for r in rows if r["status"] == "FOUND"]

    if not args.check_only and download_targets:
        results: list[ZipItem] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as ex:
            for result in ex.map(lambda it: _download_one(it, out_dir, args.timeout), download_targets):
                results.append(result)

        for item in results:
            print(f"[{item.status}] leg={item.leg} file={item.filename} bytes={item.bytes} sha={item.sha256}")

        failed = [item for item in results if item.status != "OK"]
        if failed:
            print(f"Resumen: {len(failed)} failed de {len(results)}")
            return 2

        print(f"Resumen: {len(results)} zip(s) descargados en {out_dir}")

        payload = {
            "base_url": args.base_url,
            "out_dir": str(out_dir),
            "rows": [
                {
                    "legislatura": item.leg,
                    "label": item.label,
                    "url": item.url,
                    "filename": item.filename,
                    "status": item.status,
                    "bytes": item.bytes,
                    "sha256": item.sha256,
                }
                for item in results
            ],
        }
    else:
        payload = {
            "base_url": args.base_url,
            "out_dir": str(out_dir),
            "rows": rows,
        }

    if args.report_json:
        Path(args.report_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Reporte JSON: {args.report_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
