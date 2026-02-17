from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes, payload_looks_like_html
from ..parsers import parse_json_source
from ..raw import fallback_payload_from_sample, raw_output_path
from ..types import Extracted
from ..util import normalize_ws, now_utc_iso, sha256_bytes, stable_json
from .base import BaseConnector


BOE_BASE = "https://www.boe.es"
BOE_RSS_URL = "https://www.boe.es/rss/boe.php"
BOE_REF_RE = re.compile(r"\b(BOE-[A-Z]-\d{4}-\d+)\b", flags=re.I)


def decode_boe_payload(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    encodings: list[str] = []
    if "charset=" in ct:
        encoding = ct.split("charset=", 1)[1].split(";", 1)[0].strip().strip("\"'")
        if encoding:
            encodings.append(encoding)
    encodings.extend(["utf-8-sig", "utf-8", "iso-8859-1", "cp1252"])
    tried: set[str] = set()
    for encoding in encodings:
        if encoding in tried:
            continue
        tried.add(encoding)
        try:
            return payload.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="replace")


def canonical_boe_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    absolute = urljoin(BOE_BASE, raw_url.strip())
    parts = urlsplit(absolute)
    if not parts.scheme or not parts.netloc:
        return None
    scheme = "https" if parts.scheme.lower() in {"http", "https"} else parts.scheme.lower()
    netloc = parts.netloc.lower()
    if netloc == "boe.es":
        netloc = "www.boe.es"
    return urlunsplit((scheme, netloc, parts.path, parts.query, ""))


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


def extract_boe_ref(*values: str | None) -> str | None:
    for value in values:
        if not value:
            continue
        match = BOE_REF_RE.search(value)
        if not match:
            continue
        return str(match.group(1)).upper()
    return None


def build_source_record_id(record: dict[str, Any]) -> str | None:
    boe_ref = str(record.get("boe_ref") or "").strip().upper()
    if boe_ref:
        return f"boe_ref:{boe_ref}"

    source_url = str(record.get("source_url") or "").strip()
    if source_url:
        return f"url_sha256:{sha256_bytes(source_url.encode('utf-8'))[:24]}"

    title = normalize_ws(str(record.get("title") or ""))
    if title:
        return f"title_sha256:{sha256_bytes(title.encode('utf-8'))[:24]}"
    return None


def dedupe_boe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        source_record_id = str(record.get("source_record_id") or "").strip()
        if not source_record_id:
            source_record_id = build_source_record_id(record) or ""
            if source_record_id:
                record = {**record, "source_record_id": source_record_id}
        if not source_record_id:
            continue

        current = by_id.get(source_record_id)
        if current is None:
            by_id[source_record_id] = dict(record)
            continue

        # Keep first-seen record as base and only fill missing fields deterministically.
        for key in ("source_url", "published_at_raw", "published_at_iso", "description"):
            if current.get(key) in (None, "") and record.get(key) not in (None, ""):
                current[key] = record.get(key)
        merged_categories = sorted({*(current.get("categories") or []), *(record.get("categories") or [])})
        if merged_categories:
            current["categories"] = merged_categories

    return [by_id[key] for key in sorted(by_id)]


