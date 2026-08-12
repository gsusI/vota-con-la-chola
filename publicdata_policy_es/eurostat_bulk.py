"""Bounded Eurostat JSON-stat loading for million-row indicator cohorts."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from publicdata_connectors_es.outcomes.eurostat_indicators import build_source_record_id
from publicdata_core.util import normalize_ws, now_utc_iso, sha256_bytes, stable_json
from publicdata_sqlite import upsert_source_records_with_content_sha256

SOURCE_ID = "eurostat_sdmx"


def _dataset_code(source_url: str) -> str:
    path = urlsplit(source_url).path
    marker = "/data/"
    if marker not in path:
        raise ValueError(f"Eurostat source URL lacks /data/<dataset>: {source_url}")
    code = normalize_ws(path.split(marker, 1)[1].split("/", 1)[0]).lower()
    if not code:
        raise ValueError(f"Eurostat dataset code is empty: {source_url}")
    return code


def _rows(parsed: Any) -> list[dict[str, Any]]:
    if isinstance(parsed, dict) and isinstance(parsed.get("id"), list):
        return [parsed]
    if isinstance(parsed, list):
        return [row for row in parsed if isinstance(row, dict)]
    if isinstance(parsed, dict):
        for key in ("results", "items", "data", "series"):
            value = parsed.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _dimension_codes(
    dimension: dict[str, Any], dim_id: str
) -> tuple[list[str], dict[str, str], str]:
    raw = dimension.get(dim_id)
    if not isinstance(raw, dict):
        raise TypeError(f"Eurostat dimension metadata missing: {dim_id}")
    category = raw.get("category")
    if not isinstance(category, dict):
        raise TypeError(f"Eurostat dimension category missing: {dim_id}")
    index = category.get("index")
    labels_raw = category.get("label")
    labels = (
        {str(key): normalize_ws(str(value)) for key, value in labels_raw.items()}
        if isinstance(labels_raw, dict)
        else {}
    )
    if isinstance(index, list):
        codes = [str(value) for value in index]
    elif isinstance(index, dict):
        ordered: list[tuple[int, str]] = []
        for code, position in index.items():
            try:
                ordered.append((int(position), str(code)))
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"Eurostat dimension index is not numeric: {dim_id}={position}"
                ) from exc
        ordered.sort()
        positions = [position for position, _ in ordered]
        if positions != list(range(len(positions))):
            raise RuntimeError(f"Eurostat dimension index is not contiguous: {dim_id}")
        codes = [code for _, code in ordered]
    else:
        codes = list(labels)
    if not codes:
        raise RuntimeError(f"Eurostat dimension has no codes: {dim_id}")
    if len(set(codes)) != len(codes):
        raise RuntimeError(f"Eurostat dimension has duplicate codes: {dim_id}")
    return codes, labels, normalize_ws(str(raw.get("label") or dim_id)) or dim_id


def _value_items(values: Any, *, cube_cells: int) -> Iterator[tuple[int, Any]]:
    if isinstance(values, list):
        if len(values) > int(cube_cells):
            raise RuntimeError(
                f"Eurostat value array exceeds cube bounds: values={len(values)} cells={cube_cells}"
            )
        for index, value in enumerate(values):
            if value is not None:
                yield index, value
        return
    if not isinstance(values, dict):
        raise TypeError("Eurostat value must be a JSON object or array")
    for raw_index in values:
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Eurostat value index is not numeric: {raw_index}"
            ) from exc
        if index < 0 or index >= int(cube_cells):
            raise RuntimeError(
                f"Eurostat value index exceeds cube bounds: index={index} cells={cube_cells}"
            )
    # Eurostat serializes sparse numeric keys lexically in some responses.
    # Traverse bounded cube coordinates instead of sorting a million-key list.
    for index in range(int(cube_cells)):
        value = values.get(str(index))
        if value is not None:
            yield index, value


def _metadata_version(row: dict[str, Any]) -> str | None:
    extension = row.get("extension")
    updated = extension.get("updated") if isinstance(extension, dict) else None
    token = normalize_ws(
        "|".join(
            value
            for value in (str(row.get("version") or ""), str(updated or ""))
            if normalize_ws(value)
        )
    )
    return token or None


def inspect_eurostat_jsonstat(
    path: Path,
    *,
    source_url: str,
    expected_dataset_code: str | None = None,
    maximum_cube_cells: int | None = None,
) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        parsed = json.load(handle)
    rows = _rows(parsed)
    if len(rows) != 1:
        raise RuntimeError(f"Expected one Eurostat JSON-stat cube, found {len(rows)}")
    row = rows[0]
    ids = row.get("id")
    sizes = row.get("size")
    dimensions = row.get("dimension")
    if (
        not isinstance(ids, list)
        or not isinstance(sizes, list)
        or not isinstance(dimensions, dict)
    ):
        raise TypeError("Eurostat JSON-stat cube lacks id/size/dimension metadata")
    if len(ids) != len(sizes) or not ids:
        raise RuntimeError("Eurostat JSON-stat id/size dimensions are inconsistent")
    dim_ids = [str(value) for value in ids]
    time_dimension = "time" if "time" in dim_ids else dim_ids[-1]
    if dim_ids[-1] != time_dimension:
        raise RuntimeError(
            "Eurostat bulk loader requires the time dimension to be last"
        )
    for position, dim_id in enumerate(dim_ids):
        codes, _, _ = _dimension_codes(dimensions, dim_id)
        if len(codes) != int(sizes[position]):
            raise RuntimeError(
                f"Eurostat dimension size mismatch for {dim_id}: metadata={len(codes)} size={sizes[position]}"
            )
    dataset_code = _dataset_code(source_url)
    if (
        expected_dataset_code
        and dataset_code != normalize_ws(expected_dataset_code).lower()
    ):
        raise RuntimeError(
            f"Eurostat dataset mismatch: expected={expected_dataset_code} observed={dataset_code}"
        )
    time_size = int(sizes[-1])
    cube_cells = 1
    for size in sizes:
        if int(size) < 1:
            raise RuntimeError(f"Eurostat dimension size must be positive: {size}")
        cube_cells *= int(size)
    if maximum_cube_cells is not None and cube_cells > int(maximum_cube_cells):
        raise RuntimeError(
            "Eurostat cube-cell ceiling exceeded: "
            f"cells={cube_cells} maximum={maximum_cube_cells}"
        )
    observations = 0
    series_with_values = 0
    previous_series = -1
    maximum_index = -1
    for flat_index, _ in _value_items(row.get("value"), cube_cells=cube_cells):
        observations += 1
        maximum_index = flat_index
        series_index = flat_index // time_size
        if series_index != previous_series:
            series_with_values += 1
            previous_series = series_index
    if maximum_index >= cube_cells:
        raise RuntimeError(
            f"Eurostat value index exceeds cube bounds: index={maximum_index} cells={cube_cells}"
        )
    return {
        "dataset_code": dataset_code,
        "dataset_label": normalize_ws(str(row.get("label") or dataset_code))
        or dataset_code,
        "metadata_version": _metadata_version(row),
        "dimensions": dim_ids,
        "dimension_sizes": [int(value) for value in sizes],
        "cube_cells": cube_cells,
        "series_with_values": series_with_values,
        "observations": observations,
        "time_dimension": time_dimension,
        "time_dimension_last": True,
    }


def iter_eurostat_jsonstat_series(
    path: Path,
    *,
    source_url: str,
    domain_key: str | None = None,
    maximum_cube_cells: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield one compact series at a time from an ordered JSON-stat cube."""

    with Path(path).open("r", encoding="utf-8") as handle:
        parsed = json.load(handle)
    rows = _rows(parsed)
    if len(rows) != 1:
        raise RuntimeError(f"Expected one Eurostat JSON-stat cube, found {len(rows)}")
    row = rows[0]
    ids = [str(value) for value in row["id"]]
    sizes = [int(value) for value in row["size"]]
    dimension = row["dimension"]
    time_dimension = "time" if "time" in ids else ids[-1]
    if ids[-1] != time_dimension:
        raise RuntimeError(
            "Eurostat bulk loader requires the time dimension to be last"
        )
    dimension_meta = {dim_id: _dimension_codes(dimension, dim_id) for dim_id in ids}
    dataset_code = _dataset_code(source_url)
    dataset_label = normalize_ws(str(row.get("label") or dataset_code)) or dataset_code
    metadata_version = _metadata_version(row)
    time_size = sizes[-1]
    cube_cells = 1
    for size in sizes:
        if int(size) < 1:
            raise RuntimeError(f"Eurostat dimension size must be positive: {size}")
        cube_cells *= int(size)
    if maximum_cube_cells is not None and cube_cells > int(maximum_cube_cells):
        raise RuntimeError(
            "Eurostat cube-cell ceiling exceeded: "
            f"cells={cube_cells} maximum={maximum_cube_cells}"
        )
    previous_series_index: int | None = None
    current: dict[str, Any] | None = None

    for flat_index, raw_value in _value_items(row.get("value"), cube_cells=cube_cells):
        series_index = flat_index // time_size
        time_index = flat_index % time_size
        if series_index != previous_series_index:
            if current is not None:
                current["points_count"] = len(current["points"])
                current["source_record_id"] = build_source_record_id(current)
                yield current
            remainder = series_index
            coordinates = [0] * (len(sizes) - 1)
            for position in range(len(sizes) - 2, -1, -1):
                size = sizes[position]
                coordinates[position] = remainder % size
                remainder //= size
            series_dimensions: dict[str, str] = {}
            series_dimension_labels: dict[str, str] = {}
            label_parts: list[str] = []
            for position, dim_id in enumerate(ids[:-1]):
                codes, labels, _ = dimension_meta[dim_id]
                code = codes[coordinates[position]]
                label = labels.get(code) or code
                series_dimensions[dim_id] = code
                series_dimension_labels[dim_id] = label
                if dim_id not in {"freq", "unit"}:
                    label_parts.append(label)
            series_code = (
                dataset_code
                + "|"
                + "|".join(
                    f"{key}={series_dimensions[key]}"
                    for key in sorted(series_dimensions)
                )
            )
            current = {
                "record_kind": "eurostat_series",
                "source_feed": "eurostat_jsonstat_bulk",
                "feed_url": source_url,
                "source_url": source_url,
                "dataset_code": dataset_code,
                "dataset_label": dataset_label,
                "series_code": series_code,
                "series_label": f"{dataset_label}: {', '.join(label_parts)}",
                "frequency": series_dimensions.get("freq"),
                "unit": series_dimensions.get("unit"),
                "series_dimensions": dict(sorted(series_dimensions.items())),
                "series_dimension_labels": dict(
                    sorted(series_dimension_labels.items())
                ),
                "time_dimension": time_dimension,
                "metadata_version": metadata_version,
                "domain_key": normalize_ws(domain_key or "") or None,
                "points": [],
            }
            previous_series_index = series_index
        if current is None:
            continue
        time_codes, time_labels, _ = dimension_meta[time_dimension]
        period = time_codes[time_index]
        try:
            value = float(raw_value)
            value_text = None
        except (TypeError, ValueError):
            value = None
            value_text = normalize_ws(str(raw_value)) or None
        current["points"].append(
            {
                "period": period,
                "period_label": time_labels.get(period) or period,
                "value": value,
                "value_text": value_text,
            }
        )

    if current is not None:
        current["points_count"] = len(current["points"])
        current["source_record_id"] = build_source_record_id(current)
        yield current


