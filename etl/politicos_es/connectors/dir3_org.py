from __future__ import annotations

import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes, payload_looks_like_html
from ..parsers import parse_json_source
from ..raw import fallback_payload_from_sample, raw_output_path
from ..types import Extracted
from ..util import normalize_key_part, normalize_ws, now_utc_iso, parse_date_flexible, pick_value, sha256_bytes, stable_json
from .base import BaseConnector


DIR3_CATALOG_URL = "https://datos.gob.es/es/catalogo/e05251701-directorio-comun-de-unidades-organicas-y-oficinas-dir3"
DIR3_DATASET_API_URL = (
    "https://datos.gob.es/apidata/catalog/dataset/"
    "e05251701-directorio-comun-de-unidades-organicas-y-oficinas-dir3"
)
DIR3_AGE_XLSX_URL = (
    "https://administracionelectronica.gob.es/ctt/resources/Soluciones/238/Descargas/"
    "Listado%20Unidades%20AGE.xlsx?idIniciativa=238&idElemento=2741"
)


def _xlsx_col_to_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in str(cell_ref or "") if ch.isalpha()).upper()
    if not letters:
        return -1
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return normalize_ws("".join(node.text or "" for node in cell.findall(".//{*}t")))

    node = cell.find("{*}v")
    raw_value = normalize_ws(node.text or "") if node is not None else ""
    if not raw_value:
        return ""
    if cell_type == "s":
        try:
            return normalize_ws(shared[int(raw_value)])
        except (ValueError, IndexError):
            return raw_value
    return raw_value


def parse_dir3_xlsx(payload: bytes) -> list[dict[str, Any]]:
    payload_sig = sha256_bytes(payload)
    if payload_looks_like_html(payload):
        raise RuntimeError(f"Respuesta HTML inesperada para DIR3 XLSX (payload_sig={payload_sig})")

    try:
        zf = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"XLSX invalido para DIR3 (payload_sig={payload_sig})") from exc

    with zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall(".//{*}si"):
                shared.append("".join(node.text or "" for node in si.findall(".//{*}t")))

        sheets = sorted(name for name in zf.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))
        if not sheets:
            return []

        root = ET.fromstring(zf.read(sheets[0]))
        raw_rows: list[list[str]] = []
        for row in root.findall(".//{*}sheetData/{*}row"):
            row_values: dict[int, str] = {}
            max_idx = -1
            for cell in row.findall("{*}c"):
                idx = _xlsx_col_to_index(cell.attrib.get("r", ""))
                if idx < 0:
                    idx = max_idx + 1
                row_values[idx] = _cell_text(cell, shared)
                max_idx = max(max_idx, idx)
            if max_idx >= 0:
                raw_rows.append([row_values.get(i, "") for i in range(max_idx + 1)])

    if not raw_rows:
        return []

    header_idx = -1
    for idx, values in enumerate(raw_rows[:30]):
        normalized_headers = {normalize_key_part(value) for value in values if normalize_key_part(value)}
        if any("codigo" in h and ("unidad" in h or "dir3" in h) for h in normalized_headers) and any(
            "denominacion" in h or "nombre" in h for h in normalized_headers
        ):
            header_idx = idx
            break
    if header_idx < 0:
        raise RuntimeError(f"No se encontro cabecera DIR3 reconocible (payload_sig={payload_sig})")

    headers = [normalize_ws(value) for value in raw_rows[header_idx]]
    rows: list[dict[str, Any]] = []
    for values in raw_rows[header_idx + 1 :]:
        record: dict[str, Any] = {}
        non_empty = False
        for idx, key in enumerate(headers):
            key = normalize_ws(key)
            if not key:
                continue
            value = normalize_ws(values[idx] if idx < len(values) else "")
            record[key] = value
            non_empty = non_empty or bool(value)
        if non_empty:
            rows.append(record)
    return rows


def _clean_code(raw: str | None) -> str:
    text = normalize_ws(str(raw or "")).upper()
    if not text:
        return ""
    text = text.split("-", 1)[0].strip() if re.search(r"\s*-\s*v\d+", text, flags=re.I) else text
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text


def _clean_version(raw: str | None) -> str | None:
    text = normalize_ws(str(raw or ""))
    if not text:
        return None
    match = re.search(r"\bv\s*([0-9]+)\b", text, flags=re.I)
    if match:
        return match.group(1)
    if text.isdigit():
        return text
    return None


