from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from typing import Any

from .util import normalize_key_part, normalize_ws, now_utc_iso, parse_date_flexible, sha256_bytes, stable_json
from .policy_events import _domain_id_by_canonical_key, _infer_policy_event_domain_key


INDICATOR_SOURCE_IDS = ("eurostat_sdmx", "bde_series_api", "aemet_opendata_series")

_YEAR_RE = re.compile(r"^(\d{4})$")
_YEAR_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR_MONTH_ALT_RE = re.compile(r"^(\d{4})M(\d{1,2})$", flags=re.I)
_YEAR_QUARTER_RE = re.compile(r"^(\d{4})-?Q([1-4])$", flags=re.I)
_YEAR_WEEK_RE = re.compile(r"^(\d{4})W(\d{1,2})$", flags=re.I)


def _normalize_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    token = normalize_ws(str(value)).replace(" ", "")
    if not token:
        return None
    token = token.replace("EUR", "").replace("eur", "").replace("€", "")
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


def _normalize_iso_date(value: Any) -> str | None:
    if value is None:
        return None
    text = normalize_ws(str(value))
    if not text:
        return None
    parsed = parse_date_flexible(text)
    if parsed:
        return parsed
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def _period_to_date(period: Any, frequency: str | None) -> str | None:
    text = normalize_ws(str(period or ""))
    if not text:
        return None
    freq = normalize_key_part(frequency or "")

    direct = parse_date_flexible(text)
    if direct:
        return direct

    match = _YEAR_MONTH_RE.match(text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}-01"

    match = _YEAR_MONTH_ALT_RE.match(text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}-01"

    match = _YEAR_QUARTER_RE.match(text)
    if match:
        year = int(match.group(1))
        quarter = int(match.group(2))
        month = (quarter - 1) * 3 + 1
        return f"{year:04d}-{month:02d}-01"

    match = _YEAR_WEEK_RE.match(text)
    if match:
        year = int(match.group(1))
        week = int(match.group(2))
        if 1 <= week <= 53:
            try:
                date = dt.date.fromisocalendar(year, week, 1)
            except ValueError:
                return None
            return date.isoformat()

    match = _YEAR_RE.match(text)
    if match:
        if not freq or freq in {"a", "anual", "annual", "yearly", "year"}:
            return f"{int(match.group(1)):04d}-01-01"
        return f"{int(match.group(1)):04d}-01-01"

    return None


def _series_version_token(metadata_version: str | None, snapshot_date: str | None) -> str:
    metadata = normalize_ws(str(metadata_version or ""))
    if metadata:
        return f"meta-{sha256_bytes(metadata.encode('utf-8'))[:16]}"
    snapshot = _normalize_iso_date(snapshot_date)
    if snapshot:
        return f"snap-{snapshot}"
    return "v0"


def _series_methodology_version(metadata_version: str | None, snapshot_date: str | None) -> str:
    metadata = normalize_ws(str(metadata_version or ""))
    if metadata:
        return metadata
    snapshot = _normalize_iso_date(snapshot_date)
    if snapshot:
        return f"snapshot:{snapshot}"
    return "snapshot:unknown"


def _infer_indicator_series_domain_key(
    *,
    source_id: str,
    series_label: str,
    series_code: str,
    dataset_code: str,
    raw_payload: dict[str, Any],
) -> str | None:
    explicit_key = normalize_ws(
        str(
            raw_payload.get("domain_key")
            or raw_payload.get("domain_canonical_key")
            or raw_payload.get("policy_domain_key")
            or ""
        )
    )
    if explicit_key:
        return explicit_key

    if source_id == "eurostat_sdmx":
        dataset_key = normalize_ws(str(dataset_code or "")).lower()
        if dataset_key == "une_rt_a":
            return "proteccion_social_pensiones"

    return _infer_policy_event_domain_key(
        source_id=source_id,
        title=series_label,
        summary=f"{series_code} {dataset_code}".strip(),
        source_url=None,
        raw_payload=raw_payload,
    )


def _series_canonical_key(
    *,
    source_id: str,
    series_code: str,
    frequency: str | None,
    unit: str | None,
    version_token: str,
) -> str:
    frequency_token = normalize_key_part(frequency or "").replace(" ", "_") or "na"
    unit_token = normalize_key_part(unit or "").replace(" ", "_") or "na"
    series_token = normalize_ws(series_code)
    if not series_token:
        series_token = f"series-{sha256_bytes(stable_json({'source_id': source_id}).encode('utf-8'))[:24]}"
    return (
        f"indicator|source={source_id}|series={series_token}|freq={frequency_token}|"
        f"unit={unit_token}|ver={version_token}"
    )


