#!/usr/bin/env python3
"""Exporta un snapshot estático de seguimiento de resultados / indicadores.

Estado actual: fase temprana de resultados.
- `interventions`, `intervention_events` y `causal_estimates` suelen estar vacías.
- Se prioriza un reporte descriptivo con señales de co-movimiento entre
  eventos de política e indicadores cercanos temporalmente.

Objetivo:
- Mantener evidencia explícita de limitaciones metodológicas.
- Entregar un artefacto acotado para GH Pages con agregados por indicador,
  eventos y posibles asociaciones descriptivas.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT = Path("docs/gh-pages/policy-outcomes/data/policy-outcomes.json")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporta snapshot para página de resultados e indicadores (fase temprana)."
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Ruta a la base SQLite")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Ruta de salida JSON")
    parser.add_argument("--snapshot-date", default="", help="Snapshot date YYYY-MM-DD para metadata.")
    parser.add_argument(
        "--max-series",
        type=int,
        default=120,
        help="Máximo de series de indicadores a incluir (ordenadas por cobertura)",
    )
    parser.add_argument(
        "--min-points",
        type=int,
        default=2,
        help="Mínimo de puntos válidos para incluir una serie.",
    )
    parser.add_argument(
        "--max-points-per-series",
        type=int,
        default=36,
        help="Máximo de puntos históricos exportados por serie (más recientes)",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=500,
        help="Máximo de eventos de política a incluir para análisis descriptivo",
    )
    parser.add_argument(
        "--max-associations-per-series",
        type=int,
        default=6,
        help="Máximo vínculos descriptivos por serie.",
    )
    parser.add_argument(
        "--max-associations",
        type=int,
        default=500,
        help="Máximo de vínculos descriptivos en el output global.",
    )
    parser.add_argument(
        "--pre-window-days",
        type=int,
        default=120,
        help="Máximo de días antes del evento para buscar punto previo.",
    )
    parser.add_argument(
        "--post-window-days",
        type=int,
        default=120,
        help="Máximo de días después del evento para buscar punto posterior.",
    )
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = safe_text(value)
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_date(value: Any) -> date | None:
    text = safe_text(value)
    if not text:
        return None
    if DATE_RE.match(text):
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def date_key(value: Any) -> int:
    parsed = parse_date(value)
    if parsed is None:
        return 0
    return int(parsed.strftime("%Y%m%d"))


def format_date(value: date | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def build_short_text(text: str, max_chars: int = 130) -> str:
    stripped = safe_text(text)
    if len(stripped) <= max_chars:
        return stripped
    return f"{stripped[: max_chars - 3].rstrip()}..."


def as_percent(delta: float | None, base: float | None) -> float | None:
    if delta is None or base is None or base == 0:
        return None
    return delta / base * 100.0


def infer_snapshot_date(conn: sqlite3.Connection) -> str:
    candidates = [
        conn.execute(
            """
            SELECT MAX(source_snapshot_date) AS d
            FROM indicator_series
            WHERE source_snapshot_date IS NOT NULL
            """
        ).fetchone(),
        conn.execute(
            """
            SELECT MAX(source_snapshot_date) AS d
            FROM indicator_points ip
            JOIN indicator_series s ON s.indicator_series_id = ip.indicator_series_id
            WHERE s.source_snapshot_date IS NOT NULL
            """
        ).fetchone(),
        conn.execute(
            """
            SELECT MAX(COALESCE(event_date, published_date)) AS d
            FROM policy_events
            """
        ).fetchone(),
        conn.execute(
            """
            SELECT MAX(source_snapshot_date) AS d
            FROM policy_events
            WHERE source_snapshot_date IS NOT NULL
            """
        ).fetchone(),
    ]

    snapshot = ""
    for row in candidates:
        value = safe_text(row["d"] if row else "")
        if value:
            if DATE_RE.match(value):
                if not snapshot or value > snapshot:
                    snapshot = value
    if snapshot:
        return snapshot
    return now_utc_iso()[:10]


def load_series(conn: sqlite3.Connection, *, max_series: int, min_points: int) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    rows = conn.execute(
        """
        SELECT
          s.indicator_series_id,
          s.canonical_key,
          s.label,
          COALESCE(s.unit, '') AS unit,
          COALESCE(s.frequency, '') AS frequency,
          s.domain_id,
          s.admin_level_id,
          s.territory_id,
          COALESCE(s.source_id, '') AS source_id,
          COALESCE(s.source_url, '') AS source_url,
          COALESCE(s.source_snapshot_date, '') AS source_snapshot_date,
          COALESCE(d.label, '') AS domain_label,
          COALESCE(d.canonical_key, '') AS domain_key,
          COALESCE(a.label, '') AS admin_level_label,
          COALESCE(t.name, COALESCE(t.code, '')) AS territory_label,
          COALESCE(t.code, '') AS territory_code,
          COUNT(p.indicator_point_id) AS point_count,
          MIN(p.date) AS first_point_date,
          MAX(p.date) AS latest_point_date
        FROM indicator_series s
        LEFT JOIN indicator_points p ON p.indicator_series_id = s.indicator_series_id
        LEFT JOIN domains d ON d.domain_id = s.domain_id
        LEFT JOIN admin_levels a ON a.admin_level_id = s.admin_level_id
        LEFT JOIN territories t ON t.territory_id = s.territory_id
        GROUP BY
          s.indicator_series_id, s.canonical_key, s.label, s.unit, s.frequency, s.domain_id,
          s.admin_level_id, s.territory_id, s.source_id, s.source_url, s.source_snapshot_date,
          d.label, d.canonical_key, a.label, t.name, t.code
        HAVING point_count >= ?
        ORDER BY point_count DESC, latest_point_date DESC
        LIMIT ?
        """,
        (min_points, int(max_series)),
    ).fetchall()

    series = []
    ids = []
    for row in rows:
        sid = int(row["indicator_series_id"])
        ids.append(sid)
        series.append(
            {
                "indicator_series_id": sid,
                "canonical_key": safe_text(row["canonical_key"]),
                "label": safe_text(row["label"]),
                "unit": safe_text(row["unit"]),
                "frequency": safe_text(row["frequency"]),
                "domain_id": int(row["domain_id"] or 0),
                "domain_label": safe_text(row["domain_label"]),
                "domain_key": safe_text(row["domain_key"]),
                "admin_level_id": int(row["admin_level_id"] or 0),
                "admin_level_label": safe_text(row["admin_level_label"]),
                "territory_id": int(row["territory_id"] or 0),
                "territory_label": safe_text(row["territory_label"]),
                "territory_code": safe_text(row["territory_code"]),
                "source_id": safe_text(row["source_id"]),
                "source_url": safe_text(row["source_url"]),
                "source_snapshot_date": safe_text(row["source_snapshot_date"]),
                "point_count": int(row["point_count"]),
                "first_point_date": safe_text(row["first_point_date"]),
                "latest_point_date": safe_text(row["latest_point_date"]),
                "points": [],
            }
        )

    if not ids:
        return series, {}

    placeholders = ",".join("?" for _ in ids)
    point_rows = conn.execute(
        f"""
        SELECT
          indicator_series_id,
          date,
          value,
          COALESCE(value_text, '') AS value_text
        FROM indicator_points
        WHERE indicator_series_id IN ({placeholders})
        ORDER BY indicator_series_id ASC, date ASC
        """,
        ids,
    ).fetchall()

    points_by_series: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in point_rows:
        sid = int(row["indicator_series_id"])
        row_value = safe_float(row["value"])
        parsed_date = parse_date(row["date"])
        points_by_series[sid].append(
            {
                "date": safe_text(row["date"]),
                "date_ord": int(parsed_date.strftime("%Y%m%d")) if parsed_date else date_key(row["date"]),
                "value": row_value,
                "value_text": safe_text(row["value_text"]),
            }
        )

    return series, points_by_series


def enrich_series(series: list[dict[str, Any]], points_by_series: dict[int, list[dict[str, Any]]], *, max_points_per_series: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    series_payload = []
    for row in series:
        sid = int(row["indicator_series_id"])
        all_points = points_by_series.get(sid, [])
        if not all_points:
            continue

        latest = all_points[-1]
        latest_numeric = latest.get("value")
        prev_numeric = None
        prev_point = None
        for candidate in reversed(all_points[:-1]):
            if candidate.get("value") is not None:
                prev_point = candidate
                prev_numeric = candidate.get("value")
                break
        delta = None
        delta_pct = None
        if prev_numeric is not None and latest_numeric is not None:
            delta = latest_numeric - prev_numeric
            delta_pct = as_percent(delta, prev_numeric)

        row.update(
            {
                "latest_value": latest.get("value"),
                "latest_value_text": latest.get("value_text"),
                "latest_date": latest.get("date"),
                "previous_date": prev_point.get("date") if prev_point else "",
                "previous_value": prev_point.get("value") if prev_point else None,
                "latest_delta": delta,
                "latest_delta_pct": delta_pct,
                "points": all_points[-max_points_per_series:],
            }
        )
        series_payload.append(row)

    source_counts: Counter[str] = Counter()
    for item in series_payload:
        source_counts[item["source_id"]] += 1

    return series_payload, {"unique_series": len(series_payload), "by_source": dict(sorted(source_counts.items()))}


def load_policy_events(conn: sqlite3.Connection, *, max_events: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          pe.policy_event_id,
          COALESCE(pe.event_date, pe.published_date, '') AS event_date,
          COALESCE(pe.published_date, '') AS published_date,
          COALESCE(pe.title, '') AS title,
          COALESCE(pe.summary, '') AS summary,
          COALESCE(pe.scope, '') AS scope,
          COALESCE(pe.source_id, '') AS source_id,
          COALESCE(pe.source_url, '') AS source_url,
          COALESCE(pe.domain_id, 0) AS domain_id,
          COALESCE(d.label, '') AS domain_label,
          COALESCE(d.canonical_key, '') AS domain_key,
          COALESCE(i.name, '') AS institution_name,
          COALESCE(a.label, '') AS admin_level_label,
          COALESCE(t.name, COALESCE(t.code, '')) AS territory_label,
          COALESCE(t.code, '') AS territory_code
        FROM policy_events pe
        LEFT JOIN domains d ON d.domain_id = pe.domain_id
        LEFT JOIN institutions i ON i.institution_id = pe.institution_id
        LEFT JOIN admin_levels a ON a.admin_level_id = pe.admin_level_id
        LEFT JOIN territories t ON t.territory_id = pe.territory_id
        ORDER BY date(COALESCE(pe.event_date, pe.published_date)) DESC
        LIMIT ?
        """,
        (int(max_events),),
    ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        raw_date = safe_text(row["event_date"] or row["published_date"])
        out.append(
            {
                "policy_event_id": safe_text(row["policy_event_id"]),
                "event_date": raw_date,
                "event_date_ord": date_key(raw_date),
                "published_date": safe_text(row["published_date"]),
                "title": safe_text(row["title"]),
                "summary": build_short_text(safe_text(row["summary"]), 220),
                "scope": safe_text(row["scope"]),
                "source_id": safe_text(row["source_id"]),
                "source_url": safe_text(row["source_url"]),
                "domain_id": int(row["domain_id"] or 0),
                "domain_label": safe_text(row["domain_label"]),
                "domain_key": safe_text(row["domain_key"]),
                "institution_name": safe_text(row["institution_name"]),
                "admin_level_label": safe_text(row["admin_level_label"]),
                "territory_label": safe_text(row["territory_label"]),
                "territory_code": safe_text(row["territory_code"]),
            }
        )
    return out


