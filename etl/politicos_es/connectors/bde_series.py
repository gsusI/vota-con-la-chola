from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes, payload_looks_like_html
from ..raw import fallback_payload_from_sample, raw_output_path
from ..types import Extracted
from ..util import normalize_key_part, normalize_ws, now_utc_iso, parse_date_flexible, sha256_bytes, stable_json
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


def _extract_series_code(row: dict[str, Any]) -> str:
    series_code = normalize_ws(
        str(
            row.get("series_code")
            or row.get("codigo")
            or row.get("codSerie")
            or row.get("id")
            or row.get("serie")
            or ""
        )
    )
    if not series_code and isinstance(row.get("metadata"), dict):
        series_code = normalize_ws(str((row.get("metadata") or {}).get("codigo") or ""))
    return series_code


def _extract_frequency(row: dict[str, Any]) -> str:
    return normalize_ws(
        str(
            row.get("frequency")
            or row.get("frecuencia")
            or row.get("freq")
            or ((row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}).get("frecuencia")
            or ""
        )
    )


def _extract_unit(row: dict[str, Any]) -> str:
    return normalize_ws(
        str(
            row.get("unit")
            or row.get("unidad")
            or row.get("units")
            or ((row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}).get("unidad")
            or ""
        )
    )


def _extract_label(row: dict[str, Any], *, series_code: str) -> str:
    return normalize_ws(
        str(
            row.get("label")
            or row.get("descripcion")
            or row.get("title")
            or ((row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}).get("descripcion")
            or series_code
        )
    )


def _extract_points(points_obj: Any) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    if not isinstance(points_obj, list):
        return points
    for point in points_obj:
        if isinstance(point, dict):
            period = normalize_ws(
                str(
                    point.get("period")
                    or point.get("fecha")
                    or point.get("date")
                    or point.get("time")
                    or ""
                )
            )
            raw_value = point.get("value", point.get("valor"))
            period_label = normalize_ws(str(point.get("period_label") or period)) or period
            value_text = normalize_ws(str(point.get("value_text") or "")) or None
        elif isinstance(point, list) and len(point) >= 2:
            period = normalize_ws(str(point[0] or ""))
            raw_value = point[1]
            period_label = period
            value_text = None
        else:
            continue
        if not period:
            continue
        numeric = _parse_numeric(raw_value)
        if numeric is not None:
            value_text = None
        elif value_text is None:
            value_text = normalize_ws(str(raw_value))
        points.append(
            {
                "period": period,
                "period_label": period_label,
                "value": numeric,
                "value_text": value_text or None,
            }
        )
    return sorted(points, key=lambda item: str(item.get("period") or ""))


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
    for row in candidates:
        series_code = _extract_series_code(row)
        if not series_code:
            continue

        freq = _extract_frequency(row)
        unit = _extract_unit(row)
        label = _extract_label(row, series_code=series_code)
        points = _extract_points(row.get("points"))
        if not points:
            points = _extract_points(row.get("observations"))
        if not points:
            points = _extract_points(row.get("data"))
        if not points:
            continue

        metadata_version = normalize_ws(
            "|".join(
                token
                for token in (
                    str(row.get("metadata_version") or ""),
                    str(row.get("updated_at") or row.get("actualizado") or ""),
                )
                if normalize_ws(token)
            )
        )
        source_url = normalize_ws(str(row.get("source_url") or row.get("feed_url") or feed_url)) or feed_url

        series_dimensions = _normalize_series_dimensions(row.get("series_dimensions"))
        if not series_dimensions:
            series_dimensions = {"source": "bde_api", "series_code": series_code}
            if freq:
                series_dimensions["freq"] = freq
            if unit:
                series_dimensions["unit"] = unit

        series_dimension_labels = _normalize_series_dimension_labels(row.get("series_dimension_labels"))
        if not series_dimension_labels:
            series_dimension_labels = {"series_code": label}

        record: dict[str, Any] = {
            "record_kind": normalize_ws(str(row.get("record_kind") or "bde_series")) or "bde_series",
            "source_feed": normalize_ws(str(row.get("source_feed") or "bde_series_api")) or "bde_series_api",
            "feed_url": normalize_ws(str(row.get("feed_url") or feed_url)) or feed_url,
            "source_url": source_url,
            "dataset_code": normalize_ws(str(row.get("dataset_code") or "bde_series_api")) or "bde_series_api",
            "series_code": series_code,
            "series_label": label,
            "frequency": freq or None,
            "unit": unit or None,
            "series_dimensions": series_dimensions,
            "series_dimension_labels": series_dimension_labels,
            "time_dimension": normalize_ws(str(row.get("time_dimension") or "period")) or "period",
            "metadata_version": metadata_version or None,
            "points": points,
            "points_count": len(points),
        }
        source_record_id = normalize_ws(str(row.get("source_record_id") or ""))
        record["source_record_id"] = source_record_id or build_source_record_id(record)
        normalized_records.append(record)

    if not normalized_records:
        return []
    return _dedupe_records(normalized_records)


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
    date_only = parse_date_flexible(text)
    if date_only:
        return f"{date_only}T00:00:00+00:00"
    return None


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


