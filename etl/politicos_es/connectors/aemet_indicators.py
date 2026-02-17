from __future__ import annotations

import json
import os
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes, payload_looks_like_html
from ..raw import fallback_payload_from_sample, raw_output_path
from ..types import Extracted
from ..util import normalize_key_part, normalize_ws, now_utc_iso, parse_date_flexible, sha256_bytes, stable_json
from .base import BaseConnector


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


def _series_key(raw: str | None) -> str:
    return normalize_key_part(raw or "").replace(" ", "_")


def _classify_aemet_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        code = int(getattr(exc, "code", 0) or 0)
        if code in {401, 403}:
            return "auth"
        if 400 <= code < 500:
            return "contract"
        return "network"
    if isinstance(exc, FileNotFoundError):
        return "contract"
    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return "network"

    message = normalize_ws(str(exc)).lower()
    if "aemet_api_key" in message or ("api_key" in message and "no definido" in message):
        return "auth"
    contract_signals = (
        "respuesta html inesperada",
        "json invalido para aemet",
        "no se encontraron series parseables en aemet",
        "no se pudieron construir series normalizadas en aemet",
        "metric,value",
        "http error 404",
    )
    if any(signal in message for signal in contract_signals):
        return "contract"
    if "http error 401" in message or "http error 403" in message:
        return "auth"
    return "network"


def _raise_blocker_error(exc: Exception) -> RuntimeError:
    blocker = _classify_aemet_error(exc)
    return RuntimeError(f"aemet_blocker={blocker}; error_type={type(exc).__name__}; detail={exc}")


def build_source_record_id(record: dict[str, Any]) -> str:
    station = _series_key(str(record.get("station_id") or ""))
    variable = _series_key(str(record.get("variable") or ""))
    if station and variable:
        return f"station:{station}:var:{variable}"
    if station:
        return f"station:{station}"
    if variable:
        return f"var:{variable}"
    return f"series:{sha256_bytes(stable_json(record.get('series_dimensions') or {}).encode('utf-8'))[:24]}"


def _normalize_station(raw: dict[str, Any]) -> dict[str, Any]:
    station_id = normalize_ws(
        str(raw.get("indicativo") or raw.get("station_id") or raw.get("idema") or raw.get("id") or "")
    )
    station_name = normalize_ws(str(raw.get("nombre") or raw.get("name") or raw.get("estacion") or ""))
    province = normalize_ws(str(raw.get("provincia") or raw.get("province") or ""))
    lat = normalize_ws(str(raw.get("latitud") or raw.get("lat") or raw.get("latitude") or ""))
    lon = normalize_ws(str(raw.get("longitud") or raw.get("lon") or raw.get("longitude") or ""))
    altitude = normalize_ws(str(raw.get("altitud") or raw.get("altitude") or ""))
    return {
        "station_id": station_id or None,
        "station_name": station_name or None,
        "province": province or None,
        "lat": lat or None,
        "lon": lon or None,
        "altitude_m": altitude or None,
    }


