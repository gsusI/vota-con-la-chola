#!/usr/bin/env python3
"""Export prefilled raw template for official procedural-review metrics capture."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.report_sanction_procedural_official_review_status import OFFICIAL_REVIEW_SOURCE_IDS

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SOURCE_ID = "boe_api_legal"
DEFAULT_PERIOD_GRANULARITY = "year"

RAW_FIELDNAMES: tuple[str, ...] = (
    "sanction_source_id",
    "period_date",
    "period_granularity",
    "source_url",
    "evidence_date",
    "evidence_quote",
    "recurso_presentado_count",
    "recurso_estimado_count",
    "anulaciones_formales_count",
    "resolution_delay_p90_days",
    "source_id",
    "source_record_id",
    "source_label",
    "organismo",
    "expected_metrics",
    "procedural_kpis_expected",
    "procedural_kpis_covered_total",
    "procedural_metric_rows_total",
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _slug(value: str) -> str:
    out: list[str] = []
    prev_dash = False
    for ch in _norm(value).lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    token = "".join(out).strip("-")
    return token or "na"


def _source_record_id(*, sanction_source_id: str, period_date: str, period_granularity: str) -> str:
    return ":".join(
        [
            "official_review_raw",
            _slug(sanction_source_id),
            _slug(period_date),
            _slug(period_granularity),
        ]
    )


def _source_expected_metrics(raw_contract_json: Any) -> list[str]:
    raw = _norm(raw_contract_json)
    if not raw:
        return []
    try:
        doc = json.loads(raw)
    except Exception:  # noqa: BLE001
        return []
    vals = doc.get("expected_metrics")
    if not isinstance(vals, list):
        return []
    out: list[str] = []
    for value in vals:
        token = _norm(value)
        if token:
            out.append(token)
    return out


def build_raw_template(
    conn: Any,
    *,
    period_date: str,
    period_granularity: str,
    default_source_id: str,
    only_missing: bool,
) -> dict[str, Any]:
    placeholders = ",".join(["?"] * len(OFFICIAL_REVIEW_SOURCE_IDS))

    source_rows = conn.execute(
        f"""
        SELECT
          sanction_source_id,
          label,
          organismo,
          source_url,
          data_contract_json
        FROM sanction_volume_sources
        WHERE sanction_source_id IN ({placeholders})
        ORDER BY sanction_source_id
        """,
        OFFICIAL_REVIEW_SOURCE_IDS,
    ).fetchall()
    source_map = {str(row["sanction_source_id"]): row for row in source_rows}

    kpi_rows = conn.execute(
        """
        SELECT kpi_id
        FROM sanction_procedural_kpi_definitions
        ORDER BY kpi_id
        """
    ).fetchall()
    kpi_ids = [_norm(row["kpi_id"]) for row in kpi_rows if _norm(row["kpi_id"])]
    expected_kpis_total = len(kpi_ids)

    metric_rows = conn.execute(
        f"""
        SELECT
          sanction_source_id,
          COUNT(*) AS metric_rows_total,
          COUNT(DISTINCT kpi_id) AS kpis_covered_total
        FROM sanction_procedural_metrics
        WHERE sanction_source_id IN ({placeholders})
          AND period_date = ?
          AND period_granularity = ?
        GROUP BY sanction_source_id
        """,
        (*OFFICIAL_REVIEW_SOURCE_IDS, _norm(period_date), _norm(period_granularity)),
    ).fetchall()
    metric_map = {
        _norm(row["sanction_source_id"]): {
            "metric_rows_total": int(row["metric_rows_total"] or 0),
            "kpis_covered_total": int(row["kpis_covered_total"] or 0),
        }
        for row in metric_rows
    }

    rows: list[dict[str, Any]] = []
    counts = {
        "sources_expected_total": len(OFFICIAL_REVIEW_SOURCE_IDS),
        "sources_seeded_total": len(source_rows),
        "sources_missing_total": 0,
        "procedural_kpis_expected_total": expected_kpis_total,
        "rows_emitted_total": 0,
        "rows_skipped_fully_covered_total": 0,
    }

    for sanction_source_id in OFFICIAL_REVIEW_SOURCE_IDS:
        src = source_map.get(sanction_source_id)
        if src is None:
            counts["sources_missing_total"] += 1
            continue

        metrics = metric_map.get(sanction_source_id, {})
        kpis_covered_total = int(metrics.get("kpis_covered_total", 0))
        metric_rows_total = int(metrics.get("metric_rows_total", 0))
        if bool(only_missing) and expected_kpis_total > 0 and kpis_covered_total >= expected_kpis_total:
            counts["rows_skipped_fully_covered_total"] += 1
            continue

        expected_metrics = _source_expected_metrics(src["data_contract_json"])
        row = {
            "sanction_source_id": sanction_source_id,
            "period_date": _norm(period_date),
            "period_granularity": _norm(period_granularity) or DEFAULT_PERIOD_GRANULARITY,
            "source_url": _norm(src["source_url"]),
            "evidence_date": "",
            "evidence_quote": "",
            "recurso_presentado_count": "",
            "recurso_estimado_count": "",
            "anulaciones_formales_count": "",
            "resolution_delay_p90_days": "",
            "source_id": _norm(default_source_id) or DEFAULT_SOURCE_ID,
            "source_record_id": _source_record_id(
                sanction_source_id=sanction_source_id,
                period_date=_norm(period_date),
                period_granularity=_norm(period_granularity) or DEFAULT_PERIOD_GRANULARITY,
            ),
            "source_label": _norm(src["label"]),
            "organismo": _norm(src["organismo"]),
            "expected_metrics": ",".join(expected_metrics),
            "procedural_kpis_expected": ",".join(kpi_ids),
            "procedural_kpis_covered_total": kpis_covered_total,
            "procedural_metric_rows_total": metric_rows_total,
        }
        rows.append(row)

    counts["rows_emitted_total"] = len(rows)
    return {
        "generated_at": now_utc_iso(),
        "period_date": _norm(period_date),
        "period_granularity": _norm(period_granularity) or DEFAULT_PERIOD_GRANULARITY,
        "default_source_id": _norm(default_source_id) or DEFAULT_SOURCE_ID,
        "only_missing": bool(only_missing),
        "counts": counts,
        "sources_missing_seed": [
            source_id
            for source_id in OFFICIAL_REVIEW_SOURCE_IDS
            if source_id not in source_map
        ],
        "rows_preview": rows[:20],
        "rows": rows,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(RAW_FIELDNAMES))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in RAW_FIELDNAMES})


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Export prefilled raw CSV template for official procedural-review metrics capture"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--period-date", required=True)
    ap.add_argument("--period-granularity", default=DEFAULT_PERIOD_GRANULARITY)
    ap.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--only-missing", action="store_true")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--summary-out", default="", help="Optional JSON summary output")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_raw_template(
            conn,
            period_date=_norm(args.period_date),
            period_granularity=_norm(args.period_granularity) or DEFAULT_PERIOD_GRANULARITY,
            default_source_id=_norm(args.source_id) or DEFAULT_SOURCE_ID,
            only_missing=bool(args.only_missing),
        )
    finally:
        conn.close()

    rows = list(report.pop("rows", []))
    out_path = Path(args.out)
    _write_csv(out_path, rows)

    payload = {
        **report,
        "db_path": str(args.db),
        "output_csv": str(out_path),
        "rows_emitted_total": len(rows),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.summary_out):
        summary_path = Path(args.summary_out)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