def _parse_int(raw: str | None) -> int | None:
    text = normalize_ws(str(raw or ""))
    if not text:
        return None
    match = re.search(r"-?\d+", text)
    if not match:
        return None
    return int(match.group(0))


def _pick_date(record: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
    raw = pick_value(record, candidates)
    parsed = parse_date_flexible(raw)
    return parsed or (normalize_ws(raw) if raw else None)


def normalize_dir3_record(row: dict[str, Any], *, feed_url: str) -> dict[str, Any] | None:
    code_raw = pick_value(
        row,
        (
            "codigo unidad organica",
            "código unidad orgánica",
            "codigo unidad",
            "código unidad",
            "codigo dir3",
            "código dir3",
            "cod unidad organica",
            "codigo",
        ),
    )
    org_unit_code = _clean_code(code_raw)
    name = pick_value(
        row,
        (
            "denominacion unidad organica",
            "denominación unidad orgánica",
            "denominacion",
            "denominación",
            "nombre unidad organica",
            "unidad organica",
            "nombre",
        ),
    )
    if not org_unit_code or not name:
        return None

    parent_code = _clean_code(
        pick_value(
            row,
            (
                "codigo unidad organica superior",
                "código unidad orgánica superior",
                "codigo unidad superior",
                "código unidad superior",
                "codigo unidad padre",
                "código unidad padre",
                "codigo dir3 superior",
                "codigo dependencia organica",
                "dependencia organica codigo",
            ),
        )
    )
    version = _clean_version(
        pick_value(row, ("version", "versión", "version unidad", "versión unidad", "codigo unidad organica"))
        or code_raw
    )
    normalized: dict[str, Any] = {
        "record_kind": "dir3_org_unit",
        "source_catalog_url": DIR3_CATALOG_URL,
        "feed_url": feed_url,
        "source_url": feed_url,
        "source_record_id": f"dir3:{org_unit_code}",
        "org_unit_code": org_unit_code,
        "org_unit_version": version,
        "org_unit_name": normalize_ws(name),
        "normalized_name": normalize_key_part(name),
        "parent_org_unit_code": parent_code or None,
        "parent_org_unit_name": pick_value(
            row,
            (
                "denominacion unidad organica superior",
                "denominación unidad orgánica superior",
                "nombre unidad superior",
                "unidad superior",
                "dependencia organica",
            ),
        ),
        "administration_level": pick_value(
            row,
            (
                "nivel administracion",
                "nivel administración",
                "nivel de administracion",
                "nivel de administración",
                "administracion",
                "administración",
            ),
        ),
        "administration_name": pick_value(row, ("administracion", "administración", "nombre administracion")),
        "ministry_name": pick_value(row, ("ministerio", "departamento ministerial", "departamento")),
        "entity_type_code": pick_value(row, ("codigo tipo entidad publica", "código tipo entidad pública", "tipo entidad codigo")),
        "entity_type_label": pick_value(row, ("tipo entidad publica", "tipo entidad pública", "tipo entidad")),
        "unit_type_code": pick_value(row, ("codigo tipo unidad organica", "código tipo unidad orgánica", "tipo unidad codigo")),
        "unit_type_label": pick_value(row, ("tipo unidad organica", "tipo unidad orgánica", "tipo unidad")),
        "organic_level": _parse_int(pick_value(row, ("nivel jerarquico", "nivel jerárquico", "nivel organico", "nivel orgánico"))),
        "status": pick_value(row, ("estado", "situacion", "situación", "vigencia")),
        "valid_from": _pick_date(row, ("fecha alta", "fecha inicio", "fecha vigencia desde")),
        "valid_to": _pick_date(row, ("fecha baja", "fecha fin", "fecha extincion", "fecha extinción", "fecha vigencia hasta")),
        "raw_row": row,
    }
    return normalized


def dedupe_dir3_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        source_record_id = str(record.get("source_record_id") or "")
        if not source_record_id:
            continue
        current = by_id.get(source_record_id)
        if current is None:
            by_id[source_record_id] = dict(record)
            continue
        for key, value in record.items():
            if current.get(key) in (None, "") and value not in (None, ""):
                current[key] = value
    return [by_id[key] for key in sorted(by_id)]


def find_dir3_age_distribution_url(catalog_payload: dict[str, Any]) -> str | None:
    result = catalog_payload.get("result", {})
    items = result.get("items", []) if isinstance(result, dict) else []
    if not isinstance(items, list):
        return None

    for item in items:
        distributions = item.get("distribution", []) if isinstance(item, dict) else []
        if not isinstance(distributions, list):
            continue
        for distribution in distributions:
            if not isinstance(distribution, dict):
                continue
            title_values = distribution.get("title", [])
            titles = []
            if isinstance(title_values, list):
                for value in title_values:
                    if isinstance(value, dict):
                        titles.append(normalize_key_part(str(value.get("_value") or "")))
            title = " ".join(titles)
            if "unidades organicas" not in title or "age" not in title:
                continue
            access_url = normalize_ws(str(distribution.get("accessURL") or ""))
            if access_url:
                return access_url
    return None


def resolve_dir3_age_distribution_url(timeout: int) -> str | None:
    payload, content_type = http_get_bytes(DIR3_DATASET_API_URL, timeout)
    if payload_looks_like_html(payload):
        raise RuntimeError(f"Respuesta HTML inesperada para catalogo DIR3 (content_type={content_type or 'desconocido'})")
    catalog_payload = json.loads(payload.decode("utf-8"))
    if not isinstance(catalog_payload, dict):
        return None
    return find_dir3_age_distribution_url(catalog_payload)


class Dir3UnidadesAgeConnector(BaseConnector):
    source_id = "dir3_unidades_age"
    ingest_mode = "source_records_only"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        if url_override:
            return url_override
        try:
            resolved = resolve_dir3_age_distribution_url(timeout)
        except Exception:  # noqa: BLE001
            resolved = None
        return resolved or SOURCE_CONFIG[self.source_id].get("default_url", DIR3_AGE_XLSX_URL)

    def _records_from_payload(self, payload: bytes, *, feed_url: str, content_type: str | None) -> list[dict[str, Any]]:
        _ = content_type
        if payload.lstrip().startswith(b"{") or payload.lstrip().startswith(b"["):
            parsed = parse_json_source(payload)
            records = [record for record in parsed if isinstance(record, dict)]
            return dedupe_dir3_records(records)
        rows = parse_dir3_xlsx(payload)
        records = [record for row in rows if (record := normalize_dir3_record(row, feed_url=feed_url)) is not None]
        return dedupe_dir3_records(records)

    def _extracted(
        self,
        *,
        source_url: str,
        resolved_url: str,
        raw_dir: Path,
        records: list[dict[str, Any]],
        note: str,
    ) -> Extracted:
        serialized = json.dumps(
            {"source": self.source_id, "source_url": source_url, "records": records},
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
        fetched_at = now_utc_iso()
        raw_path = raw_output_path(raw_dir, self.source_id, "json")
        raw_path.write_bytes(serialized)
        return Extracted(
            source_id=self.source_id,
            source_url=source_url,
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
            payload = from_file.read_bytes()
            records = self._records_from_payload(payload, feed_url=resolved_url, content_type=None)
            if not records:
                raise RuntimeError(f"No se encontraron unidades DIR3 parseables en {from_file}")
            return self._extracted(
                source_url=resolved_url,
                resolved_url=resolved_url,
                raw_dir=raw_dir,
                records=records,
                note="from-file",
            )

        resolved_url = self.resolve_url(url_override, timeout)
        try:
            payload, content_type = http_get_bytes(resolved_url, timeout)
            records = self._records_from_payload(payload, feed_url=resolved_url, content_type=content_type)
            if not records:
                raise RuntimeError("No se encontraron unidades DIR3 parseables")
            return self._extracted(
                source_url=resolved_url,
                resolved_url=resolved_url,
                raw_dir=raw_dir,
                records=records,
                note="network",
            )
        except Exception as exc:  # noqa: BLE001
            if strict_network:
                raise
            fetched = fallback_payload_from_sample(
                self.source_id,
                raw_dir,
                note=f"network-error-fallback: {type(exc).__name__}: {exc}",
            )
            records = self._records_from_payload(
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
        source_record_id = normalize_ws(str(record.get("source_record_id") or ""))
        if not source_record_id:
            return None
        return {
            "source_record_id": source_record_id,
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
