from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from publicdata_core.connectors import BaseConnector
from publicdata_core.http import http_get_bytes, payload_looks_like_html
from publicdata_core.raw import raw_output_path
from publicdata_core.raw import fallback_payload_from_sample as _fallback_payload_from_sample
from publicdata_core.sources import SourceDefinition, source_config_mapping
from publicdata_core.types import Extracted
from publicdata_core.util import normalize_ws, now_utc_iso, sha256_bytes, stable_json


BOE_BASE = "https://www.boe.es"
BOE_RSS_URL = "https://www.boe.es/rss/boe.php"
BOE_OPEN_DATA_SUMMARY_BASE = "https://www.boe.es/datosabiertos/api/boe/sumario"
BOE_REF_RE = re.compile(r"\b(BOE-[A-Z]-\d{4}-\d+)\b", flags=re.I)

SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        source_id="boe_api_legal",
        name="BOE API - Marco legal (RSS diario)",
        scope="legal",
        default_url=BOE_RSS_URL,
        format="xml",
        fallback_file="",
        min_records_loaded_strict=5,
    ),
)

SOURCE_CONFIG = source_config_mapping(SOURCE_DEFINITIONS)


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


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _url_text(value: Any) -> str | None:
    if isinstance(value, dict):
        text = normalize_ws(str(value.get("texto") or ""))
    else:
        text = normalize_ws(str(value or ""))
    return text or None


def _date_yyyymmdd_to_iso(value: Any) -> str | None:
    text = normalize_ws(str(value or ""))
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return None


def _xml_local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _xml_children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(node) if _xml_local_name(str(child.tag)) == name]


def _xml_first_child(node: ET.Element, name: str) -> ET.Element | None:
    children = _xml_children(node, name)
    return children[0] if children else None


def _xml_child_text(node: ET.Element, name: str) -> str | None:
    child = _xml_first_child(node, name)
    if child is None:
        return None
    return normalize_ws("".join(child.itertext()))


