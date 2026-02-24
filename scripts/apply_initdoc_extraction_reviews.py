#!/usr/bin/env python3
"""Apply review decisions to `parl_initiative_doc_extractions` from CSV.

CSV contract (headers):
- source_record_pk (required)
- review_status (required for rows to apply): resolved|ignored|pending
- final_subject (optional)
- final_title (optional)
- final_confidence (optional float)
- review_note (optional)
- reviewer (optional)

Rows with empty `review_status` are skipped.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.util import normalize_ws, now_utc_iso, stable_json


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
_ALLOWED_STATUS = {"resolved", "ignored", "pending"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply initiative-doc extraction review decisions")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--in", dest="in_file", required=True, help="Input CSV with review decisions")
    p.add_argument("--source-id", default="parl_initiative_docs", help="Extraction source_id scope")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _parse_float(raw: str) -> float | None:
    token = normalize_ws(raw)
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _load_payload(raw: str | None) -> dict[str, Any]:
    token = normalize_ws(str(raw or ""))
    if not token:
        return {}
    try:
        obj = json.loads(token)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return []
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({str(k or ""): str(v or "") for k, v in row.items()})
        return rows


def apply_review_decisions(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    rows: list[dict[str, str]],
    dry_run: bool,
) -> dict[str, Any]:
    now_iso = now_utc_iso()

    seen = 0
    decision_rows = 0
    updated = 0
    skipped_blank_status = 0
    skipped_invalid_status = 0
    skipped_missing_pk = 0
    skipped_not_found = 0
    skipped_source_mismatch = 0
    invalid_confidence = 0
    failures: list[str] = []

    updates: list[tuple[Any, ...]] = []

    for r in rows:
        seen += 1

        pk_token = normalize_ws(r.get("source_record_pk", ""))
        if not pk_token:
            skipped_missing_pk += 1
            continue
        try:
            source_record_pk = int(pk_token)
        except ValueError:
            skipped_missing_pk += 1
            continue

        status = normalize_ws(r.get("review_status", "")).lower()
        if not status:
            skipped_blank_status += 1
            continue
        if status not in _ALLOWED_STATUS:
            skipped_invalid_status += 1
            continue
        decision_rows += 1

        final_subject = normalize_ws(r.get("final_subject", ""))
        final_title = normalize_ws(r.get("final_title", ""))
        final_confidence = _parse_float(r.get("final_confidence", ""))
        reviewer = normalize_ws(r.get("reviewer", ""))
        review_note = normalize_ws(r.get("review_note", ""))

        if normalize_ws(r.get("final_confidence", "")) and final_confidence is None:
            invalid_confidence += 1

        current = conn.execute(
            """
            SELECT source_id, analysis_payload_json
            FROM parl_initiative_doc_extractions
            WHERE source_record_pk = ?
            """,
            (source_record_pk,),
        ).fetchone()
        if current is None:
            skipped_not_found += 1
            continue

        row_source_id = normalize_ws(str(current["source_id"] or ""))
        if source_id and row_source_id != source_id:
            skipped_source_mismatch += 1
            continue

        payload = _load_payload(str(current["analysis_payload_json"] or ""))
        review_event = {
            "status": status,
            "reviewer": reviewer,
            "note": review_note,
            "reviewed_at": now_iso,
        }
        if final_subject:
            review_event["final_subject"] = final_subject
        if final_title:
            review_event["final_title"] = final_title
        if final_confidence is not None:
            review_event["final_confidence"] = final_confidence

        history = payload.get("review_history")
        if not isinstance(history, list):
            history = []
        history.append(review_event)

        payload["review_status"] = status
        payload["reviewed_at"] = now_iso
        if reviewer:
            payload["reviewer"] = reviewer
        if review_note:
            payload["review_note"] = review_note
        payload["review_history"] = history[-50:]

        needs_review = 1 if status == "pending" else 0

        updates.append(
            (
                final_subject or None,
                final_title or None,
                final_confidence,
                int(needs_review),
                stable_json(payload),
                now_iso,
                source_record_pk,
            )
        )

    if updates and not dry_run:
        with conn:
            conn.executemany(
                """
                UPDATE parl_initiative_doc_extractions
                SET
                  extracted_subject = CASE
                    WHEN ? IS NOT NULL AND TRIM(?) <> '' THEN ?
                    ELSE extracted_subject
                  END,
                  extracted_title = CASE
                    WHEN ? IS NOT NULL AND TRIM(?) <> '' THEN ?
                    ELSE extracted_title
                  END,
                  confidence = COALESCE(?, confidence),
                  needs_review = ?,
                  analysis_payload_json = ?,
                  updated_at = ?
                WHERE source_record_pk = ?
                """,
                [
                    (
                        u[0],
                        u[0],
                        u[0],
                        u[1],
                        u[1],
                        u[1],
                        u[2],
                        u[3],
                        u[4],
                        u[5],
                        u[6],
                    )
                    for u in updates
                ],
            )

    updated = len(updates)

    return {
        "source_id": source_id,
        "dry_run": bool(dry_run),
        "rows_seen": int(seen),
        "rows_with_decision": int(decision_rows),
        "updated": int(updated),
        "skipped_blank_status": int(skipped_blank_status),
        "skipped_invalid_status": int(skipped_invalid_status),
        "skipped_missing_pk": int(skipped_missing_pk),
        "skipped_not_found": int(skipped_not_found),
        "skipped_source_mismatch": int(skipped_source_mismatch),
        "invalid_confidence_values": int(invalid_confidence),
        "failures": failures,
    }


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
    with open_db(db_path) as conn:
        result = apply_review_decisions(
            conn,
            source_id=normalize_ws(str(args.source_id or "")) or "parl_initiative_docs",
            rows=rows,
            dry_run=bool(args.dry_run),
        )

    result.update(
        {
            "db": str(db_path),
            "input_csv": str(in_path),
        }
    )

    if normalize_ws(str(args.out or "")):
        out_path = Path(str(args.out)).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