def load_eurostat_source_records(
    conn: sqlite3.Connection,
    *,
    blob_path: Path,
    source_url: str,
    snapshot_date: str,
    raw_content_sha256: str,
    acquisition_id: int,
    domain_key: str | None,
    maximum_cube_cells: int | None = None,
    batch_size: int = 1_000,
    progress_callback: Callable[[], None] | None = None,
) -> dict[str, int]:
    if int(batch_size) < 1:
        raise ValueError("batch_size must be >= 1")
    conn.execute(
        "DELETE FROM indicator_bulk_acquisition_records WHERE indicator_bulk_acquisition_id = ?",
        (int(acquisition_id),),
    )
    conn.commit()
    now_iso = now_utc_iso()
    batch: list[dict[str, Any]] = []
    batch_points: dict[str, int] = {}
    series_total = 0
    observations_total = 0

    def flush() -> None:
        nonlocal batch, batch_points
        if not batch:
            return
        source_record_pks = upsert_source_records_with_content_sha256(
            conn,
            source_id=SOURCE_ID,
            rows=batch,
            snapshot_date=snapshot_date,
            now_iso=now_iso,
        )
        conn.executemany(
            """
            INSERT INTO indicator_bulk_acquisition_records (
              indicator_bulk_acquisition_id,
              source_record_pk,
              observations_discovered,
              record_sha256
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(indicator_bulk_acquisition_id, source_record_pk) DO UPDATE SET
              observations_discovered=excluded.observations_discovered,
              record_sha256=excluded.record_sha256
            """,
            [
                (
                    int(acquisition_id),
                    int(source_record_pks[str(row["source_record_id"])]),
                    int(batch_points[str(row["source_record_id"])]),
                    str(row["content_sha256"]),
                )
                for row in batch
            ],
        )
        conn.commit()
        if progress_callback is not None:
            progress_callback()
        batch = []
        batch_points = {}

    for record in iter_eurostat_jsonstat_series(
        blob_path,
        source_url=source_url,
        domain_key=domain_key,
        maximum_cube_cells=maximum_cube_cells,
    ):
        semantic_payload = stable_json(record)
        record_sha256 = sha256_bytes(semantic_payload.encode("utf-8"))
        base_record_id = str(record["source_record_id"])
        versioned_record_id = f"{base_record_id}:v:{record_sha256[:24]}"
        stored_record = {
            **record,
            "source_record_id": versioned_record_id,
            "series_version_sha256": record_sha256,
            "origin_capture_sha256": raw_content_sha256,
        }
        raw_payload = stable_json(stored_record)
        points_count = int(record["points_count"])
        batch.append(
            {
                "source_record_id": versioned_record_id,
                "raw_payload": raw_payload,
                "content_sha256": record_sha256,
            }
        )
        batch_points[versioned_record_id] = points_count
        series_total += 1
        observations_total += points_count
        if len(batch) >= int(batch_size):
            flush()
    flush()
    return {
        "series_loaded": series_total,
        "observations_discovered": observations_total,
    }