def parse_boe_rss_items(
    payload: bytes,
    *,
    feed_url: str,
    content_type: str | None,
) -> list[dict[str, Any]]:
    payload_sig = sha256_bytes(payload)
    if payload_looks_like_html(payload):
        raise RuntimeError(f"Respuesta HTML inesperada para BOE RSS (payload_sig={payload_sig})")

    xml_text = decode_boe_payload(payload, content_type)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RuntimeError(f"RSS XML invalido para BOE ({exc}; payload_sig={payload_sig})") from exc

    parsed: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        title = normalize_ws((item.findtext("title") or "").strip())
        link = normalize_ws((item.findtext("link") or "").strip())
        guid = normalize_ws((item.findtext("guid") or "").strip())
        description = normalize_ws((item.findtext("description") or "").strip())
        pub_date_raw = normalize_ws((item.findtext("pubDate") or "").strip())
        categories = [normalize_ws((cat.text or "").strip()) for cat in item.findall("category")]
        categories = [cat for cat in categories if cat]

        source_url = canonical_boe_url(link) or canonical_boe_url(guid)
        boe_ref = extract_boe_ref(link, guid, title, description)
        if not source_url and not boe_ref:
            continue

        record: dict[str, Any] = {
            "record_kind": "boe_rss_item",
            "source_feed": "boe_diario_rss",
            "feed_url": feed_url,
            "title": title or boe_ref or "Documento BOE",
            "source_url_raw": link or guid,
            "source_url": source_url,
            "boe_ref": boe_ref,
            "published_at_raw": pub_date_raw or None,
            "published_at_iso": parse_rfc_pubdate(pub_date_raw),
            "description": description or None,
            "categories": categories,
        }
        source_record_id = build_source_record_id(record)
        if not source_record_id:
            continue
        record["source_record_id"] = source_record_id
        parsed.append(record)

    records = dedupe_boe_records(parsed)
    if records:
        return records

    root_tag = str(root.tag or "").strip() or "<unknown>"
    raise RuntimeError(f"No se encontraron items parseables en BOE RSS ({root_tag}; payload_sig={payload_sig})")


class BoeApiLegalConnector(BaseConnector):
    source_id = "boe_api_legal"
    ingest_mode = "source_records_only"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or SOURCE_CONFIG[self.source_id].get("default_url", BOE_RSS_URL)

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
                all_records: list[dict[str, Any]] = []
                for sample in sorted(from_file.glob("*.xml")):
                    payload = sample.read_bytes()
                    all_records.extend(
                        parse_boe_rss_items(
                            payload,
                            feed_url=f"file://{sample.resolve()}",
                            content_type="text/xml",
                        )
                    )
                records = dedupe_boe_records(all_records)
                if not records:
                    raise RuntimeError(f"No se encontraron XML parseables en directorio BOE: {from_file}")
                serialized = json.dumps(
                    {"source": "boe_api_legal_dir", "dir": str(from_file), "records": records},
                    ensure_ascii=True,
                    sort_keys=True,
                ).encode("utf-8")
                fetched_at = now_utc_iso()
                raw_path = raw_output_path(raw_dir, self.source_id, "json")
                raw_path.write_bytes(serialized)
                return Extracted(
                    source_id=self.source_id,
                    source_url=f"file://{from_file.resolve()}",
                    resolved_url=f"file://{from_file.resolve()}",
                    fetched_at=fetched_at,
                    raw_path=raw_path,
                    content_sha256=sha256_bytes(serialized),
                    content_type="application/json",
                    bytes=len(serialized),
                    note="from-dir",
                    payload=serialized,
                    records=records,
                )

            resolved_url = f"file://{from_file.resolve()}"
            payload = from_file.read_bytes()
            if from_file.suffix.lower() == ".json":
                records = parse_json_source(payload)
            else:
                records = parse_boe_rss_items(payload, feed_url=resolved_url, content_type="text/xml")
            serialized = json.dumps(
                {"source": "boe_api_legal_file", "file": str(from_file), "records": records},
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
        try:
            payload, content_type = http_get_bytes(resolved_url, timeout)
            records = parse_boe_rss_items(payload, feed_url=resolved_url, content_type=content_type)
            serialized = json.dumps(
                {"source": "boe_api_legal_network", "feed_url": resolved_url, "records": records},
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
                note="network",
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
                records = parse_boe_rss_items(
                    fetched["payload"],
                    feed_url=fetched["source_url"],
                    content_type=fetched.get("content_type"),
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
        source_record_id = str(record.get("source_record_id") or "").strip()
        if not source_record_id:
            source_record_id = build_source_record_id(record) or ""
        if not source_record_id:
            return None
        return {
            "source_record_id": source_record_id,
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