def point_value_delta(
    points: list[dict[str, Any]],
    *,
    event_ord: int,
    pre_window_days: int,
    post_window_days: int,
) -> dict[str, Any] | None:
    if len(points) < 2:
        return None

    dates = [point.get("date_ord", 0) for point in points]
    idx = bisect_left(dates, event_ord)
    pre_idx = idx - 1
    post_idx = idx
    if pre_idx < 0 or post_idx >= len(points):
        return None

    pre = points[pre_idx]
    post = points[post_idx]
    pre_value = pre.get("value")
    post_value = post.get("value")
    if pre_value is None or post_value is None:
        return None

    pre_date_ord = pre.get("date_ord", 0)
    post_date_ord = post.get("date_ord", 0)
    pre_gap = event_ord - pre_date_ord
    post_gap = post_date_ord - event_ord
    if pre_gap < 0 or post_gap < 0:
        return None
    if pre_gap > pre_window_days or post_gap > post_window_days:
        return None

    delta = post_value - pre_value
    delta_pct = as_percent(delta, pre_value)

    return {
        "pre_point_date": pre.get("date", ""),
        "pre_value": pre_value,
        "post_point_date": post.get("date", ""),
        "post_value": post_value,
        "delta": delta,
        "delta_pct": delta_pct,
        "pre_gap_days": pre_gap,
        "post_gap_days": post_gap,
    }


