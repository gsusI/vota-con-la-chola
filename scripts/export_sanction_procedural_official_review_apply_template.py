#!/usr/bin/env python3
"""Export prefilled CSV template for official procedural-review metric apply loop."""

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


def _source_record_id(
    *,
    sanction_source_id: str,
    kpi_id: str,
    period_date: str,
    period_granularity: str,
) -> str:
    return ":".join(
        [
            "official_review",
            _slug(sanction_source_id),
            _slug(kpi_id),
            _slug(period_date),
            _slug(period_granularity),
        ]
    )


def build_template_rows(
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
        SELECT kpi_id, label, metric_formula, target_direction
        FROM sanction_procedural_kpi_definitions
        ORDER BY kpi_id
        """
    ).fetchall()

    existing_metric_keys: set[str] = set()
    if bool(only_missing):
        for row in conn.execute(
            f"""
            SELECT metric_key
            FROM sanction_procedural_metrics
            WHERE sanction_source_id IN ({placeholders})
              AND period_date = ?
              AND period_granularity = ?
            """,
            (*OFFICIAL_REVIEW_SOURCE_IDS, _norm(period_date), _norm(period_granularity)),
        ).fetchall():
            existing_metric_keys.add(_norm(row["metric_key"]))

    rows: list[dict[str, Any]] = []
    counts = {
        "sources_expected_total": len(OFFICIAL_REVIEW_SOURCE_IDS),
        "sources_seeded_total": len(source_rows),
        "sources_missing_total": 0,
        "kpis_total": len(kpi_rows),
        "rows_emitted_total": 0,
        "rows_skipped_existing_total": 0,
    }

    for sanction_source_id in OFFICIAL_REVIEW_SOURCE_IDS:
        src = source_map.get(sanction_source_id)
        if src is None:
            counts["sources_missing_total"] += 1
            continue

        source_url = _norm(src["source_url"])
        source_label = _norm(src["label"])
        organismo = _norm(src["organismo"])

        expected_metrics: str = ""
        try:
            contract = json.loads(_norm(src["data_contract_json"]) or "{}")
            vals = contract.get("expected_metrics")
            if isinstance(vals, list):
                expected_metrics = ",".join(_norm(v) for v in vals if _norm(v))
        except Exception:  # noqa: BLE001
            expected_metrics = ""

        for kpi in kpi_rows:
            kpi_id = _norm(kpi["kpi_id"])
            metric_key = "|".join([kpi_id, sanction_source_id, _norm(period_date), _norm(period_granularity)])
            if bool(only_missing) and metric_key in existing_metric_keys:
                counts["rows_skipped_existing_total"] += 1
                continue

            row = {
                "sanction_source_id": sanction_source_id,
                "kpi_id": kpi_id,
                "period_date": _norm(period_date),
                "period_granularity": _norm(period_granularity),
                "value": "",
                "numerator": "",
                "denominator": "",
                "source_url": source_url,
                "evidence_date": "",
                "evidence_quote": "",
                "source_id": _norm(default_source_id),
                "source_record_id": _source_record_id(
                    sanction_source_id=sanction_source_id,
                    kpi_id=kpi_id,
                    period_date=_norm(period_date),
                    period_granularity=_norm(period_granularity),
                ),
                "metric_key": metric_key,
                "source_label": source_label,
                "organismo": organismo,
                "kpi_label": _norm(kpi["label"]),
                "metric_formula": _norm(kpi["metric_formula"]),
                "target_direction": _norm(kpi["target_direction"]),
                "expected_metrics": expected_metrics,
            }
            rows.append(row)

    counts["rows_emitted_total"] = len(rows)
    return {
        "generated_at": now_utc_iso(),
        "period_date": _norm(period_date),
        "period_granularity": _norm(period_granularity),
        "default_source_id": _norm(default_source_id),
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
    fieldnames = [
        "sanction_source_id",
        "kpi_id",
        "period_date",
        "period_granularity",
        "value",
        "numerator",
        "denominator",
        "source_url",
        "evidence_date",
        "evidence_quote",
        "source_id",
        "source_record_id",
        "metric_key",
        "source_label",
        "organismo",
        "kpi_label",
        "metric_formula",
        "target_direction",
        "expected_metrics",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Export prefilled CSV template for official procedural-review metrics apply loop"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--period-date", required=True)
    ap.add_argument("--period-granularity", default="year")
    ap.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--only-missing", action="store_true")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--summary-out", default="", help="Optional JSON summary output")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_template_rows(
            conn,
            period_date=_norm(args.period_date),
            period_granularity=_norm(args.period_granularity) or "year",
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
