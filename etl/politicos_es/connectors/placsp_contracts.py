from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes, payload_looks_like_html
from ..parsers import parse_json_source
from ..raw import fallback_payload_from_sample, raw_output_path
from ..types import Extracted
from ..util import normalize_key_part, normalize_ws, now_utc_iso, sha256_bytes, stable_json
from .base import BaseConnector


PLACSP_BASE = "https://contrataciondelestado.es"

EXPEDIENTE_PATTERNS = (
    re.compile(r"(?:expediente|n(?:u|ú)m(?:ero)?\s+de\s+expediente)\s*[:\-]\s*([A-Za-z0-9./_-]{3,})", re.I),
    re.compile(r"\bEXP[-_/]?\d{4}[-_/]\d+\b", re.I),
)
ORGANO_PATTERNS = (
    re.compile(r"(?:organo(?:\s+de\s+contratacion)?|entidad adjudicadora)\s*[:\-]\s*([^.;\n]+)", re.I),
)
AMOUNT_PATTERNS = (
    re.compile(r"(?:importe|presupuesto)[^0-9]{0,25}([0-9][0-9., ]{0,40})", re.I),
    re.compile(r"([0-9][0-9., ]{0,40})\s*(?:EUR|€)", re.I),
)
DATE_PATTERNS = (
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{2}/\d{2}/\d{4})\b"),
)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _canonical_placsp_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    absolute = urljoin(PLACSP_BASE, raw_url.strip())
    parts = urlsplit(absolute)
    if not parts.netloc:
        return None
    scheme = "https" if parts.scheme.lower() in {"http", "https", ""} else parts.scheme.lower()
    return urlunsplit((scheme, parts.netloc.lower(), parts.path, parts.query, ""))


def _parse_datetime_iso(raw: str | None) -> str | None:
    if not raw:
        return None
    text = normalize_ws(raw)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _extract_text(entry: ET.Element, field_name: str) -> str:
    for child in list(entry):
        if _local_name(child.tag) != field_name:
            continue
        text = normalize_ws(" ".join(part.strip() for part in child.itertext() if part and part.strip()))
        if text:
            return text
    return ""


def _extract_links(entry: ET.Element) -> list[str]:
    urls: list[str] = []
    for node in entry.findall("{*}link"):
        href = normalize_ws(str(node.attrib.get("href") or ""))
        if not href:
            continue
        rel = normalize_ws(str(node.attrib.get("rel") or ""))
        if rel.lower() == "alternate":
            urls.insert(0, href)
        else:
            urls.append(href)
    return urls


def _extract_expediente(text_blob: str, *, source_url: str | None, entry_id: str | None) -> str | None:
    for pattern in EXPEDIENTE_PATTERNS:
        match = pattern.search(text_blob)
        if not match:
            continue
        value = normalize_ws(match.group(1) if match.lastindex else match.group(0))
        if value:
            return value
    if source_url:
        params = parse_qs(urlsplit(source_url).query)
        for key in ("numexp", "expediente", "idExpediente"):
            values = params.get(key, [])
            for value in values:
                text = normalize_ws(value)
                if text:
                    return text
    if entry_id:
        token = normalize_ws(entry_id.rsplit(":", 1)[-1])
        if token:
            return token
    return None


def _extract_organo(text_blob: str) -> str | None:
    for pattern in ORGANO_PATTERNS:
        match = pattern.search(text_blob)
        if not match:
            continue
        value = normalize_ws(match.group(1))
        if value:
            return value
    return None


def _extract_cpv_codes(text_blob: str) -> list[str]:
    cpvs = sorted({m.group(0) for m in re.finditer(r"\b\d{8}\b", text_blob)})
    return cpvs


def _parse_decimal_token(raw_value: str) -> float | None:
    token = normalize_ws(raw_value).replace(" ", "")
    if not token:
        return None
    token = token.replace("EUR", "").replace("eur", "").replace("€", "")
    token = token.strip()
    if not token:
        return None
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        parts = token.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "." in token:
        parts = token.split(".")
        if len(parts) == 2 and len(parts[1]) <= 2:
            pass
        else:
            token = token.replace(".", "")
    try:
        return float(token)
    except ValueError:
        return None


def _extract_amount_eur(text_blob: str) -> float | None:
    for pattern in AMOUNT_PATTERNS:
        for match in pattern.finditer(text_blob):
            value = _parse_decimal_token(match.group(1))
            if value is not None:
                return value
    return None


def _extract_publication_iso(*raw_values: str) -> str | None:
    for raw_value in raw_values:
        iso = _parse_datetime_iso(raw_value)
        if iso:
            return iso
    merged = " ".join(v for v in raw_values if v)
    for pattern in DATE_PATTERNS:
        match = pattern.search(merged)
        if not match:
            continue
        token = match.group(1)
        if "-" in token:
            return f"{token}T00:00:00+00:00"
        day, month, year = token.split("/")
        return f"{year}-{month}-{day}T00:00:00+00:00"
    return None