def build_associations(
    series_payload: list[dict[str, Any]],
    policy_events: list[dict[str, Any]],
    *,
    pre_window_days: int,
    post_window_days: int,
    max_associations_per_series: int,
    max_associations: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    associations: list[dict[str, Any]] = []
    for series in series_payload:
        points = series.get("points") or []
        if len(points) < 2:
            continue
        candidates: list[dict[str, Any]] = []
        for event in policy_events:
            if series["domain_id"] and event["domain_id"] and int(series["domain_id"]) != int(event["domain_id"]):
                continue
            event_ord = int(event["event_date_ord"] or 0)
            if not event_ord:
                continue
            delta_data = point_value_delta(
                points,
                event_ord=event_ord,
                pre_window_days=pre_window_days,
                post_window_days=post_window_days,
            )
            if not delta_data:
                continue

            candidates.append(
                {
                    **delta_data,
                    "policy_event_id": event["policy_event_id"],
                    "policy_event_title": build_short_text(event["title"] or event["summary"], 120),
                    "policy_event_date": event["event_date"],
                    "policy_event_source_id": event["source_id"],
                    "policy_event_source_url": event["source_url"],
                    "policy_event_domain_label": event["domain_label"],
                    "policy_event_domain_key": event["domain_key"],
                    "indicator_series_id": series["indicator_series_id"],
                    "indicator_series_label": series["label"],
                    "indicator_series_canonical_key": series["canonical_key"],
                    "indicator_unit": series["unit"],
                    "indicator_source_id": series["source_id"],
                    "indicator_domain_label": series["domain_label"],
                }
            )
        candidates.sort(key=lambda item: abs(float(item["delta"] or 0)), reverse=True)
        associations.extend(candidates[:max(0, int(max_associations_per_series))])

    associations.sort(key=lambda item: abs(float(item["delta"] or 0)), reverse=True)
    associations = associations[: int(max_associations)]

    event_link_counter: Counter[str] = Counter()
    for item in associations:
        event_link_counter[item["policy_event_id"]] += 1

    return associations, {
        "pairs_total": len(associations),
        "linked_series": len({item["indicator_series_id"] for item in associations}),
        "linked_events": len(event_link_counter),
    }


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT COUNT(*) AS c FROM indicator_series").fetchone()
    indicator_series_total = int(rows["c"]) if rows else 0
    rows = conn.execute("SELECT COUNT(*) AS c FROM indicator_points").fetchone()
    indicator_points_total = int(rows["c"]) if rows else 0
    rows = conn.execute("SELECT COUNT(*) AS c FROM interventions").fetchone()
    interventions_total = int(rows["c"]) if rows else 0
    rows = conn.execute("SELECT COUNT(*) AS c FROM intervention_events").fetchone()
    intervention_events_total = int(rows["c"]) if rows else 0
    rows = conn.execute("SELECT COUNT(*) AS c FROM causal_estimates").fetchone()
    causal_estimates_total = int(rows["c"]) if rows else 0
    rows = conn.execute("SELECT COUNT(*) AS c FROM policy_events").fetchone()
    policy_events_total = int(rows["c"]) if rows else 0
    return {
        "indicator_series_total": indicator_series_total,
        "indicator_points_total": indicator_points_total,
        "interventions_total": interventions_total,
        "intervention_events_total": intervention_events_total,
        "causal_estimates_total": causal_estimates_total,
        "policy_events_total": policy_events_total,
    }


def build_payload(conn: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    snapshot_date = args.snapshot_date if hasattr(args, "snapshot_date") and args.snapshot_date else infer_snapshot_date(conn)
    counts = table_counts(conn)

    series, points_by_series = load_series(conn, max_series=args.max_series, min_points=args.min_points)
    series_payload, series_stats = enrich_series(
        series,
        points_by_series,
        max_points_per_series=max(4, args.max_points_per_series),
    )

    policy_events = load_policy_events(conn, max_events=max(0, args.max_events))
    associations, association_stats = build_associations(
        series_payload=series_payload,
        policy_events=policy_events,
        pre_window_days=max(1, args.pre_window_days),
        post_window_days=max(1, args.post_window_days),
        max_associations_per_series=max(0, args.max_associations_per_series),
        max_associations=max(0, args.max_associations),
    )

    association_by_event = Counter()
    for row in associations:
        association_by_event[row["policy_event_id"]] += 1

    for item in policy_events:
        item["associated_series_count"] = int(association_by_event.get(item["policy_event_id"], 0))

    event_summary = sorted(
        policy_events,
        key=lambda row: (row.get("event_date") or "", row.get("policy_event_id", "")),
        reverse=True,
    )

    source_filters = {
        "series_source_ids": sorted(series_stats.get("by_source", {}).keys()),
        "event_source_ids": sorted({item["source_id"] for item in policy_events if item["source_id"]}),
        "domains": sorted(
            {item.get("domain_label") or item.get("domain_key") for item in policy_events if item.get("domain_label") or item.get("domain_key")}
        ),
    }

    return {
        "meta": {
            "generated_at": now_utc_iso(),
            "snapshot_date": snapshot_date,
            "snapshot_db": args.db,
            "filters": {
                "max_series": int(args.max_series),
                "min_points": int(args.min_points),
                "max_points_per_series": int(args.max_points_per_series),
                "max_events": int(args.max_events),
                "max_associations_per_series": int(args.max_associations_per_series),
                "max_associations": int(args.max_associations),
                "pre_window_days": int(args.pre_window_days),
                "post_window_days": int(args.post_window_days),
            },
        },
        "coverage": {
            **counts,
            "series_loaded": len(series_payload),
            "events_loaded": len(policy_events),
            "events_in_association": association_stats["linked_events"],
            "associations_total": association_stats["pairs_total"],
            "series_in_association": association_stats["linked_series"],
            "series_by_source": series_stats["by_source"],
            "series_coverage_by_point_count": {
                "min_points_included": int(min((s["point_count"] for s in series_payload), default=0)),
                "max_points_included": int(max((s["point_count"] for s in series_payload), default=0)),
            },
        },
        "series": series_payload,
        "policy_events": event_summary,
        "associations": associations,
        "limitations": {
            "interventions_available": counts["interventions_total"] > 0,
            "intervention_events_available": counts["intervention_events_total"] > 0,
            "causal_estimates_available": counts["causal_estimates_total"] > 0,
            "description": [
                "Este dataset está en fase temprana: hoy predomina evidencia descriptiva.",
                "No hay pipeline estable de intervenciones e impactos causales en esta fase.",
                "Las asociaciones son diferencias de indicador antes/después por ventana temporal, no causalidad.",
            ],
            "method_note": "Correlación no implica causalidad.",
        },
        "filters": source_filters,
    }


def save_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)

    if not db_path.exists():
        print(f"ERROR: no existe DB -> {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        payload = build_payload(conn, args)
    finally:
        conn.close()

    save_payload(out_path, payload)
    print(f"OK policy outcomes -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