def _series_key_token(raw: str | None) -> str:
    key = normalize_key_part(raw or "")
    return key.replace(" ", "_")


def build_source_record_id(record: dict[str, Any]) -> str:
    series_code = normalize_ws(str(record.get("series_code") or ""))
    if series_code:
        return f"series:{_series_key_token(series_code)}"
    fallback = stable_json(record.get("series_dimensions") or {})
    return f"series:{sha256_bytes(fallback.encode('utf-8'))[:24]}"


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
        point_map: dict[str, dict[str, Any]] = {}
        for point in current.get("points", []):
            period = str(point.get("period") or "")
            if period:
                point_map[period] = dict(point)
        for point in record.get("points", []):
            period = str(point.get("period") or "")
            if period:
                point_map[period] = dict(point)
        merged = [point_map[key] for key in sorted(point_map.keys())]
        current["points"] = merged
        current["points_count"] = len(merged)
        if current.get("metadata_version") in (None, "") and record.get("metadata_version") not in (None, ""):
            current["metadata_version"] = record.get("metadata_version")
    return [by_id[key] for key in sorted(by_id.keys())]


def parse_bde_records(payload: bytes, *, feed_url: str, content_type: str | None) -> list[dict[str, Any]]:
    payload_sig = sha256_bytes(payload)
    if payload_looks_like_html(payload):
        raise RuntimeError(f"Respuesta HTML inesperada para BDE feed (payload_sig={payload_sig})")
    payload_text = payload.decode("utf-8", errors="replace")
    if payload_text.lstrip().startswith("metric,value"):
        raise RuntimeError(
            "Payload invalido para BDE: se detecto CSV metric,value de run snapshot "
            f"(payload_sig={payload_sig})"
        )
    try:
        parsed = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON invalido para BDE ({exc}; payload_sig={payload_sig})") from exc

    replay_records = _records_from_serialized_container(parsed, feed_url=feed_url)
    if replay_records:
        return replay_records

    rows = _flatten_rows(parsed)
    extracted: list[dict[str, Any]] = []
    for row in rows:
        series_code = _extract_series_code(row)
        if not series_code:
            continue

        freq = _extract_frequency(row)
        unit = _extract_unit(row)
        label = _extract_label(row, series_code=series_code)

        points_obj = row.get("points")
        if not isinstance(points_obj, list):
            points_obj = row.get("observations")
        if not isinstance(points_obj, list):
            points_obj = row.get("data")
        points = _extract_points(points_obj)
        if not points:
            continue

        metadata_version = normalize_ws(
            "|".join(
                token
                for token in (
                    str(row.get("metadata_version") or ""),
                    str(row.get("updated_at") or row.get("actualizado") or ""),
                )
                if normalize_ws(token)
            )
        )

        source_url = normalize_ws(str(row.get("source_url") or feed_url))
        series_dimensions = {"source": "bde_api", "series_code": series_code}
        if freq:
            series_dimensions["freq"] = freq
        if unit:
            series_dimensions["unit"] = unit

        record: dict[str, Any] = {
            "record_kind": "bde_series",
            "source_feed": "bde_series_api",
            "feed_url": feed_url,
            "source_url": source_url,
            "dataset_code": "bde_series_api",
            "series_code": series_code,
            "series_label": label,
            "frequency": freq or None,
            "unit": unit or None,
            "series_dimensions": series_dimensions,
            "series_dimension_labels": {"series_code": label},
            "time_dimension": "period",
            "metadata_version": metadata_version or None,
            "points": sorted(points, key=lambda item: str(item.get("period") or "")),
        }
        record["points_count"] = len(record["points"])
        record["source_record_id"] = build_source_record_id(record)
        extracted.append(record)

    records = _dedupe_records(extracted)
    if records:
        return records
    raise RuntimeError(
        "No se encontraron series parseables en BDE "
        f"({payload_sig}; esperado payload BDE o contenedor serializado con 'records')"
    )


class BdeSeriesApiConnector(BaseConnector):
    source_id = "bde_series_api"
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
                        parse_bde_records(
                            payload,
                            feed_url=f"file://{sample.resolve()}",
                            content_type="application/json",
                        )
                    )
                records = _dedupe_records(all_records)
                if not records:
                    raise RuntimeError(f"No se encontraron JSON parseables en directorio BDE: {from_file}")
                serialized = json.dumps(
                    {"source": "bde_series_api_dir", "dir": str(from_file), "records": records},
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
            records = parse_bde_records(payload, feed_url=resolved_url, content_type="application/json")
            serialized = json.dumps(
                {"source": "bde_series_api_file", "file": str(from_file), "records": records},
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
            records = parse_bde_records(payload, feed_url=resolved_url, content_type=content_type)
            serialized = json.dumps(
                {"source": "bde_series_api_network", "feed_url": resolved_url, "records": records},
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
            records = parse_bde_records(
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