def _extract_source_url(payload: dict[str, Any]) -> str | None:
    for key in ("source_url", "feed_url"):
        value = payload.get(key)
        if value is None:
            continue
        text = normalize_ws(str(value))
        if text:
            return text
    return None


def _delete_stale_indicator_points(
    conn: sqlite3.Connection,
    *,
    indicator_series_id: int,
    keep_dates: list[str],
) -> int:
    if not keep_dates:
        cur = conn.execute("DELETE FROM indicator_points WHERE indicator_series_id = ?", (indicator_series_id,))
        return max(int(cur.rowcount or 0), 0)
    placeholders = ",".join("?" for _ in keep_dates)
    cur = conn.execute(
        f"""
        DELETE FROM indicator_points
        WHERE indicator_series_id = ?
          AND date NOT IN ({placeholders})
        """,
        (indicator_series_id, *keep_dates),
    )
    return max(int(cur.rowcount or 0), 0)


def _delete_stale_observation_records(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    source_record_id: str,
    series_code: str,
    keep_dates: list[str],
) -> int:
    if not keep_dates:
        cur = conn.execute(
            """
            DELETE FROM indicator_observation_records
            WHERE source_id = ?
              AND source_record_id = ?
              AND series_code = ?
            """,
            (source_id, source_record_id, series_code),
        )
        return max(int(cur.rowcount or 0), 0)
    placeholders = ",".join("?" for _ in keep_dates)
    cur = conn.execute(
        f"""
        DELETE FROM indicator_observation_records
        WHERE source_id = ?
          AND source_record_id = ?
          AND series_code = ?
          AND point_date NOT IN ({placeholders})
        """,
        (source_id, source_record_id, series_code, *keep_dates),
    )
    return max(int(cur.rowcount or 0), 0)


