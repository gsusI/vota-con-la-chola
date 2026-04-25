#!/usr/bin/env python3
"""Apply official procedural-review metrics to `sanction_procedural_metrics` from CSV."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.db import open_db
from etl.politicos_es.db import upsert_source_record
from etl.politicos_es.util import normalize_ws, sha256_bytes, stable_json

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SOURCE_ID = "boe_api_legal"
MIN_EVIDENCE_QUOTE_LEN = 20


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return []
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({str(k or ""): str(v or "") for k, v in row.items()})
        return rows


def _to_float(raw: Any) -> float | None:
    token = _norm(raw)
    if not token:
        return None
    return float(token)


def _to_int(raw: Any) -> int | None:
    token = _norm(raw)
    if not token:
        return None
    return int(token)


def _is_yyyy_mm_dd(value: str) -> bool:
    token = _norm(value)
    if not token:
        return False
    try:
        datetime.strptime(token, "%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return False
    return True


def _source_exists(conn: sqlite3.Connection, source_id: str) -> bool:
    token = _norm(source_id)
    if not token:
        return False
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (token,)).fetchone()
    return row is not None


def _ensure_metric_evidence_columns(conn: sqlite3.Connection) -> None:
    cols = {
        str(row["name"])
        for row in conn.execute('PRAGMA table_info("sanction_procedural_metrics")').fetchall()
    }
    if "evidence_date" not in cols:
        conn.execute('ALTER TABLE "sanction_procedural_metrics" ADD COLUMN evidence_date TEXT')
    if "evidence_quote" not in cols:
        conn.execute('ALTER TABLE "sanction_procedural_metrics" ADD COLUMN evidence_quote TEXT')


def _kpi_exists(conn: sqlite3.Connection, kpi_id: str) -> bool:
    token = _norm(kpi_id)
    if not token:
        return False
    row = conn.execute(
        "SELECT 1 FROM sanction_procedural_kpi_definitions WHERE kpi_id = ?",
        (token,),
    ).fetchone()
    return row is not None


def _sanction_source_exists(conn: sqlite3.Connection, sanction_source_id: str) -> bool:
    token = _norm(sanction_source_id)
    if not token:
        return False
    row = conn.execute(
        "SELECT 1 FROM sanction_volume_sources WHERE sanction_source_id = ?",
        (token,),
    ).fetchone()
    return row is not None


def _resolve_source_record_pk(
    conn: sqlite3.Connection,
    *,
    cache: dict[tuple[str, str], int | None],
    source_id: str,
    source_record_id: str,
) -> int | None:
    sid = _norm(source_id)
    srid = _norm(source_record_id)
    if not sid or not srid:
        return None
    key = (sid, srid)
    if key in cache:
        return cache[key]
    row = conn.execute(
        """
        SELECT source_record_pk
        FROM source_records
        WHERE source_id = ? AND source_record_id = ?
        """,
        (sid, srid),
    ).fetchone()
    if row is None:
        cache[key] = None
        return None
    pk = int(row["source_record_pk"])
    cache[key] = pk
    return pk


def _metric_key(row: dict[str, Any]) -> str:
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


def _default_source_record_id(row: dict[str, Any]) -> str:
    return ":".join(
        [
            "official_review",
            _slug(row.get("sanction_source_id") or ""),
            _slug(row.get("kpi_id") or ""),
            _slug(row.get("period_date") or ""),
            _slug(row.get("period_granularity") or "year"),
        ]
    )


def apply_rows(
    conn: sqlite3.Connection,
    *,
    rows: list[dict[str, str]],
    default_source_id: str,
    snapshot_date: str,
    dry_run: bool,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    source_record_cache: dict[tuple[str, str], int | None] = {}
    _ensure_metric_evidence_columns(conn)

    counts: dict[str, int] = {
        "rows_seen": 0,
        "rows_ready": 0,
        "rows_upserted": 0,
        "inserted_rows": 0,
        "updated_rows": 0,
        "skipped_missing_required": 0,
        "skipped_invalid_sanction_source_id": 0,
        "skipped_invalid_kpi_id": 0,
        "skipped_invalid_source_id": 0,
        "skipped_invalid_numeric": 0,
        "skipped_invalid_evidence_date": 0,
        "skipped_short_evidence_quote": 0,
        "source_record_pk_existing": 0,
        "source_record_pk_auto_resolved": 0,
        "source_record_pk_auto_created": 0,
        "source_record_pk_would_create": 0,
    }
    samples: list[dict[str, Any]] = []

    for idx, raw in enumerate(rows, start=2):
        counts["rows_seen"] += 1

        sanction_source_id = _norm(raw.get("sanction_source_id"))
        kpi_id = _norm(raw.get("kpi_id"))
        period_date = _norm(raw.get("period_date"))
        period_granularity = _norm(raw.get("period_granularity")) or "year"
        source_url = _norm(raw.get("source_url"))
        evidence_date = _norm(raw.get("evidence_date"))
        evidence_quote = _norm(raw.get("evidence_quote"))

        if (
            not sanction_source_id
            or not kpi_id
            or not period_date
            or not source_url
            or not evidence_date
            or not evidence_quote
        ):
            counts["skipped_missing_required"] += 1
            continue
        if not _is_yyyy_mm_dd(evidence_date):
            counts["skipped_invalid_evidence_date"] += 1
            continue
        if len(evidence_quote) < MIN_EVIDENCE_QUOTE_LEN:
            counts["skipped_short_evidence_quote"] += 1
            continue

        if not _sanction_source_exists(conn, sanction_source_id):
            counts["skipped_invalid_sanction_source_id"] += 1
            continue

        if not _kpi_exists(conn, kpi_id):
            counts["skipped_invalid_kpi_id"] += 1
            continue

        source_id = _norm(raw.get("source_id")) or _norm(default_source_id)
        if source_id and not _source_exists(conn, source_id):
            counts["skipped_invalid_source_id"] += 1
            continue

        try:
            value = _to_float(raw.get("value"))
            numerator = _to_float(raw.get("numerator"))
            denominator = _to_float(raw.get("denominator"))
            source_record_pk = _to_int(raw.get("source_record_pk"))
        except Exception:
            counts["skipped_invalid_numeric"] += 1
            continue

        if value is None:
            counts["skipped_missing_required"] += 1
            continue

        source_record_id = _norm(raw.get("source_record_id"))
        if source_id and source_record_pk is None:
            if not source_record_id:
                source_record_id = _default_source_record_id(
                    {
                        "sanction_source_id": sanction_source_id,
                        "kpi_id": kpi_id,
                        "period_date": period_date,
                        "period_granularity": period_granularity,
                    }
                )
            resolved_pk = _resolve_source_record_pk(
                conn,
                cache=source_record_cache,
                source_id=source_id,
                source_record_id=source_record_id,
            )
            if resolved_pk is not None:
                source_record_pk = int(resolved_pk)
                counts["source_record_pk_auto_resolved"] += 1
            else:
                sr_payload = {
                    "record_kind": "sanction_procedural_official_review_metric",
                    "sanction_source_id": sanction_source_id,
                    "kpi_id": kpi_id,
                    "period_date": period_date,
                    "period_granularity": period_granularity,
                    "source_url": source_url,
                    "evidence_date": evidence_date,
                    "evidence_quote": evidence_quote,
                    "value": value,
                    "numerator": numerator,
                    "denominator": denominator,
                    "snapshot_date": _norm(snapshot_date),
                }
                if dry_run:
                    counts["source_record_pk_would_create"] += 1
                else:
                    source_record_pk = upsert_source_record(
                        conn,
                        source_id,
                        source_record_id,
                        _norm(snapshot_date) or None,
                        stable_json(sr_payload),
                        sha256_bytes(stable_json(sr_payload).encode("utf-8")),
                        now_iso,
                    )
                    source_record_cache[(source_id, source_record_id)] = int(source_record_pk)
                    counts["source_record_pk_auto_created"] += 1
        elif source_record_pk is not None:
            counts["source_record_pk_existing"] += 1

        metric_key = _metric_key(
            {
                "metric_key": raw.get("metric_key"),
                "kpi_id": kpi_id,
                "sanction_source_id": sanction_source_id,
                "period_date": period_date,
                "period_granularity": period_granularity,
            }
        )
        if not metric_key:
            counts["skipped_missing_required"] += 1
            continue

        exists = (
            conn.execute(
                "SELECT 1 FROM sanction_procedural_metrics WHERE metric_key = ?",
                (metric_key,),
            ).fetchone()
            is not None
        )

        payload = {
            "record_kind": "sanction_procedural_official_review_csv_import",
            "sanction_source_id": sanction_source_id,
            "kpi_id": kpi_id,
            "period_date": period_date,
            "period_granularity": period_granularity,
            "value": value,
            "numerator": numerator,
            "denominator": denominator,
            "source_url": source_url,
            "evidence_date": evidence_date,
            "evidence_quote": evidence_quote,
            "source_id": source_id or None,
            "source_record_id": source_record_id or None,
            "source_snapshot_date": _norm(snapshot_date) or None,
            "input_row": raw,
        }

        counts["rows_ready"] += 1

        if not dry_run:
            conn.execute(
                """
                INSERT INTO sanction_procedural_metrics (
                  metric_key, kpi_id, sanction_source_id,
                  period_date, period_granularity,
                  value, numerator, denominator,
                  source_id, source_url, source_record_pk, evidence_date, evidence_quote,
                  raw_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(metric_key) DO UPDATE SET
                  kpi_id=excluded.kpi_id,
                  sanction_source_id=excluded.sanction_source_id,
                  period_date=excluded.period_date,
                  period_granularity=excluded.period_granularity,
                  value=excluded.value,
                  numerator=excluded.numerator,
                  denominator=excluded.denominator,
                  source_id=COALESCE(excluded.source_id, sanction_procedural_metrics.source_id),
                  source_url=excluded.source_url,
                  source_record_pk=COALESCE(excluded.source_record_pk, sanction_procedural_metrics.source_record_pk),
                  evidence_date=excluded.evidence_date,
                  evidence_quote=excluded.evidence_quote,
                  raw_payload=excluded.raw_payload,
                  updated_at=excluded.updated_at
                """,
                (
                    metric_key,
                    kpi_id,
                    sanction_source_id,
                    period_date,
                    period_granularity,
                    value,
                    numerator,
                    denominator,
                    source_id or None,
                    source_url,
                    source_record_pk,
                    evidence_date,
                    evidence_quote,
                    stable_json(payload),
                    now_iso,
                    now_iso,
                ),
            )
            counts["rows_upserted"] += 1
            if exists:
                counts["updated_rows"] += 1
            else:
                counts["inserted_rows"] += 1

        if len(samples) < 20:
            samples.append(
                {
                    "csv_line": idx,
                    "metric_key": metric_key,
                    "sanction_source_id": sanction_source_id,
                    "kpi_id": kpi_id,
                    "period_date": period_date,
                    "source_record_pk": source_record_pk,
                    "would_insert": not exists,
                }
            )

    if not dry_run:
        conn.commit()

    return {
        "dry_run": bool(dry_run),
        "snapshot_date": _norm(snapshot_date),
        "default_source_id": _norm(default_source_id),
        "counts": counts,
        "samples": samples,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply official procedural-review metrics from CSV")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--in", dest="in_file", required=True, help="Input CSV")
    p.add_argument("--source-id", default=DEFAULT_SOURCE_ID, help="Default source_id for source_records")
    p.add_argument("--snapshot-date", default=today_utc_date())
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--strict", action="store_true", help="Exit non-zero when rows are skipped")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


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

    rows = _read_csv(in_path)

    conn = open_db(db_path)
    try:
        report = apply_rows(
            conn,
            rows=rows,
            default_source_id=_norm(args.source_id) or DEFAULT_SOURCE_ID,
            snapshot_date=_norm(args.snapshot_date) or today_utc_date(),
            dry_run=bool(args.dry_run),
        )
    finally:
        conn.close()

    payload = {
        **report,
        "db_path": str(db_path),
        "input_csv": str(in_path),
        "strict": bool(args.strict),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if bool(args.strict):
        skipped_total = (
            int(payload["counts"].get("skipped_missing_required", 0))
            + int(payload["counts"].get("skipped_invalid_sanction_source_id", 0))
            + int(payload["counts"].get("skipped_invalid_kpi_id", 0))
            + int(payload["counts"].get("skipped_invalid_source_id", 0))
            + int(payload["counts"].get("skipped_invalid_numeric", 0))
        )
        if skipped_total > 0:
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
