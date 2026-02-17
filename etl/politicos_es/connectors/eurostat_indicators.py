from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes, payload_looks_like_html
from ..raw import fallback_payload_from_sample, raw_output_path
from ..types import Extracted
from ..util import normalize_key_part, normalize_ws, now_utc_iso, sha256_bytes, stable_json
from .base import BaseConnector


def _flatten_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("results", "items", "data", "series"):
            value = data.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        return [data]
    return []


def _normalize_series_dimensions(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    dims: dict[str, str] = {}
    for key, value in raw.items():
        dim = normalize_ws(str(key))
        code = normalize_ws(str(value))
        if dim and code:
            dims[dim] = code
    return dict(sorted(dims.items()))


def _normalize_series_dimension_labels(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    labels: dict[str, str] = {}
    for key, value in raw.items():
        dim = normalize_ws(str(key))
        label = normalize_ws(str(value))
        if dim and label:
            labels[dim] = label
    return dict(sorted(labels.items()))


def _normalize_points(raw_points: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_points, list):
        return []
    points: list[dict[str, Any]] = []
    for point in raw_points:
        if not isinstance(point, dict):
            continue
        period = normalize_ws(str(point.get("period") or ""))
        if not period:
            continue
        period_label = normalize_ws(str(point.get("period_label") or period)) or period
        numeric_value = _parse_numeric(point.get("value"))
        value_text = normalize_ws(str(point.get("value_text") or "")) or None
        if numeric_value is not None:
            value_text = None
        elif value_text is None and point.get("value") is not None:
            value_text = normalize_ws(str(point.get("value"))) or None
        points.append(
            {
                "period": period,
                "period_label": period_label,
                "value": numeric_value,
                "value_text": value_text,
            }
        )
    return sorted(points, key=lambda value: str(value.get("period") or ""))


def _normalize_dimension_codelists(
    raw: Any,
    *,
    series_dimensions: dict[str, str],
    series_dimension_labels: dict[str, str],
) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            dim = normalize_ws(str(key))
            if not dim:
                continue
            label = dim
            codes: list[str] = []
            if isinstance(value, dict):
                label = normalize_ws(str(value.get("label") or dim)) or dim
                raw_codes = value.get("codes")
                if isinstance(raw_codes, list):
                    codes = [normalize_ws(str(code)) for code in raw_codes if normalize_ws(str(code))]
                elif isinstance(raw_codes, dict):
                    codes = [normalize_ws(str(code)) for code in raw_codes.keys() if normalize_ws(str(code))]
            if not codes and dim in series_dimensions:
                codes = [series_dimensions[dim]]
            normalized[dim] = {"label": label, "codes": codes}
    if normalized:
        return normalized

    # Build minimal deterministic codelists from resolved dimensions when explicit metadata is unavailable.
    for dim, code in series_dimensions.items():
        normalized[dim] = {
            "label": normalize_ws(str(series_dimension_labels.get(dim) or dim)) or dim,
            "codes": [code],
        }
    return normalized


def _records_from_serialized_container(parsed: Any, *, feed_url: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(parsed, dict):
        records = parsed.get("records")
        if isinstance(records, list):
            candidates = [record for record in records if isinstance(record, dict)]
    elif isinstance(parsed, list):
        candidates = [record for record in parsed if isinstance(record, dict)]

    if not candidates:
        return []

    normalized_records: list[dict[str, Any]] = []
    for record in candidates:
        points = _normalize_points(record.get("points"))
        if not points:
            continue

        series_dimensions = _normalize_series_dimensions(record.get("series_dimensions"))
        series_dimension_labels = _normalize_series_dimension_labels(record.get("series_dimension_labels"))
        if not series_dimension_labels:
            series_dimension_labels = {key: key for key in series_dimensions.keys()}

        dataset_code = normalize_ws(str(record.get("dataset_code") or "")) or _dataset_code_from_source(feed_url, record)
        series_code = normalize_ws(str(record.get("series_code") or ""))
        if not series_code and series_dimensions:
            series_code = _series_code(dataset_code, series_dimensions)
        if not series_code:
            continue

        normalized = {
            "record_kind": normalize_ws(str(record.get("record_kind") or "eurostat_series")) or "eurostat_series",
            "source_feed": normalize_ws(str(record.get("source_feed") or "eurostat_jsonstat")) or "eurostat_jsonstat",
            "feed_url": normalize_ws(str(record.get("feed_url") or feed_url)) or feed_url,
            "source_url": normalize_ws(str(record.get("source_url") or record.get("feed_url") or feed_url)) or feed_url,
            "dataset_code": dataset_code,
            "series_code": series_code,
            "frequency": normalize_ws(str(record.get("frequency") or "")) or None,
            "unit": normalize_ws(str(record.get("unit") or "")) or None,
            "series_dimensions": series_dimensions,
            "series_dimension_labels": series_dimension_labels,
            "time_dimension": normalize_ws(str(record.get("time_dimension") or "time")) or "time",
            "metadata_version": normalize_ws(str(record.get("metadata_version") or "")) or None,
            "dimension_codelists": _normalize_dimension_codelists(
                record.get("dimension_codelists"),
                series_dimensions=series_dimensions,
                series_dimension_labels=series_dimension_labels,
            ),
            "points": points,
            "points_count": len(points),
        }
        source_record_id = normalize_ws(str(record.get("source_record_id") or ""))
        normalized["source_record_id"] = source_record_id or build_source_record_id(normalized)
        normalized_records.append(normalized)

    if not normalized_records:
        return []
    return _dedupe_records(normalized_records)


def _dataset_code_from_source(feed_url: str, payload: dict[str, Any]) -> str:
    ext = payload.get("extension")
    if isinstance(ext, dict):
        dataset_id = normalize_ws(str(ext.get("datasetId") or ""))
        if dataset_id:
            return dataset_id
    parsed = urlsplit(feed_url)
    marker = "/data/"
    if marker in parsed.path:
        tail = parsed.path.split(marker, 1)[1]
        dataset_id = normalize_ws(tail.split("/", 1)[0])
        if dataset_id:
            return dataset_id
    label = normalize_key_part(str(payload.get("label") or ""))
    if label:
        return label.replace(" ", "_")
    return "eurostat_dataset"


def _idx_to_code_list(category_index: Any, category_labels: dict[str, Any]) -> list[str]:
    if isinstance(category_index, list):
        return [str(item) for item in category_index]
    if isinstance(category_index, dict):
        pairs: list[tuple[int, str]] = []
        for code, idx in category_index.items():
            try:
                int_idx = int(idx)
            except (TypeError, ValueError):
                continue
            pairs.append((int_idx, str(code)))
        if pairs:
            pairs.sort(key=lambda pair: pair[0])
            return [code for _, code in pairs]
    if category_labels:
        return [str(code) for code in sorted(category_labels.keys())]
    return []


def _decode_flat_index(flat_index: int, sizes: list[int]) -> list[int]:
    coords = [0] * len(sizes)
    value = int(flat_index)
    for pos in range(len(sizes) - 1, -1, -1):
        size = int(sizes[pos])
        if size <= 0:
            coords[pos] = 0
            continue
        coords[pos] = value % size
        value //= size
    return coords


def _parse_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    token = normalize_ws(str(value)).replace(" ", "")
    if not token:
        return None
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        parts = token.split(",")
        if len(parts) == 2 and len(parts[1]) <= 3:
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def _series_code(dataset_code: str, dims: dict[str, str]) -> str:
    parts = [f"{dim}={dims[dim]}" for dim in sorted(dims.keys())]
    return f"{dataset_code}|{'|'.join(parts)}"


def build_source_record_id(record: dict[str, Any]) -> str:
    series_code = normalize_ws(str(record.get("series_code") or ""))
    if series_code:
        return f"series:{sha256_bytes(series_code.encode('utf-8'))[:24]}"
    raw_series = stable_json(record.get("series_dimensions") or {})
    return f"series:{sha256_bytes(raw_series.encode('utf-8'))[:24]}"


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        source_record_id = str(record.get("source_record_id") or "").strip()
        if not source_record_id:
            source_record_id = build_source_record_id(record)
            record = {**record, "source_record_id": source_record_id}
        current = by_id.get(source_record_id)
        if current is None:
            by_id[source_record_id] = dict(record)
            continue
        # Merge points deterministically by period key.
        point_map: dict[str, dict[str, Any]] = {}
        for point in current.get("points", []):
            period = str(point.get("period") or "")
            if period:
                point_map[period] = dict(point)
        for point in record.get("points", []):
            period = str(point.get("period") or "")
            if period:
                point_map[period] = dict(point)
        merged_points = [point_map[key] for key in sorted(point_map.keys())]
        current["points"] = merged_points
        current["points_count"] = len(merged_points)
        if current.get("metadata_version") in (None, "") and record.get("metadata_version") not in (None, ""):
            current["metadata_version"] = record.get("metadata_version")
    return [by_id[key] for key in sorted(by_id.keys())]


def parse_eurostat_records(payload: bytes, *, feed_url: str, content_type: str | None) -> list[dict[str, Any]]:
    payload_sig = sha256_bytes(payload)
    if payload_looks_like_html(payload):
        raise RuntimeError(f"Respuesta HTML inesperada para Eurostat feed (payload_sig={payload_sig})")
    payload_text = payload.decode("utf-8", errors="replace")
    if payload_text.lstrip().startswith("metric,value"):
        raise RuntimeError(
            "Payload invalido para Eurostat: se detecto CSV metric,value de run snapshot "
            f"(payload_sig={payload_sig})"
        )
    try:
        parsed = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON invalido para Eurostat ({exc}; payload_sig={payload_sig})") from exc

    replay_records = _records_from_serialized_container(parsed, feed_url=feed_url)
    if replay_records:
        return replay_records

    rows = _flatten_rows(parsed)
    extracted: list[dict[str, Any]] = []
    for row in rows:
        ids = row.get("id")
        sizes = row.get("size")
        dimensions = row.get("dimension")
        values_obj = row.get("value")
        if not isinstance(ids, list) or not isinstance(sizes, list) or not isinstance(dimensions, dict):
            continue
        if len(ids) != len(sizes):
            continue
        if not isinstance(values_obj, (dict, list)):
            continue

        dataset_code = _dataset_code_from_source(feed_url, row)
        metadata_version = normalize_ws(
            "|".join(
                token
                for token in (
                    str(row.get("version") or ""),
                    str(((row.get("extension") or {}) if isinstance(row.get("extension"), dict) else {}).get("updated") or ""),
                )
                if normalize_ws(token)
            )
        )

        dim_info: dict[str, dict[str, Any]] = {}
        for dim_id in ids:
            dim_key = str(dim_id)
            dim_obj = dimensions.get(dim_key)
            if not isinstance(dim_obj, dict):
                dim_info[dim_key] = {"codes": [], "labels": {}, "label": dim_key}
                continue
            category = dim_obj.get("category")
            cat_index = category.get("index") if isinstance(category, dict) else None
            cat_labels = category.get("label") if isinstance(category, dict) and isinstance(category.get("label"), dict) else {}
            codes = _idx_to_code_list(cat_index, cat_labels if isinstance(cat_labels, dict) else {})
            label = normalize_ws(str(dim_obj.get("label") or dim_key)) or dim_key
            labels_map = {str(code): normalize_ws(str(label_value)) for code, label_value in (cat_labels or {}).items()}
            dim_info[dim_key] = {"codes": codes, "labels": labels_map, "label": label}

        time_dim = "time" if "time" in [str(x) for x in ids] else str(ids[-1])
        values_iter: list[tuple[int, Any]] = []
        if isinstance(values_obj, dict):
            for raw_idx, raw_val in values_obj.items():
                try:
                    int_idx = int(raw_idx)
                except (TypeError, ValueError):
                    continue
                values_iter.append((int_idx, raw_val))
        else:
            for idx, raw_val in enumerate(values_obj):
                values_iter.append((idx, raw_val))

        grouped: dict[str, dict[str, Any]] = {}
        for flat_index, raw_value in sorted(values_iter, key=lambda item: item[0]):
            coords = _decode_flat_index(flat_index, [int(v) for v in sizes])
            series_dims: dict[str, str] = {}
            series_dim_labels: dict[str, str] = {}
            point_period = ""
            point_period_label = ""
            for pos, dim_id in enumerate(ids):
                dim_key = str(dim_id)
                info = dim_info.get(dim_key, {"codes": [], "labels": {}, "label": dim_key})
                codes = info.get("codes") or []
                idx = coords[pos] if pos < len(coords) else 0
                code = codes[idx] if idx < len(codes) else str(idx)
                code = str(code)
                label_map = info.get("labels") or {}
                code_label = normalize_ws(str(label_map.get(code) or code))
                if dim_key == time_dim:
                    point_period = code
                    point_period_label = code_label
                else:
                    series_dims[dim_key] = code
                    series_dim_labels[dim_key] = code_label
            if not point_period:
                continue
            series_code = _series_code(dataset_code, series_dims)
            group = grouped.get(series_code)
            if group is None:
                codelist_refs: dict[str, Any] = {}
                for dim_name, info in dim_info.items():
                    codelist_refs[dim_name] = {
                        "label": info.get("label"),
                        "codes": list(info.get("codes") or []),
                    }
                unit = series_dims.get("unit")
                freq = series_dims.get("freq")
                group = {
                    "record_kind": "eurostat_series",
                    "source_feed": "eurostat_jsonstat",
                    "feed_url": feed_url,
                    "source_url": feed_url,
                    "dataset_code": dataset_code,
                    "series_code": series_code,
                    "frequency": freq,
                    "unit": unit,
                    "series_dimensions": dict(sorted(series_dims.items())),
                    "series_dimension_labels": dict(sorted(series_dim_labels.items())),
                    "time_dimension": time_dim,
                    "metadata_version": metadata_version or None,
                    "dimension_codelists": codelist_refs,
                    "points": [],
                }
                grouped[series_code] = group
            numeric_value = _parse_numeric(raw_value)
            group["points"].append(
                {
                    "period": point_period,
                    "period_label": point_period_label,
                    "value": numeric_value,
                    "value_text": None if numeric_value is not None else normalize_ws(str(raw_value)),
                }
            )

        for group in grouped.values():
            group["points"] = sorted(group["points"], key=lambda point: str(point.get("period") or ""))
            group["points_count"] = len(group["points"])
            group["source_record_id"] = build_source_record_id(group)
            extracted.append(group)

    records = _dedupe_records(extracted)
    if records:
        return records
    raise RuntimeError(
        "No se encontraron series parseables en Eurostat "
        f"({payload_sig}; esperado JSON-stat o contenedor serializado con 'records')"
    )


class EurostatSdmxConnector(BaseConnector):
    source_id = "eurostat_sdmx"
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
                for sample in sorted(from_file.glob("*.json")):
                    payload = sample.read_bytes()
                    all_records.extend(
                        parse_eurostat_records(
                            payload,
                            feed_url=f"file://{sample.resolve()}",
                            content_type="application/json",
                        )
                    )
                records = _dedupe_records(all_records)
                if not records:
                    raise RuntimeError(f"No se encontraron JSON parseables en directorio Eurostat: {from_file}")
                serialized = json.dumps(
                    {"source": "eurostat_sdmx_dir", "dir": str(from_file), "records": records},
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
            records = parse_eurostat_records(payload, feed_url=resolved_url, content_type="application/json")
            serialized = json.dumps(
                {"source": "eurostat_sdmx_file", "file": str(from_file), "records": records},
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
            records = parse_eurostat_records(payload, feed_url=resolved_url, content_type=content_type)
            serialized = json.dumps(
                {"source": "eurostat_sdmx_network", "feed_url": resolved_url, "records": records},
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
            records = parse_eurostat_records(
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
            source_record_id = build_source_record_id(record)
        if not source_record_id:
            return None
        return {
            "source_record_id": source_record_id,
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