def _xml_url_text(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    nested_text = _xml_child_text(node, "texto")
    if nested_text:
        return nested_text
    return normalize_ws("".join(node.itertext())) or None


def _record_from_boe_summary_item(
    *,
    item: dict[str, Any],
    feed_url: str,
    publication_date: str | None,
    daily_summary_id: str | None,
    daily_summary_url_pdf: str | None,
    section_code: str | None,
    section_name: str | None,
    department_code: str | None,
    department_name: str | None,
    epigraph_name: str | None,
) -> dict[str, Any] | None:
    boe_ref = normalize_ws(str(item.get("identificador") or ""))
    title = normalize_ws(str(item.get("titulo") or ""))
    if not boe_ref and not title:
        return None

    url_pdf = _url_text(item.get("url_pdf"))
    source_url = (
        canonical_boe_url(str(item.get("url_html") or ""))
        or canonical_boe_url(str(item.get("url_xml") or ""))
        or canonical_boe_url(url_pdf)
    )
    if not source_url and not boe_ref:
        return None

    categories = [value for value in (section_name, department_name, epigraph_name) if value]
    record: dict[str, Any] = {
        "record_kind": "boe_summary_item",
        "source_feed": "boe_sumario_api",
        "feed_url": feed_url,
        "title": title or boe_ref or "Documento BOE",
        "source_url_raw": source_url,
        "source_url": source_url,
        "boe_ref": boe_ref or extract_boe_ref(source_url, title),
        "published_at_iso": publication_date,
        "publication_date": publication_date,
        "daily_summary_id": daily_summary_id,
        "daily_summary_url_pdf": daily_summary_url_pdf,
        "section_code": section_code,
        "section_name": section_name,
        "department_code": department_code,
        "department_name": department_name,
        "epigraph_name": epigraph_name,
        "control": normalize_ws(str(item.get("control") or "")) or None,
        "url_html": canonical_boe_url(str(item.get("url_html") or "")),
        "url_xml": canonical_boe_url(str(item.get("url_xml") or "")),
        "url_pdf": canonical_boe_url(url_pdf),
        "categories": categories,
    }
    if isinstance(item.get("url_pdf"), dict):
        url_pdf_obj = item["url_pdf"]
        record["page_start"] = normalize_ws(str(url_pdf_obj.get("pagina_inicial") or "")) or None
        record["page_end"] = normalize_ws(str(url_pdf_obj.get("pagina_final") or "")) or None
    source_record_id = build_source_record_id(record)
    if not source_record_id:
        return None
    record["source_record_id"] = source_record_id
    return record


def parse_boe_summary_json(payload: bytes, *, feed_url: str) -> list[dict[str, Any]]:
    payload_sig = sha256_bytes(payload)
    try:
        parsed = json.loads(payload.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON invalido para BOE sumario ({exc}; payload_sig={payload_sig})") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"JSON BOE sumario no es objeto (payload_sig={payload_sig})")

    status = parsed.get("status")
    if isinstance(status, dict) and str(status.get("code") or "") != "200":
        raise RuntimeError(
            "Respuesta BOE sumario no OK "
            f"(code={status.get('code')!r}; text={status.get('text')!r}; payload_sig={payload_sig})"
        )

    sumario = ((parsed.get("data") or {}).get("sumario") if isinstance(parsed.get("data"), dict) else None)
    if not isinstance(sumario, dict):
        raise RuntimeError(f"JSON BOE sumario sin data.sumario (payload_sig={payload_sig})")

    metadata = sumario.get("metadatos") if isinstance(sumario.get("metadatos"), dict) else {}
    publication_date = _date_yyyymmdd_to_iso((metadata or {}).get("fecha_publicacion"))
    records: list[dict[str, Any]] = []
    for diario in _as_list(sumario.get("diario")):
        if not isinstance(diario, dict):
            continue
        summary = diario.get("sumario_diario") if isinstance(diario.get("sumario_diario"), dict) else {}
        daily_summary_id = normalize_ws(str((summary or {}).get("identificador") or "")) or None
        daily_summary_url_pdf = canonical_boe_url(_url_text((summary or {}).get("url_pdf")))
        for section in _as_list(diario.get("seccion")):
            if not isinstance(section, dict):
                continue
            section_code = normalize_ws(str(section.get("codigo") or "")) or None
            section_name = normalize_ws(str(section.get("nombre") or "")) or None
            for department in _as_list(section.get("departamento")):
                if not isinstance(department, dict):
                    continue
                department_code = normalize_ws(str(department.get("codigo") or "")) or None
                department_name = normalize_ws(str(department.get("nombre") or "")) or None
                for epigraph in _as_list(department.get("epigrafe")):
                    if not isinstance(epigraph, dict):
                        continue
                    epigraph_name = normalize_ws(str(epigraph.get("nombre") or "")) or None
                    for item in _as_list(epigraph.get("item")):
                        if not isinstance(item, dict):
                            continue
                        record = _record_from_boe_summary_item(
                            item=item,
                            feed_url=feed_url,
                            publication_date=publication_date,
                            daily_summary_id=daily_summary_id,
                            daily_summary_url_pdf=daily_summary_url_pdf,
                            section_code=section_code,
                            section_name=section_name,
                            department_code=department_code,
                            department_name=department_name,
                            epigraph_name=epigraph_name,
                        )
                        if record is not None:
                            records.append(record)

    records = dedupe_boe_records(records)
    if records:
        return records
    raise RuntimeError(f"No se encontraron items parseables en BOE sumario JSON (payload_sig={payload_sig})")


def parse_boe_summary_xml(payload: bytes, *, feed_url: str, content_type: str | None) -> list[dict[str, Any]]:
    payload_sig = sha256_bytes(payload)
    xml_text = decode_boe_payload(payload, content_type)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RuntimeError(f"XML invalido para BOE sumario ({exc}; payload_sig={payload_sig})") from exc

    if _xml_local_name(str(root.tag)) != "response":
        raise RuntimeError(f"XML BOE sumario no es response (payload_sig={payload_sig})")
    status = _xml_first_child(root, "status")
    status_code = _xml_child_text(status, "code") if status is not None else None
    if status_code and status_code != "200":
        status_text = _xml_child_text(status, "text") if status is not None else None
        raise RuntimeError(f"Respuesta BOE sumario no OK (code={status_code}; text={status_text}; payload_sig={payload_sig})")

    data = _xml_first_child(root, "data")
    sumario = _xml_first_child(data, "sumario") if data is not None else None
    if sumario is None:
        raise RuntimeError(f"XML BOE sumario sin data/sumario (payload_sig={payload_sig})")
    metadata = _xml_first_child(sumario, "metadatos")
    publication_date = _date_yyyymmdd_to_iso(_xml_child_text(metadata, "fecha_publicacion") if metadata is not None else None)

    records: list[dict[str, Any]] = []
    for diario in _xml_children(sumario, "diario"):
        summary = _xml_first_child(diario, "sumario_diario")
        daily_summary_id = _xml_child_text(summary, "identificador") if summary is not None else None
        daily_summary_url_pdf = canonical_boe_url(_xml_url_text(_xml_first_child(summary, "url_pdf") if summary is not None else None))
        for section in _xml_children(diario, "seccion"):
            section_code = _xml_child_text(section, "codigo")
            section_name = _xml_child_text(section, "nombre")
            for department in _xml_children(section, "departamento"):
                department_code = _xml_child_text(department, "codigo")
                department_name = _xml_child_text(department, "nombre")
                for epigraph in _xml_children(department, "epigrafe"):
                    epigraph_name = _xml_child_text(epigraph, "nombre")
                    for item_node in _xml_children(epigraph, "item"):
                        item = {
                            "identificador": _xml_child_text(item_node, "identificador"),
                            "control": _xml_child_text(item_node, "control"),
                            "titulo": _xml_child_text(item_node, "titulo"),
                            "url_html": _xml_child_text(item_node, "url_html"),
                            "url_xml": _xml_child_text(item_node, "url_xml"),
                            "url_pdf": {
                                "texto": _xml_url_text(_xml_first_child(item_node, "url_pdf")),
                                "pagina_inicial": _xml_child_text(_xml_first_child(item_node, "url_pdf"), "pagina_inicial")
                                if _xml_first_child(item_node, "url_pdf") is not None
                                else None,
                                "pagina_final": _xml_child_text(_xml_first_child(item_node, "url_pdf"), "pagina_final")
                                if _xml_first_child(item_node, "url_pdf") is not None
                                else None,
                            },
                        }
                        record = _record_from_boe_summary_item(
                            item=item,
                            feed_url=feed_url,
                            publication_date=publication_date,
                            daily_summary_id=daily_summary_id,
                            daily_summary_url_pdf=daily_summary_url_pdf,
                            section_code=section_code,
                            section_name=section_name,
                            department_code=department_code,
                            department_name=department_name,
                            epigraph_name=epigraph_name,
                        )
                        if record is not None:
                            records.append(record)

    records = dedupe_boe_records(records)
    if records:
        return records
    raise RuntimeError(f"No se encontraron items parseables en BOE sumario XML (payload_sig={payload_sig})")


def parse_boe_payload(
    payload: bytes,
    *,
    feed_url: str,
    content_type: str | None,
) -> list[dict[str, Any]]:
    sample = payload[:4096].lstrip()
    lowered_url = feed_url.lower()
    lowered_ct = (content_type or "").lower()
    if "datosabiertos/api/boe/sumario" in lowered_url or sample.startswith(b"{") or "json" in lowered_ct:
        return parse_boe_summary_json(payload, feed_url=feed_url)
    if sample.startswith(b"<response") or b"<sumario" in sample[:2048]:
        return parse_boe_summary_xml(payload, feed_url=feed_url, content_type=content_type)
    return parse_boe_rss_items(payload, feed_url=feed_url, content_type=content_type)


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

            resolved_url = url_override or f"file://{from_file.resolve()}"
            payload = from_file.read_bytes()
            if from_file.suffix.lower() == ".json":
                content_type = "application/json"
            else:
                content_type = "text/xml"
            records = parse_boe_payload(payload, feed_url=resolved_url, content_type=content_type)
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
            payload, content_type = http_get_bytes(
                resolved_url,
                timeout,
                headers={
                    "Accept": "application/json, application/rss+xml;q=0.9, application/xml;q=0.8, text/xml;q=0.8"
                },
            )
            records = parse_boe_payload(payload, feed_url=resolved_url, content_type=content_type)
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
            fetched = _fallback_payload_from_sample(
                SOURCE_CONFIG,
                self.source_id,
                raw_dir,
                note=f"network-error-fallback: {type(exc).__name__}: {exc}",
            )
            sample_path = Path(SOURCE_CONFIG[self.source_id]["fallback_file"])
            if sample_path.suffix.lower() == ".json":
                content_type = "application/json"
            else:
                content_type = fetched.get("content_type") or "text/xml"
            records = parse_boe_payload(
                fetched["payload"],
                feed_url=fetched["source_url"],
                content_type=content_type,
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