def _points_from_rows(rows: list[dict[str, Any]], *, variable: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for row in rows:
        period = normalize_ws(
            str(
                row.get("period")
                or row.get("fecha")
                or row.get("date")
                or row.get("fint")
                or row.get("timestamp")
                or ""
            )
        )
        if not period:
            continue
        value_raw = row.get(variable)
        if value_raw is None and "value" in row:
            value_raw = row.get("value")
        value = _parse_numeric(value_raw)
        points.append(
            {
                "period": period,
                "period_label": period,
                "value": value,
                "value_text": None if value is not None else normalize_ws(str(value_raw)),
            }
        )
    return sorted(points, key=lambda point: str(point.get("period") or ""))


def _records_from_series_payload(
    series_rows: list[dict[str, Any]],
    *,
    stations_by_id: dict[str, dict[str, Any]],
    feed_url: str,
    metadata_refs: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in series_rows:
        variable = normalize_ws(str(row.get("variable") or row.get("var") or row.get("indicador") or ""))
        if not variable:
            variable = "value"
        station_raw = _normalize_station(row)
        station_id = station_raw.get("station_id") or normalize_ws(str(row.get("station") or ""))
        station = dict(stations_by_id.get(str(station_id or ""), {}))
        station = {**station, **{k: v for k, v in station_raw.items() if v not in (None, "")}}
        station_id = station.get("station_id")
        if not station_id:
            continue
        rows = row.get("values")
        if not isinstance(rows, list):
            rows = row.get("observations")
        if not isinstance(rows, list):
            rows = row.get("data")
        if not isinstance(rows, list):
            rows = []
        value_rows = [item for item in rows if isinstance(item, dict)]
        if not value_rows:
            # Accept single-row style payload.
            value_rows = [row]

        points = _points_from_rows(value_rows, variable=variable)
        if not points:
            continue

        frequency = normalize_ws(str(row.get("frequency") or row.get("freq") or row.get("periodicidad") or ""))
        unit = normalize_ws(str(row.get("unit") or row.get("unidad") or row.get("units") or ""))
        dataset_code = normalize_ws(str(row.get("dataset") or row.get("dataset_code") or "aemet_opendata"))
        series_code = f"{dataset_code}|station={station_id}|var={variable}"
        metadata_version = normalize_ws(
            "|".join(
                token
                for token in (
                    str(row.get("updated_at") or row.get("actualizado") or ""),
                    str(metadata_refs.get("updated") or ""),
                )
                if normalize_ws(token)
            )
        )

        record: dict[str, Any] = {
            "record_kind": "aemet_station_series",
            "source_feed": "aemet_opendata",
            "feed_url": feed_url,
            "source_url": normalize_ws(str(row.get("source_url") or feed_url)),
            "dataset_code": dataset_code,
            "station_id": station_id,
            "station_name": station.get("station_name"),
            "province": station.get("province"),
            "lat": station.get("lat"),
            "lon": station.get("lon"),
            "altitude_m": station.get("altitude_m"),
            "variable": variable,
            "series_code": series_code,
            "frequency": frequency or None,
            "unit": unit or None,
            "series_dimensions": {
                "station_id": station_id,
                "variable": variable,
                "province": station.get("province"),
            },
            "series_dimension_labels": {
                "station_id": station.get("station_name") or station_id,
                "variable": variable,
            },
            "time_dimension": "period",
            "metadata_version": metadata_version or None,
            "metadata_refs": metadata_refs,
            "points": points,
            "points_count": len(points),
        }
        record["source_record_id"] = build_source_record_id(record)
        records.append(record)
    return records


def _normalize_series_dimensions(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, Any] = {}
    for key, value in raw.items():
        dim = normalize_ws(str(key))
        if not dim:
            continue
        if isinstance(value, str):
            result[dim] = normalize_ws(value) or value
        else:
            result[dim] = value
    return result


def _normalize_series_dimension_labels(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    labels: dict[str, str] = {}
    for key, value in raw.items():
        dim = normalize_ws(str(key))
        label = normalize_ws(str(value))
        if dim and label:
            labels[dim] = label
    return labels


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

    normalized: list[dict[str, Any]] = []
    for row in candidates:
        station_id = normalize_ws(
            str(
                row.get("station_id")
                or ((row.get("series_dimensions") or {}) if isinstance(row.get("series_dimensions"), dict) else {}).get(
                    "station_id"
                )
                or ""
            )
        )
        variable = normalize_ws(
            str(
                row.get("variable")
                or ((row.get("series_dimensions") or {}) if isinstance(row.get("series_dimensions"), dict) else {}).get(
                    "variable"
                )
                or ""
            )
        )
        if not station_id or not variable:
            continue

        points = _points_from_rows([item for item in row.get("points", []) if isinstance(item, dict)], variable=variable)
        if not points:
            points = _points_from_rows([item for item in row.get("values", []) if isinstance(item, dict)], variable=variable)
        if not points:
            continue

        dataset_code = normalize_ws(str(row.get("dataset_code") or row.get("dataset") or "aemet_opendata"))
        series_code = normalize_ws(str(row.get("series_code") or ""))
        if not series_code:
            series_code = f"{dataset_code}|station={station_id}|var={variable}"

        metadata_refs = row.get("metadata_refs") if isinstance(row.get("metadata_refs"), dict) else {}
        source_url = normalize_ws(str(row.get("source_url") or row.get("feed_url") or feed_url)) or feed_url
        series_dimensions = _normalize_series_dimensions(row.get("series_dimensions"))
        if not series_dimensions:
            series_dimensions = {"station_id": station_id, "variable": variable, "province": row.get("province")}
        series_dimension_labels = _normalize_series_dimension_labels(row.get("series_dimension_labels"))
        if not series_dimension_labels:
            series_dimension_labels = {
                "station_id": normalize_ws(str(row.get("station_name") or station_id)) or station_id,
                "variable": variable,
            }

        record: dict[str, Any] = {
            "record_kind": normalize_ws(str(row.get("record_kind") or "aemet_station_series")) or "aemet_station_series",
            "source_feed": normalize_ws(str(row.get("source_feed") or "aemet_opendata")) or "aemet_opendata",
            "feed_url": normalize_ws(str(row.get("feed_url") or feed_url)) or feed_url,
            "source_url": source_url,
            "dataset_code": dataset_code,
            "station_id": station_id,
            "station_name": normalize_ws(str(row.get("station_name") or "")) or None,
            "province": normalize_ws(str(row.get("province") or "")) or None,
            "lat": normalize_ws(str(row.get("lat") or "")) or None,
            "lon": normalize_ws(str(row.get("lon") or "")) or None,
            "altitude_m": normalize_ws(str(row.get("altitude_m") or "")) or None,
            "variable": variable,
            "series_code": series_code,
            "frequency": normalize_ws(str(row.get("frequency") or "")) or None,
            "unit": normalize_ws(str(row.get("unit") or "")) or None,
            "series_dimensions": series_dimensions,
            "series_dimension_labels": series_dimension_labels,
            "time_dimension": normalize_ws(str(row.get("time_dimension") or "period")) or "period",
            "metadata_version": normalize_ws(str(row.get("metadata_version") or "")) or None,
            "metadata_refs": metadata_refs,
            "points": points,
            "points_count": len(points),
        }
        source_record_id = normalize_ws(str(row.get("source_record_id") or ""))
        record["source_record_id"] = source_record_id or build_source_record_id(record)
        normalized.append(record)

    if not normalized:
        return []
    return _dedupe_records(normalized)


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
    return [by_id[key] for key in sorted(by_id.keys())]


def parse_aemet_records(payload: bytes, *, feed_url: str, content_type: str | None) -> list[dict[str, Any]]:
    payload_sig = sha256_bytes(payload)
    if payload_looks_like_html(payload):
        raise RuntimeError(f"Respuesta HTML inesperada para AEMET feed (payload_sig={payload_sig})")
    payload_text = payload.decode("utf-8", errors="replace")
    if payload_text.lstrip().startswith("metric,value"):
        raise RuntimeError(
            "Payload invalido para AEMET: se detecto CSV metric,value de run snapshot "
            f"(payload_sig={payload_sig})"
        )
    try:
        parsed = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON invalido para AEMET ({exc}; payload_sig={payload_sig})") from exc

    replay_records = _records_from_serialized_container(parsed, feed_url=feed_url)
    if replay_records:
        return replay_records

    metadata_refs: dict[str, Any] = {}
    stations_by_id: dict[str, dict[str, Any]] = {}
    series_rows: list[dict[str, Any]] = []

    if isinstance(parsed, dict):
        if isinstance(parsed.get("metadatos"), str):
            metadata_refs["metadatos_url"] = normalize_ws(str(parsed.get("metadatos")))
        if isinstance(parsed.get("descripcion"), str):
            metadata_refs["descripcion"] = normalize_ws(str(parsed.get("descripcion")))
        if isinstance(parsed.get("updated"), str):
            metadata_refs["updated"] = _parse_datetime_iso(str(parsed.get("updated")))

        stations = parsed.get("stations")
        if isinstance(stations, list):
            for raw_station in stations:
                if not isinstance(raw_station, dict):
                    continue
                station = _normalize_station(raw_station)
                station_id = str(station.get("station_id") or "")
                if station_id:
                    stations_by_id[station_id] = station

        series_obj = parsed.get("series")
        if isinstance(series_obj, list):
            series_rows = [row for row in series_obj if isinstance(row, dict)]
        else:
            datos_obj = parsed.get("datos")
            if isinstance(datos_obj, list):
                series_rows = [row for row in datos_obj if isinstance(row, dict)]
    elif isinstance(parsed, list):
        series_rows = [row for row in parsed if isinstance(row, dict)]

    if not series_rows:
        raise RuntimeError(f"No se encontraron series parseables en AEMET ({payload_sig})")

    records = _records_from_series_payload(
        series_rows,
        stations_by_id=stations_by_id,
        feed_url=feed_url,
        metadata_refs=metadata_refs,
    )
    deduped = _dedupe_records(records)
    if deduped:
        return deduped
    raise RuntimeError(
        "No se pudieron construir series normalizadas en AEMET "
        f"({payload_sig}; esperado payload AEMET o contenedor serializado con 'records')"
    )


class AemetOpenDataSeriesConnector(BaseConnector):
    source_id = "aemet_opendata_series"
    ingest_mode = "source_records_only"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        base_url = url_override or SOURCE_CONFIG[self.source_id]["default_url"]
        token = normalize_ws(os.getenv("AEMET_API_KEY", ""))
        if "{api_key}" in base_url:
            if not token:
                raise RuntimeError(
                    "AEMET_API_KEY no definido: requerido para reemplazar '{api_key}' en URL de AEMET"
                )
            return base_url.replace("{api_key}", token)
        if token and "api_key=" not in base_url:
            split = urlsplit(base_url)
            query = split.query
            params = dict()
            if query:
                for pair in query.split("&"):
                    if "=" not in pair:
                        continue
                    k, v = pair.split("=", 1)
                    params[k] = v
            params["api_key"] = token
            return urlunsplit((split.scheme, split.netloc, split.path, urlencode(params), split.fragment))
        return base_url

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
    ) -> Extracted:
        if from_file is not None:
            try:
                if from_file.is_dir():
                    all_records: list[dict[str, Any]] = []
                    for sample in sorted(from_file.glob("*.json")):
                        sample_payload = sample.read_bytes()
                        all_records.extend(
                            parse_aemet_records(
                                sample_payload,
                                feed_url=f"file://{sample.resolve()}",
                                content_type="application/json",
                            )
                        )
                    records = _dedupe_records(all_records)
                    if not records:
                        raise RuntimeError(f"No se encontraron JSON parseables en directorio AEMET: {from_file}")
                    serialized = json.dumps(
                        {"source": "aemet_opendata_series_dir", "dir": str(from_file), "records": records},
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
                records = parse_aemet_records(payload, feed_url=resolved_url, content_type="application/json")
                serialized = json.dumps(
                    {"source": "aemet_opendata_series_file", "file": str(from_file), "records": records},
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
            except Exception as exc:  # noqa: BLE001
                raise _raise_blocker_error(exc) from exc

        try:
            resolved_url = self.resolve_url(url_override, timeout)
            payload, content_type = http_get_bytes(resolved_url, timeout)
            try:
                envelope = json.loads(payload.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                envelope = None

            # AEMET often returns an envelope with `datos` URL that requires a second fetch.
            if isinstance(envelope, dict) and isinstance(envelope.get("datos"), str):
                data_url = normalize_ws(str(envelope.get("datos")))
                if data_url.startswith("http"):
                    payload, content_type = http_get_bytes(data_url, timeout)
                    resolved_url = data_url

            records = parse_aemet_records(payload, feed_url=resolved_url, content_type=content_type)
            serialized = json.dumps(
                {"source": "aemet_opendata_series_network", "feed_url": resolved_url, "records": records},
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
                raise _raise_blocker_error(exc) from exc
            blocker = _classify_aemet_error(exc)
            fetched = fallback_payload_from_sample(
                self.source_id,
                raw_dir,
                note=f"{blocker}-error-fallback: {type(exc).__name__}: {exc}",
            )
            try:
                records = parse_aemet_records(
                    fetched["payload"],
                    feed_url=fetched["source_url"],
                    content_type=fetched.get("content_type"),
                )
            except Exception as parse_exc:  # noqa: BLE001
                raise _raise_blocker_error(parse_exc) from parse_exc
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
