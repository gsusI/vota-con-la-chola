#!/usr/bin/env python3
"""Validate readiness of official procedural-review apply CSV before DB upsert."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")

_REQUIRED_HEADERS: tuple[str, ...] = (
    "sanction_source_id",
    "kpi_id",
    "period_date",
    "source_url",
    "evidence_date",
    "evidence_quote",
    "value",
)

_RATE_KPI_IDS = {
    "kpi:formal_annulment_rate",
    "kpi:recurso_estimation_rate",
}

_P90_KPI_ID = "kpi:resolution_delay_p90_days"
MIN_EVIDENCE_QUOTE_LEN = 20


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _to_float(raw: Any) -> float | None:
    token = _norm(raw)
    if not token:
        return None
    return float(token)


def _is_yyyy_mm_dd(value: str) -> bool:
    token = _norm(value)
    if not token:
        return False
    try:
        datetime.strptime(token, "%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return False
    return True


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = [str(h or "") for h in (reader.fieldnames or [])]
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({str(k or ""): str(v or "") for k, v in row.items()})
    return headers, rows


def _metric_key(row: dict[str, str]) -> str:
    given = _norm(row.get("metric_key"))
    if given:
        return given
    return "|".join(
        [
            _norm(row.get("kpi_id")),
            _norm(row.get("sanction_source_id")),
            _norm(row.get("period_date")),
            _norm(row.get("period_granularity")) or "year",
        ]
    )


def _load_allowed_sources(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT sanction_source_id FROM sanction_volume_sources").fetchall()
    return {_norm(r["sanction_source_id"]) for r in rows if _norm(r["sanction_source_id"])}


def _load_allowed_kpis(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT kpi_id FROM sanction_procedural_kpi_definitions").fetchall()
    return {_norm(r["kpi_id"]) for r in rows if _norm(r["kpi_id"])}


def _load_allowed_source_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT source_id FROM sources").fetchall()
    return {_norm(r["source_id"]) for r in rows if _norm(r["source_id"])}


def _reason_priority(reason: str) -> int:
    if reason in {
        "missing_required_field",
        "invalid_numeric_value",
        "invalid_sanction_source_id",
        "invalid_kpi_id",
        "invalid_evidence_date",
    }:
        return 100
    if reason in {"invalid_source_id", "invalid_source_url", "duplicate_metric_key", "short_evidence_quote"}:
        return 80
    if reason in {"missing_ratio_components", "rate_value_out_of_range", "zero_denominator"}:
        return 70
    if reason in {"formula_mismatch", "non_positive_p90_days"}:
        return 60
    return 30


def _queue_key(line_no: int, reason: str) -> str:
    return f"line:{line_no}:{reason}"


def build_report(
    conn: sqlite3.Connection,
    *,
    input_csv: Path,
    tolerance: float,
    queue_limit: int = 0,
) -> dict[str, Any]:
    headers, rows = _read_csv(input_csv)
    header_set = {_norm(h) for h in headers if _norm(h)}
    missing_headers = [h for h in _REQUIRED_HEADERS if h not in header_set]

    allowed_sources = _load_allowed_sources(conn)
    allowed_kpis = _load_allowed_kpis(conn)
    allowed_source_ids = _load_allowed_source_ids(conn)

    counts: dict[str, int] = {
        "rows_seen": 0,
        "rows_ready": 0,
        "rows_blocked": 0,
        "rows_missing_required_fields": 0,
        "rows_invalid_sanction_source_id": 0,
        "rows_invalid_kpi_id": 0,
        "rows_invalid_source_id": 0,
        "rows_invalid_source_url": 0,
        "rows_invalid_numeric": 0,
        "rows_invalid_evidence_date": 0,
        "rows_short_evidence_quote": 0,
        "rows_duplicate_metric_key": 0,
        "rows_missing_ratio_components": 0,
        "rows_rate_out_of_range": 0,
        "rows_zero_denominator": 0,
        "rows_formula_mismatch": 0,
        "rows_non_positive_p90_days": 0,
    }

    queue_rows: list[dict[str, Any]] = []
    metric_key_seen: dict[str, int] = {}

    for idx, row in enumerate(rows, start=2):
        counts["rows_seen"] += 1
        reasons: list[str] = []

        sanction_source_id = _norm(row.get("sanction_source_id"))
        kpi_id = _norm(row.get("kpi_id"))
        period_date = _norm(row.get("period_date"))
        source_url = _norm(row.get("source_url"))
        source_id = _norm(row.get("source_id"))
        evidence_date = _norm(row.get("evidence_date"))
        evidence_quote = _norm(row.get("evidence_quote"))
        value_raw = row.get("value")
        numerator_raw = row.get("numerator")
        denominator_raw = row.get("denominator")

        for required in _REQUIRED_HEADERS:
            if not _norm(row.get(required)):
                reasons.append("missing_required_field")
                counts["rows_missing_required_fields"] += 1
                break

        if sanction_source_id and sanction_source_id not in allowed_sources:
            reasons.append("invalid_sanction_source_id")
            counts["rows_invalid_sanction_source_id"] += 1

        if kpi_id and kpi_id not in allowed_kpis:
            reasons.append("invalid_kpi_id")
            counts["rows_invalid_kpi_id"] += 1

        if source_id and source_id not in allowed_source_ids:
            reasons.append("invalid_source_id")
            counts["rows_invalid_source_id"] += 1

        if source_url and not (source_url.startswith("http://") or source_url.startswith("https://")):
            reasons.append("invalid_source_url")
            counts["rows_invalid_source_url"] += 1
        if evidence_date and not _is_yyyy_mm_dd(evidence_date):
            reasons.append("invalid_evidence_date")
            counts["rows_invalid_evidence_date"] += 1
        if evidence_quote and len(evidence_quote) < MIN_EVIDENCE_QUOTE_LEN:
            reasons.append("short_evidence_quote")
            counts["rows_short_evidence_quote"] += 1

        value: float | None = None
        numerator: float | None = None
        denominator: float | None = None
        try:
            value = _to_float(value_raw)
            numerator = _to_float(numerator_raw)
            denominator = _to_float(denominator_raw)
        except Exception:
            reasons.append("invalid_numeric_value")
            counts["rows_invalid_numeric"] += 1

        if value is None and "missing_required_field" not in reasons:
            reasons.append("invalid_numeric_value")
            counts["rows_invalid_numeric"] += 1

        metric_key = _metric_key(row)
        if metric_key:
            if metric_key in metric_key_seen:
                reasons.append("duplicate_metric_key")
                counts["rows_duplicate_metric_key"] += 1
            else:
                metric_key_seen[metric_key] = idx

        if kpi_id in _RATE_KPI_IDS:
            if numerator is None or denominator is None:
                reasons.append("missing_ratio_components")
                counts["rows_missing_ratio_components"] += 1
            else:
                if denominator <= 0:
                    reasons.append("zero_denominator")
                    counts["rows_zero_denominator"] += 1
                if value is not None:
                    if value < 0 or value > 1:
                        reasons.append("rate_value_out_of_range")
                        counts["rows_rate_out_of_range"] += 1
                    if denominator > 0:
                        expected = numerator / denominator
                        if abs(value - expected) > max(0.0, float(tolerance)):
                            reasons.append("formula_mismatch")
                            counts["rows_formula_mismatch"] += 1

        if kpi_id == _P90_KPI_ID and value is not None and value <= 0:
            reasons.append("non_positive_p90_days")
            counts["rows_non_positive_p90_days"] += 1

        if reasons:
            counts["rows_blocked"] += 1
            for reason in sorted(set(reasons)):
                queue_rows.append(
                    {
                        "queue_key": _queue_key(idx, reason),
                        "csv_line": idx,
                        "priority": _reason_priority(reason),
                        "reason": reason,
                        "sanction_source_id": sanction_source_id,
                        "kpi_id": kpi_id,
                        "period_date": period_date,
                        "metric_key": metric_key,
                        "source_url": source_url,
                        "evidence_date": evidence_date,
                    }
                )
        else:
            counts["rows_ready"] += 1

    queue_rows.sort(key=lambda r: (-int(r["priority"]), int(r["csv_line"]), _norm(r["reason"])))
    if int(queue_limit) > 0:
        queue_rows = queue_rows[: int(queue_limit)]

    checks = {
        "input_file_has_rows": counts["rows_seen"] > 0,
        "headers_complete": len(missing_headers) == 0,
        "rows_ready_present": counts["rows_ready"] > 0,
        "rows_blocked_zero": counts["rows_blocked"] == 0,
    }
    if counts["rows_seen"] == 0 or missing_headers:
        status = "failed"
    elif counts["rows_blocked"] > 0:
        status = "degraded"
    else:
        status = "ok"

    coverage = {
        "rows_ready_pct": round((counts["rows_ready"] / counts["rows_seen"]) if counts["rows_seen"] else 0.0, 6),
        "rows_blocked_pct": round((counts["rows_blocked"] / counts["rows_seen"]) if counts["rows_seen"] else 0.0, 6),
    }

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "input_csv": str(input_csv),
        "required_headers": list(_REQUIRED_HEADERS),
        "headers_present": headers,
        "missing_headers": missing_headers,
        "tolerance": float(tolerance),
        "totals": counts,
        "coverage": coverage,
        "checks": checks,
        "queue": queue_rows,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "queue_key",
        "csv_line",
        "priority",
        "reason",
        "sanction_source_id",
        "kpi_id",
        "period_date",
        "metric_key",
        "source_url",
        "evidence_date",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Report readiness of official procedural-review apply CSV"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--in", dest="in_file", required=True, help="Input CSV for apply")
    ap.add_argument("--tolerance", type=float, default=0.01, help="Allowed abs delta for value vs numerator/denominator")
    ap.add_argument("--queue-limit", type=int, default=0)
    ap.add_argument("--csv-out", default="")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    in_path = Path(args.in_file)
    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2
    if not in_path.exists():
        print(json.dumps({"error": f"input csv not found: {in_path}"}, ensure_ascii=False))
        return 2

    conn = open_db(db_path)
    try:
        report = build_report(
            conn,
            input_csv=in_path,
            tolerance=float(args.tolerance),
            queue_limit=int(args.queue_limit),
        )
    finally:
        conn.close()

    if _norm(args.csv_out):
        _write_csv(Path(args.csv_out), list(report.get("queue") or []))

    payload = {
        **report,
        "db_path": str(db_path),
        "strict": bool(args.strict),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if bool(args.strict) and str(payload.get("status")) != "ok":
        return 4
    return 0 if str(payload.get("status")) != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