def backfill_indicator_harmonization(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] = INDICATOR_SOURCE_IDS,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    stats: dict[str, Any] = {
        "sources": list(source_ids),
        "source_records_seen": 0,
        "source_records_mapped": 0,
        "source_records_skipped": 0,
        "indicator_series_upserted": 0,
        "indicator_series_with_domain_id": 0,
        "indicator_series_unresolved_domain": 0,
        "indicator_points_upserted": 0,
        "indicator_points_deleted_stale": 0,
        "observation_records_upserted": 0,
        "observation_records_deleted_stale": 0,
        "points_skipped_unparseable_date": 0,
        "skips": [],
    }
    domain_cache: dict[str, int | None] = {}

    placeholders = ",".join("?" for _ in source_ids)
    rows = conn.execute(
        f"""
        SELECT
          sr.source_record_pk,
          sr.source_id,
          sr.source_record_id,
          sr.source_snapshot_date,
          sr.raw_payload
        FROM source_records sr
        WHERE sr.source_id IN ({placeholders})
        ORDER BY sr.source_id, sr.source_record_id
        """,
        source_ids,
    ).fetchall()

    for row in rows:
        stats["source_records_seen"] += 1
        source_record_pk = int(row["source_record_pk"])
        source_id = str(row["source_id"])
        source_record_id = normalize_ws(str(row["source_record_id"] or "")) or f"pk:{source_record_pk}"
        source_snapshot_date = _normalize_iso_date(row["source_snapshot_date"])
        raw_payload = str(row["raw_payload"] or "")

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "invalid_json_payload",
                }
            )
            continue
        if not isinstance(payload, dict):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "payload_not_object",
                }
            )
            continue

        series_code = normalize_ws(str(payload.get("series_code") or ""))
        if not series_code:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "missing_series_code",
                }
            )
            continue

        points_obj = payload.get("points")
        if not isinstance(points_obj, list):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "missing_points_array",
                }
            )
            continue

        frequency = normalize_ws(str(payload.get("frequency") or "")) or None
        unit = normalize_ws(str(payload.get("unit") or "")) or None
        metadata_version = normalize_ws(str(payload.get("metadata_version") or "")) or None
        methodology_version = _series_methodology_version(metadata_version, source_snapshot_date)
        version_token = _series_version_token(metadata_version, source_snapshot_date)
        source_url = _extract_source_url(payload)
        series_label = normalize_ws(str(payload.get("series_label") or payload.get("series_code") or ""))
        if not series_label:
            dataset_code = normalize_ws(str(payload.get("dataset_code") or ""))
            series_label = f"{dataset_code} {series_code}".strip() or series_code

        canonical_key = _series_canonical_key(
            source_id=source_id,
            series_code=series_code,
            frequency=frequency,
            unit=unit,
            version_token=version_token,
        )

        point_map: dict[str, dict[str, Any]] = {}
        for point in sorted(points_obj, key=lambda item: str((item or {}).get("period") or "")):
            if not isinstance(point, dict):
                continue
            point_date = _period_to_date(point.get("period"), frequency)
            if not point_date:
                stats["points_skipped_unparseable_date"] += 1
                continue
            numeric_value = _normalize_amount(point.get("value"))
            value_text_raw = normalize_ws(str(point.get("value_text") or ""))
            value_text = value_text_raw or None
            if numeric_value is not None:
                value_text = None
            elif value_text is None and point.get("value") is not None:
                fallback_text = normalize_ws(str(point.get("value")))
                value_text = fallback_text or None

            point_map[point_date] = {
                "date": point_date,
                "value": numeric_value,
                "value_text": value_text,
                "raw_point": dict(point),
            }

        point_dates = sorted(point_map.keys())
        if not point_dates:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "no_parseable_points",
                }
            )
            continue

        dataset_code = normalize_ws(str(payload.get("dataset_code") or ""))
        domain_key = _infer_indicator_series_domain_key(
            source_id=source_id,
            series_label=series_label,
            series_code=series_code,
            dataset_code=dataset_code,
            raw_payload=payload,
        )
        domain_id = _domain_id_by_canonical_key(conn, domain_cache, domain_key)
        if domain_id is None:
            stats["indicator_series_unresolved_domain"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "unresolved_domain",
                    "domain_key": domain_key,
                }
            )
        else:
            stats["indicator_series_with_domain_id"] += 1

        series_row = conn.execute(
            """
            INSERT INTO indicator_series (
              canonical_key,
              label,
              unit,
              frequency,
              domain_id,
              admin_level_id,
              territory_id,
              source_id,
              source_url,
              source_record_pk,
              source_snapshot_date,
              raw_payload,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(canonical_key) DO UPDATE SET
              domain_id=excluded.domain_id,
              label=excluded.label,
              unit=excluded.unit,
              frequency=excluded.frequency,
              source_id=excluded.source_id,
              source_url=excluded.source_url,
              source_record_pk=excluded.source_record_pk,
              source_snapshot_date=excluded.source_snapshot_date,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            RETURNING indicator_series_id
            """,
            (
                canonical_key,
                series_label,
                unit,
                frequency,
                domain_id,
                source_id,
                source_url,
                source_record_pk,
                source_snapshot_date,
                raw_payload,
                now_iso,
                now_iso,
            ),
        ).fetchone()
        if series_row is None:
            raise RuntimeError(f"No se pudo resolver indicator_series_id ({source_id}:{source_record_id})")
        indicator_series_id = int(series_row["indicator_series_id"])
        stats["indicator_series_upserted"] += 1

        dimensions_payload = {
            "dataset_code": payload.get("dataset_code"),
            "series_dimensions": payload.get("series_dimensions"),
            "series_dimension_labels": payload.get("series_dimension_labels"),
            "time_dimension": payload.get("time_dimension"),
            "metadata_version": metadata_version,
        }
        dimensions_json = stable_json(dimensions_payload)

        for point_date in point_dates:
            parsed_point = point_map[point_date]
            conn.execute(
                """
                INSERT INTO indicator_points (
                  indicator_series_id,
                  date,
                  value,
                  value_text,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(indicator_series_id, date) DO UPDATE SET
                  value=excluded.value,
                  value_text=excluded.value_text,
                  updated_at=excluded.updated_at
                """,
                (
                    indicator_series_id,
                    parsed_point["date"],
                    parsed_point["value"],
                    parsed_point["value_text"],
                    now_iso,
                    now_iso,
                ),
            )
            stats["indicator_points_upserted"] += 1

            observation_payload = stable_json(
                {
                    "source_record_id": source_record_id,
                    "series_code": series_code,
                    "point": parsed_point["raw_point"],
                    "series_dimensions": payload.get("series_dimensions"),
                    "dataset_code": payload.get("dataset_code"),
                }
            )
            conn.execute(
                """
                INSERT INTO indicator_observation_records (
                  source_id,
                  source_record_pk,
                  source_record_id,
                  source_snapshot_date,
                  source_url,
                  series_code,
                  point_date,
                  value,
                  value_text,
                  unit,
                  frequency,
                  dimensions_json,
                  methodology_version,
                  raw_payload,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, series_code, point_date, source_record_id) DO UPDATE SET
                  source_record_pk=excluded.source_record_pk,
                  source_snapshot_date=excluded.source_snapshot_date,
                  source_url=excluded.source_url,
                  value=excluded.value,
                  value_text=excluded.value_text,
                  unit=excluded.unit,
                  frequency=excluded.frequency,
                  dimensions_json=excluded.dimensions_json,
                  methodology_version=excluded.methodology_version,
                  raw_payload=excluded.raw_payload,
                  updated_at=excluded.updated_at
                """,
                (
                    source_id,
                    source_record_pk,
                    source_record_id,
                    source_snapshot_date,
                    source_url,
                    series_code,
                    parsed_point["date"],
                    parsed_point["value"],
                    parsed_point["value_text"],
                    unit,
                    frequency,
                    dimensions_json,
                    methodology_version,
                    observation_payload,
                    now_iso,
                    now_iso,
                ),
            )
            stats["observation_records_upserted"] += 1

        stats["indicator_points_deleted_stale"] += _delete_stale_indicator_points(
            conn,
            indicator_series_id=indicator_series_id,
            keep_dates=point_dates,
        )
        stats["observation_records_deleted_stale"] += _delete_stale_observation_records(
            conn,
            source_id=source_id,
            source_record_id=source_record_id,
            series_code=series_code,
            keep_dates=point_dates,
        )

        stats["source_records_mapped"] += 1

    conn.commit()

    total_series_row = conn.execute(
        f"SELECT COUNT(*) AS c FROM indicator_series WHERE source_id IN ({placeholders})",
        source_ids,
    ).fetchone()
    total_points_row = conn.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM indicator_points ip
        JOIN indicator_series s ON s.indicator_series_id = ip.indicator_series_id
        WHERE s.source_id IN ({placeholders})
        """,
        source_ids,
    ).fetchone()
    total_observation_row = conn.execute(
        f"SELECT COUNT(*) AS c FROM indicator_observation_records WHERE source_id IN ({placeholders})",
        source_ids,
    ).fetchone()
    by_source_series_rows = conn.execute(
        f"""
        SELECT source_id, COUNT(*) AS c
        FROM indicator_series
        WHERE source_id IN ({placeholders})
        GROUP BY source_id
        ORDER BY source_id
        """,
        source_ids,
    ).fetchall()
    by_source_point_rows = conn.execute(
        f"""
        SELECT s.source_id, COUNT(*) AS c
        FROM indicator_points ip
        JOIN indicator_series s ON s.indicator_series_id = ip.indicator_series_id
        WHERE s.source_id IN ({placeholders})
        GROUP BY s.source_id
        ORDER BY s.source_id
        """,
        source_ids,
    ).fetchall()
    by_source_observation_rows = conn.execute(
        f"""
        SELECT source_id, COUNT(*) AS c
        FROM indicator_observation_records
        WHERE source_id IN ({placeholders})
        GROUP BY source_id
        ORDER BY source_id
        """,
        source_ids,
    ).fetchall()
    with_provenance_series_row = conn.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM indicator_series
        WHERE source_id IN ({placeholders})
          AND source_record_pk IS NOT NULL
          AND source_snapshot_date IS NOT NULL
          AND trim(source_snapshot_date) <> ''
          AND source_url IS NOT NULL
          AND trim(source_url) <> ''
        """,
        source_ids,
    ).fetchone()
    with_provenance_observation_row = conn.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM indicator_observation_records
        WHERE source_id IN ({placeholders})
          AND source_record_id IS NOT NULL
          AND trim(source_record_id) <> ''
          AND source_snapshot_date IS NOT NULL
          AND trim(source_snapshot_date) <> ''
          AND source_url IS NOT NULL
          AND trim(source_url) <> ''
          AND methodology_version IS NOT NULL
          AND trim(methodology_version) <> ''
        """,
        source_ids,
    ).fetchone()

    stats["indicator_series_total"] = int(total_series_row["c"] if total_series_row else 0)
    stats["indicator_points_total"] = int(total_points_row["c"] if total_points_row else 0)
    stats["indicator_observation_records_total"] = int(total_observation_row["c"] if total_observation_row else 0)
    stats["indicator_series_with_provenance"] = int(with_provenance_series_row["c"] if with_provenance_series_row else 0)
    stats["observation_records_with_provenance"] = int(
        with_provenance_observation_row["c"] if with_provenance_observation_row else 0
    )
    stats["indicator_series_by_source"] = {str(r["source_id"]): int(r["c"]) for r in by_source_series_rows}
    stats["indicator_points_by_source"] = {str(r["source_id"]): int(r["c"]) for r in by_source_point_rows}
    stats["observation_records_by_source"] = {str(r["source_id"]): int(r["c"]) for r in by_source_observation_rows}
    return stats
