from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes, payload_looks_like_html
from ..parsers import parse_json_source
from ..raw import fallback_payload_from_sample, raw_output_path
from ..types import Extracted
from ..util import clean_text, normalize_ws, now_utc_iso, sha256_bytes, stable_json
from .base import BaseConnector


MONCLOA_BASE = "https://www.lamoncloa.gob.es"
MONCLOA_REFERENCIAS_INDEX_URL = (
    "https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/index.aspx"
)
MONCLOA_RSS_TIPO16_URL = "https://www.lamoncloa.gob.es/Paginas/rss.aspx?tipo=16"
MONCLOA_RSS_TIPO15_URL = "https://www.lamoncloa.gob.es/Paginas/rss.aspx?tipo=15"


def decode_moncloa_html(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "charset=" in ct:
        enc = ct.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            pass
    return payload.decode("utf-8", errors="replace")


def canonical_moncloa_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    absolute = urljoin(MONCLOA_BASE, raw_url.strip())
    parts = urlsplit(absolute)
    path = parts.path.lower()
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def extract_slug_from_url(raw_url: str | None) -> str:
    if not raw_url:
        return ""
    path = urlsplit(urljoin(MONCLOA_BASE, raw_url)).path
    slug = path.rsplit("/", 1)[-1]
    slug = slug.strip()
    if slug.lower().endswith(".aspx"):
        return slug.lower()
    return ""


def extract_date8_from_slug(slug: str) -> str | None:
    m = re.search(r"(\d{8})", slug or "")
    if not m:
        return None
    return m.group(1)


def parse_date8_iso(date8: str | None) -> str | None:
    if not date8:
        return None
    if not re.fullmatch(r"\d{8}", date8):
        return None
    return f"{date8[0:4]}-{date8[4:6]}-{date8[6:8]}"


def parse_moncloa_dot_date(raw: str | None) -> str | None:
    if not raw:
        return None
    text = normalize_ws(raw)
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", text)
    if not m:
        return None
    day = int(m.group(1))
    month = int(m.group(2))
    year = int(m.group(3))
    try:
        return datetime(year, month, day, tzinfo=timezone.utc).date().isoformat()
    except ValueError:
        return None


def parse_moncloa_slash_date(raw: str | None) -> str | None:
    if not raw:
        return None
    text = normalize_ws(raw)
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if not m:
        return None
    day = int(m.group(1))
    month = int(m.group(2))
    year = int(m.group(3))
    try:
        return datetime(year, month, day, tzinfo=timezone.utc).date().isoformat()
    except ValueError:
        return None


def parse_rfc_pubdate(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def extract_first_long_paragraph(html: str, *, min_len: int = 80) -> str | None:
    for m in re.finditer(
        r'<p[^>]*class="ms-rteElement-Parrafo_Normal"[^>]*>(.*?)</p>',
        html,
        flags=re.I | re.S,
    ):
        text = normalize_ws(clean_text(unescape(m.group(1))))
        if len(text) >= min_len:
            return text
    return None


def parse_referencias_list_html(html: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<li[^>]*class="advanced-new"[^>]*>(?P<body>.*?)</li>',
        html,
        flags=re.I | re.S,
    ):
        body = m.group("body")
        m_anchor = re.search(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>', body, flags=re.I | re.S)
        if not m_anchor:
            continue
        href = m_anchor.group("href").strip()
        title = normalize_ws(clean_text(unescape(m_anchor.group("title"))))
        if not href:
            continue
        m_date = re.search(r'<span[^>]*class="date"[^>]*>(.*?)</span>', body, flags=re.I | re.S)
        date_raw = normalize_ws(clean_text(unescape(m_date.group(1)))) if m_date else None

        source_url = canonical_moncloa_url(href)
        slug = extract_slug_from_url(source_url or href)
        if not slug:
            continue
        date8 = extract_date8_from_slug(slug)

        records.append(
            {
                "record_kind": "referencia",
                "origin_channel": "list_html",
                "stable_id_slug": slug,
                "stable_id_date8": date8,
                "title": title or "Referencia Consejo de Ministros",
                "source_url_raw": href,
                "source_url": source_url,
                "published_at_raw": date_raw,
                "published_at_iso": parse_moncloa_dot_date(date_raw),
                "event_date_raw": date_raw,
                "event_date_iso": parse_moncloa_dot_date(date_raw) or parse_date8_iso(date8),
                "summary_text": None,
                "summary_html_raw": None,
            }
        )
    return records


def parse_referencias_detail_html(html: str) -> dict[str, Any] | None:
    m_canonical = re.search(r"<link\s+rel='canonical'\s+href='([^']+)'", html, flags=re.I)
    source_url = canonical_moncloa_url(m_canonical.group(1)) if m_canonical else None
    if not source_url:
        m_og_url = re.search(r'<meta[^>]+property="og:url"[^>]+content="([^"]+)"', html, flags=re.I)
        source_url = canonical_moncloa_url(m_og_url.group(1)) if m_og_url else None

    slug = extract_slug_from_url(source_url)
    if not slug:
        return None
    date8 = extract_date8_from_slug(slug)

    m_title = re.search(r'<h1[^>]*id="h1Title"[^>]*>(.*?)</h1>', html, flags=re.I | re.S)
    title = normalize_ws(clean_text(unescape(m_title.group(1)))) if m_title else ""
    if not title:
        m_og_title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html, flags=re.I)
        if m_og_title:
            title = normalize_ws(clean_text(unescape(m_og_title.group(1))))
    if not title:
        m_page_title = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
        if m_page_title:
            page_title = normalize_ws(clean_text(unescape(m_page_title.group(1))))
            if "." in page_title:
                page_title = page_title.split(".", 1)[-1].strip()
            if "[" in page_title:
                page_title = page_title.split("[", 1)[0].strip()
            title = page_title

    m_desc = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html, flags=re.I)
    description = normalize_ws(clean_text(unescape(m_desc.group(1)))) if m_desc else ""
    published_raw = description
    published_iso = parse_moncloa_slash_date(description)
    summary_text = extract_first_long_paragraph(html)
    if not summary_text and description:
        summary_text = description

    return {
        "record_kind": "referencia",
        "origin_channel": "detail_html",
        "stable_id_slug": slug,
        "stable_id_date8": date8,
        "title": title or "Referencia Consejo de Ministros",
        "source_url_raw": source_url,
        "source_url": source_url,
        "published_at_raw": published_raw or None,
        "published_at_iso": published_iso or parse_date8_iso(date8),
        "event_date_raw": published_raw or None,
        "event_date_iso": published_iso or parse_date8_iso(date8),
        "summary_text": summary_text,
        "summary_html_raw": None,
    }


def merge_referencias_records(
    list_records: list[dict[str, Any]], detail_records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_slug: dict[str, dict[str, Any]] = {}
    for rec in list_records:
        slug = str(rec.get("stable_id_slug") or "").strip()
        if not slug:
            continue
        by_slug[slug] = dict(rec)

    for detail in detail_records:
        slug = str(detail.get("stable_id_slug") or "").strip()
        if not slug:
            continue
        if slug not in by_slug:
            by_slug[slug] = dict(detail)
            continue
        base = by_slug[slug]
        # Keep list discovery fields but prioritize detail for content-rich fields.
        for key in (
            "title",
            "source_url",
            "source_url_raw",
            "published_at_raw",
            "published_at_iso",
            "event_date_raw",
            "event_date_iso",
            "summary_text",
            "summary_html_raw",
        ):
            val = detail.get(key)
            if val not in (None, ""):
                base[key] = val
        base["origin_channel"] = "list+detail"

    return sorted(by_slug.values(), key=lambda r: str(r.get("stable_id_slug") or ""))


def parse_rss_items(payload: bytes, feed_type: str, feed_url: str) -> list[dict[str, Any]]:
    if payload_looks_like_html(payload):
        raise RuntimeError(f"Respuesta HTML inesperada en feed {feed_type}")

    try:
        root = ET.fromstring(payload.decode("utf-8-sig", errors="replace"))
    except ET.ParseError as exc:
        raise RuntimeError(f"RSS XML invalido ({feed_type}): {exc}") from exc

    records: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        title = normalize_ws("".join(item.findtext("title") or "").strip())
        link = normalize_ws("".join(item.findtext("link") or "").strip())
        guid = normalize_ws("".join(item.findtext("guid") or "").strip())
        description_html = (item.findtext("description") or "").strip()
        description_text = normalize_ws(clean_text(unescape(description_html)))
        pub_date_raw = normalize_ws((item.findtext("pubDate") or "").strip())
        categories = [normalize_ws((c.text or "").strip()) for c in item.findall("category")]
        categories = [c for c in categories if c]

        canonical_url = canonical_moncloa_url(guid or link)
        slug = extract_slug_from_url(canonical_url)
        if not slug:
            continue
        date8 = extract_date8_from_slug(slug)

        records.append(
            {
                "record_kind": "referencia_rss",
                "origin_channel": "rss",
                "source_feed": feed_type,
                "feed_url": feed_url,
                "stable_id_slug": slug,
                "stable_id_date8": date8,
                "title": title or "Referencia Consejo de Ministros",
                "source_url_raw": guid or link,
                "source_url": canonical_url,
                "published_at_raw": pub_date_raw or None,
                "published_at_iso": parse_rfc_pubdate(pub_date_raw),
                "event_date_raw": pub_date_raw or None,
                "event_date_iso": parse_date8_iso(date8),
                "summary_text": description_text or None,
                "summary_html_raw": description_html or None,
                "categories": categories,
            }
        )

    return records


def dedupe_rss_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for rec in records:
        feed = str(rec.get("source_feed") or "")
        slug = str(rec.get("stable_id_slug") or "")
        if not feed or not slug:
            continue
        key = f"{feed}:{slug}"
        deduped[key] = rec
    return sorted(deduped.values(), key=lambda r: f"{r.get('source_feed','')}:{r.get('stable_id_slug','')}")


def parse_referencias_from_dir(batch_dir: Path) -> list[dict[str, Any]]:
    list_dir = batch_dir / "list_pages"
    detail_dir = batch_dir / "detail_pages"
    list_records: list[dict[str, Any]] = []
    detail_records: list[dict[str, Any]] = []

    if list_dir.exists():
        for path in sorted(list_dir.glob("*.html")):
            html = path.read_text(encoding="utf-8", errors="replace")
            list_records.extend(parse_referencias_list_html(html))

    if detail_dir.exists():
        for path in sorted(detail_dir.glob("*.html")):
            html = path.read_text(encoding="utf-8", errors="replace")
            rec = parse_referencias_detail_html(html)
            if rec:
                detail_records.append(rec)

    merged = merge_referencias_records(list_records, detail_records)
    if not merged:
        raise RuntimeError(f"No se pudieron extraer referencias desde: {batch_dir}")
    return merged


def parse_rss_from_dir(batch_dir: Path) -> list[dict[str, Any]]:
    rss_dir = batch_dir / "rss_feeds"
    if not rss_dir.exists():
        raise RuntimeError(f"Directorio sin rss_feeds: {batch_dir}")

    out: list[dict[str, Any]] = []
    for path in sorted(rss_dir.glob("*.xml")):
        lower = path.name.lower()
        if "tipo16" in lower:
            feed_type = "tipo16"
            feed_url = MONCLOA_RSS_TIPO16_URL
        elif "tipo15" in lower:
            feed_type = "tipo15"
            feed_url = MONCLOA_RSS_TIPO15_URL
        else:
            continue
        payload = path.read_bytes()
        out.extend(parse_rss_items(payload, feed_type=feed_type, feed_url=feed_url))

    deduped = dedupe_rss_records(out)
    if not deduped:
        raise RuntimeError(f"No se pudieron extraer items RSS desde: {batch_dir}")
    return deduped


class MoncloaReferenciasConnector(BaseConnector):
    source_id = "moncloa_referencias"
    ingest_mode = "source_records_only"

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
    ) -> Extracted:
        if from_file is not None:
            if from_file.is_dir():
                records = parse_referencias_from_dir(from_file)
                payload_obj = {
                    "source": "moncloa_referencias_dir",
                    "dir": str(from_file),
                    "records": records,
                }
                payload = json.dumps(payload_obj, ensure_ascii=True, sort_keys=True).encode("utf-8")
                fetched_at = now_utc_iso()
                raw_path = raw_output_path(raw_dir, self.source_id, "json")
                raw_path.write_bytes(payload)
                return Extracted(
                    source_id=self.source_id,
                    source_url=f"file://{from_file.resolve()}",
                    resolved_url=f"file://{from_file.resolve()}",
                    fetched_at=fetched_at,
                    raw_path=raw_path,
                    content_sha256=sha256_bytes(payload),
                    content_type="application/json",
                    bytes=len(payload),
                    note="from-dir",
                    payload=payload,
                    records=records,
                )

            resolved_url = f"file://{from_file.resolve()}"
            payload = from_file.read_bytes()
            if from_file.suffix.lower() == ".json":
                records = parse_json_source(payload)
            else:
                html = decode_moncloa_html(payload, "text/html")
                list_records = parse_referencias_list_html(html)
                detail = parse_referencias_detail_html(html)
                detail_records = [detail] if detail else []
                records = merge_referencias_records(list_records, detail_records)
                if not records:
                    raise RuntimeError(f"Sample invalida para {self.source_id}: sin registros parseables")
            fetched_at = now_utc_iso()
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            serialized = json.dumps(
                {"source": "moncloa_referencias_file", "file": str(from_file), "records": records},
                ensure_ascii=True,
                sort_keys=True,
            ).encode("utf-8")
            raw_path.write_bytes(serialized)
            return Extracted(
                source_id=self.source_id,
                source_url=resolved_url,
                resolved_url=resolved_url,
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(serialized),
                content_type="application/json",
                bytes=len(serialized),
                note="from-file",
                payload=serialized,
                records=records,
            )

        resolved_url = self.resolve_url(url_override, timeout)
        try:
            payload, ct = http_get_bytes(resolved_url, timeout)
            list_html = decode_moncloa_html(payload, ct)
            list_records = parse_referencias_list_html(list_html)
            if not list_records:
                raise RuntimeError("No se encontraron items de referencias en listado")

            detail_records: list[dict[str, Any]] = []
            notes: list[str] = []
            for base in list_records:
                detail_url = str(base.get("source_url") or "")
                if not detail_url:
                    continue
                try:
                    detail_payload, detail_ct = http_get_bytes(detail_url, timeout)
                    detail_html = decode_moncloa_html(detail_payload, detail_ct)
                    detail = parse_referencias_detail_html(detail_html)
                    if detail:
                        detail_records.append(detail)
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"detail[{detail_url}]: {type(exc).__name__}: {exc}")

            records = merge_referencias_records(list_records, detail_records)
            payload_obj: dict[str, Any] = {
                "source": "moncloa_referencias_network",
                "list_url": resolved_url,
                "records": records,
            }
            if notes:
                payload_obj["warnings"] = notes
            serialized = json.dumps(payload_obj, ensure_ascii=True, sort_keys=True).encode("utf-8")
            fetched_at = now_utc_iso()
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(serialized)
            note = "network"
            if notes:
                note = f"network-with-partial-errors ({'; '.join(notes)})"
            return Extracted(
                source_id=self.source_id,
                source_url=resolved_url,
                resolved_url=resolved_url,
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(serialized),
                content_type="application/json",
                bytes=len(serialized),
                note=note,
                payload=serialized,
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
            sample_path = Path(SOURCE_CONFIG[self.source_id]["fallback_file"])
            if sample_path.suffix.lower() == ".json":
                records = parse_json_source(fetched["payload"])
            else:
                html = decode_moncloa_html(fetched["payload"], fetched.get("content_type"))
                records = parse_referencias_list_html(html)
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
        slug = str(record.get("stable_id_slug") or "").strip().lower()
        if not slug:
            source_url = str(record.get("source_url") or "")
            slug = extract_slug_from_url(source_url)
        if not slug:
            return None
        source_record_id = f"referencia:{slug}"
        return {
            "source_record_id": source_record_id,
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }


class MoncloaRssReferenciasConnector(BaseConnector):
    source_id = "moncloa_rss_referencias"
    ingest_mode = "source_records_only"

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
    ) -> Extracted:
        if from_file is not None:
            if from_file.is_dir():
                records = parse_rss_from_dir(from_file)
                payload_obj = {"source": "moncloa_rss_dir", "dir": str(from_file), "records": records}
                payload = json.dumps(payload_obj, ensure_ascii=True, sort_keys=True).encode("utf-8")
                fetched_at = now_utc_iso()
                raw_path = raw_output_path(raw_dir, self.source_id, "json")
                raw_path.write_bytes(payload)
                return Extracted(
                    source_id=self.source_id,
                    source_url=f"file://{from_file.resolve()}",
                    resolved_url=f"file://{from_file.resolve()}",
                    fetched_at=fetched_at,
                    raw_path=raw_path,
                    content_sha256=sha256_bytes(payload),
                    content_type="application/json",
                    bytes=len(payload),
                    note="from-dir",
                    payload=payload,
                    records=records,
                )

            resolved_url = f"file://{from_file.resolve()}"
            payload = from_file.read_bytes()
            if from_file.suffix.lower() == ".json":
                records = parse_json_source(payload)
            else:
                feed_type = "tipo15" if "tipo15" in from_file.name.lower() else "tipo16"
                records = parse_rss_items(payload, feed_type=feed_type, feed_url=resolved_url)
            serialized = json.dumps(
                {"source": "moncloa_rss_file", "file": str(from_file), "records": records},
                ensure_ascii=True,
                sort_keys=True,
            ).encode("utf-8")
            fetched_at = now_utc_iso()
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(serialized)
            return Extracted(
                source_id=self.source_id,
                source_url=resolved_url,
                resolved_url=resolved_url,
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(serialized),
                content_type="application/json",
                bytes=len(serialized),
                note="from-file",
                payload=serialized,
                records=records,
            )

        resolved_url = self.resolve_url(url_override, timeout)
        urls = [resolved_url, MONCLOA_RSS_TIPO15_URL]
        all_records: list[dict[str, Any]] = []
        notes: list[str] = []
        try:
            for feed_url in urls:
                feed_type = "tipo16" if "tipo=16" in feed_url.lower() else "tipo15"
                try:
                    payload, _ct = http_get_bytes(feed_url, timeout)
                    all_records.extend(parse_rss_items(payload, feed_type=feed_type, feed_url=feed_url))
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"{feed_type}: {type(exc).__name__}: {exc}")
            records = dedupe_rss_records(all_records)
            if not records:
                raise RuntimeError("No se pudo extraer ningun item RSS de Moncloa")
            payload_obj: dict[str, Any] = {
                "source": "moncloa_rss_network",
                "records": records,
                "feeds": urls,
            }
            if notes:
                payload_obj["warnings"] = notes
            serialized = json.dumps(payload_obj, ensure_ascii=True, sort_keys=True).encode("utf-8")
            fetched_at = now_utc_iso()
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(serialized)
            note = "network"
            if notes:
                note = f"network-with-partial-errors ({'; '.join(notes)})"
            return Extracted(
                source_id=self.source_id,
                source_url=resolved_url,
                resolved_url=resolved_url,
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(serialized),
                content_type="application/json",
                bytes=len(serialized),
                note=note,
                payload=serialized,
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
            sample_path = Path(SOURCE_CONFIG[self.source_id]["fallback_file"])
            if sample_path.suffix.lower() == ".json":
                records = parse_json_source(fetched["payload"])
            else:
                records = parse_rss_items(
                    fetched["payload"],
                    feed_type="tipo16",
                    feed_url=fetched["source_url"],
                )
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
        slug = str(record.get("stable_id_slug") or "").strip().lower()
        feed = str(record.get("source_feed") or "").strip().lower()
        if not slug:
            source_url = str(record.get("source_url") or "")
            slug = extract_slug_from_url(source_url)
        if not slug:
            return None
        if not feed:
            feed = "rss"
        source_record_id = f"{feed}:{slug}"
        return {
            "source_record_id": source_record_id,
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