def build_source_record_id(record: dict[str, Any]) -> str | None:
    expediente = normalize_ws(str(record.get("expediente") or ""))
    source_url = normalize_ws(str(record.get("source_url") or ""))
    entry_id = normalize_ws(str(record.get("entry_id") or ""))
    title = normalize_ws(str(record.get("title") or ""))

    if expediente:
        expediente_key = normalize_key_part(expediente).replace(" ", "_")
        if source_url:
            return f"expediente:{expediente_key}:{sha256_bytes(source_url.encode('utf-8'))[:12]}"
        return f"expediente:{expediente_key}"
    if entry_id:
        return f"entry:{sha256_bytes(entry_id.encode('utf-8'))[:24]}"
    if source_url:
        return f"url:{sha256_bytes(source_url.encode('utf-8'))[:24]}"
    if title:
        return f"title:{sha256_bytes(title.encode('utf-8'))[:24]}"
    return None


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        for key in (
            "title",
            "source_url",
            "published_at_iso",
            "expediente",
            "organo_contratacion",
            "cpv",
            "amount_eur",
            "summary_text",
        ):
            if current.get(key) in (None, "") and record.get(key) not in (None, ""):
                current[key] = record.get(key)
        merged_cpvs = sorted({*(current.get("cpv_codes") or []), *(record.get("cpv_codes") or [])})
        current["cpv_codes"] = merged_cpvs
    return [by_id[key] for key in sorted(by_id)]


def parse_placsp_atom_entries(
    payload: bytes,
    *,
    feed_url: str,
    content_type: str | None,
) -> list[dict[str, Any]]:
    payload_sig = sha256_bytes(payload)
    if payload_looks_like_html(payload):
        raise RuntimeError(f"Respuesta HTML inesperada para PLACSP feed (payload_sig={payload_sig})")
    try:
        root = ET.fromstring(payload.decode("utf-8-sig", errors="replace"))
    except ET.ParseError as exc:
        raise RuntimeError(f"Feed XML invalido para PLACSP ({exc}; payload_sig={payload_sig})") from exc

    parsed: list[dict[str, Any]] = []
    for entry in root.findall(".//{*}entry"):
        entry_id = _extract_text(entry, "id")
        title = _extract_text(entry, "title")
        summary = _extract_text(entry, "summary")
        content = _extract_text(entry, "content")
        updated_raw = _extract_text(entry, "updated")
        published_raw = _extract_text(entry, "published")

        links = _extract_links(entry)
        source_url = _canonical_placsp_url(links[0]) if links else None
        if source_url is None:
            source_url = _canonical_placsp_url(entry_id)
        source_url_raw = links[0] if links else entry_id

        text_blob = normalize_ws(" ".join(part for part in (title, summary, content) if part))
        expediente = _extract_expediente(text_blob, source_url=source_url, entry_id=entry_id)
        organo = _extract_organo(text_blob)
        cpv_codes = _extract_cpv_codes(text_blob)
        amount_eur = _extract_amount_eur(text_blob)
        published_iso = _extract_publication_iso(updated_raw, published_raw, text_blob)

        record: dict[str, Any] = {
            "record_kind": "placsp_atom_entry",
            "source_feed": "placsp_atom",
            "feed_url": feed_url,
            "entry_id": entry_id or None,
            "title": title or "Licitacion PLACSP",
            "source_url_raw": source_url_raw or None,
            "source_url": source_url,
            "published_at_raw": updated_raw or published_raw or None,
            "published_at_iso": published_iso,
            "expediente": expediente,
            "organo_contratacion": organo,
            "cpv_codes": cpv_codes,
            "cpv": cpv_codes[0] if cpv_codes else None,
            "amount_eur": amount_eur,
            "currency": "EUR" if amount_eur is not None else None,
            "summary_text": summary or content or None,
        }
        source_record_id = build_source_record_id(record)
        if not source_record_id:
            continue
        record["source_record_id"] = source_record_id
        parsed.append(record)

    records = _dedupe_records(parsed)
    if records:
        return records
    root_tag = str(root.tag or "").strip() or "<unknown>"
    raise RuntimeError(f"No se encontraron entries parseables en PLACSP ({root_tag}; payload_sig={payload_sig})")


class _PlacspBaseConnector(BaseConnector):
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
                all_records: list[dict[str, Any]] = []
                for sample in sorted(from_file.glob("*.xml")) + sorted(from_file.glob("*.atom")):
                    payload = sample.read_bytes()
                    all_records.extend(
                        parse_placsp_atom_entries(
                            payload,
                            feed_url=f"file://{sample.resolve()}",
                            content_type="application/atom+xml",
                        )
                    )
                records = _dedupe_records(all_records)
                if not records:
                    raise RuntimeError(f"No se encontraron XML parseables en directorio PLACSP: {from_file}")
                serialized = json.dumps(
                    {"source": f"{self.source_id}_dir", "dir": str(from_file), "records": records},
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
                records = parse_placsp_atom_entries(
                    payload,
                    feed_url=resolved_url,
                    content_type="application/atom+xml",
                )
            serialized = json.dumps(
                {"source": f"{self.source_id}_file", "file": str(from_file), "records": records},
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
            records = parse_placsp_atom_entries(payload, feed_url=resolved_url, content_type=content_type)
            serialized = json.dumps(
                {"source": f"{self.source_id}_network", "feed_url": resolved_url, "records": records},
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
                records = parse_placsp_atom_entries(
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


class PlacspSindicacionConnector(_PlacspBaseConnector):
    source_id = "placsp_sindicacion"


class PlacspAutonomicoConnector(_PlacspBaseConnector):
    source_id = "placsp_autonomico"

