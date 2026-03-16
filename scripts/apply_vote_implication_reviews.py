#!/usr/bin/env python3
"""Apply citizen-facing vote implication review decisions from CSV."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws, now_utc_iso, stable_json


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
ALLOWED_STATUS = {"resolved", "ignored", "pending"}
ALLOWED_IMPLICATION_KINDS = {
    "binding_law",
    "budget_tax",
    "regulation",
    "non_binding_motion",
    "oversight",
    "authorization",
    "procedural",
    "unknown",
}
ALLOWED_BINDING_STRENGTHS = {"binding", "non_binding", "authorization", "procedural", "unknown"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply vote implication review decisions")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--in", dest="in_file", required=True, help="Input CSV with review decisions")
    p.add_argument("--source-id", default="", help="Optional queue source_id scope")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _parse_float(raw: Any) -> float | None:
    token = _norm(raw)
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _load_payload(raw: Any) -> dict[str, Any]:
    token = _norm(raw)
    if not token:
        return {}
    try:
        obj = json.loads(token)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return []
        return [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]


def apply_review_decisions(
    conn: Any,
    *,
    rows: list[dict[str, str]],
    source_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    seen = 0
    decision_rows = 0
    updated = 0
    skipped_blank_status = 0
    skipped_invalid_status = 0
    skipped_missing_key = 0
    skipped_not_found = 0
    skipped_source_mismatch = 0
    invalid_confidence_values = 0
    invalid_kind_values = 0
    invalid_binding_values = 0

    updates: list[tuple[Any, ...]] = []

    for row in rows:
        seen += 1
        review_key = _norm(row.get("review_key"))
        if not review_key:
            skipped_missing_key += 1
            continue

        status = _norm(row.get("review_status")).lower()
        if not status:
            skipped_blank_status += 1
            continue
        if status not in ALLOWED_STATUS:
            skipped_invalid_status += 1
            continue
        decision_rows += 1

        final_kind = _norm(row.get("final_implication_kind")).lower()
        if final_kind and final_kind not in ALLOWED_IMPLICATION_KINDS:
            invalid_kind_values += 1
            continue
        final_binding = _norm(row.get("final_binding_strength")).lower()
        if final_binding and final_binding not in ALLOWED_BINDING_STRENGTHS:
            invalid_binding_values += 1
            continue
        final_confidence = _parse_float(row.get("final_confidence"))
        if _norm(row.get("final_confidence")) and final_confidence is None:
            invalid_confidence_values += 1
            continue

        citizen_title = _norm(row.get("citizen_title"))
        citizen_question = _norm(row.get("citizen_question"))
        citizen_summary = _norm(row.get("citizen_summary"))
        impact_if_approved = _norm(row.get("impact_if_approved"))
        impact_if_rejected = _norm(row.get("impact_if_rejected"))
        affected_groups = _norm(row.get("affected_groups"))
        evidence_quote = _norm(row.get("evidence_quote"))
        reviewer = _norm(row.get("reviewer"))
        review_note = _norm(row.get("review_note"))

        if status == "resolved" and not (citizen_title or citizen_question or citizen_summary):
            skipped_invalid_status += 1
            continue

        current = conn.execute(
            """
            SELECT source_id, raw_payload_json
            FROM parl_vote_implication_reviews
            WHERE review_key = ?
            """,
            (review_key,),
        ).fetchone()
        if current is None:
            skipped_not_found += 1
            continue

        row_source_id = _norm(current["source_id"])
        if source_id and row_source_id != _norm(source_id):
            skipped_source_mismatch += 1
            continue

        payload = _load_payload(current["raw_payload_json"])
        history = payload.get("review_history")
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "status": status,
                "reviewed_at": now_iso,
                "reviewer": reviewer,
                "note": review_note,
                "final_implication_kind": final_kind,
                "final_binding_strength": final_binding,
                "citizen_title": citizen_title,
                "citizen_question": citizen_question,
                "citizen_summary": citizen_summary,
                "impact_if_approved": impact_if_approved,
                "impact_if_rejected": impact_if_rejected,
                "affected_groups": affected_groups,
                "evidence_quote": evidence_quote,
                "final_confidence": final_confidence,
            }
        )
        payload["review_status"] = status
        payload["reviewed_at"] = now_iso
        if reviewer:
            payload["reviewer"] = reviewer
        if review_note:
            payload["review_note"] = review_note
        payload["review_history"] = history[-50:]

        updates.append(
            (
                status,
                citizen_title or None,
                citizen_question or None,
                citizen_summary or None,
                impact_if_approved or None,
                impact_if_rejected or None,
                affected_groups or None,
                evidence_quote or None,
                final_kind or None,
                final_binding or None,
                final_confidence,
                review_note or None,
                stable_json(payload),
                now_iso,
                review_key,
            )
        )

    if updates and not dry_run:
        with conn:
            conn.executemany(
                """
                UPDATE parl_vote_implication_reviews
                SET
                  status = ?,
                  citizen_title = ?,
                  citizen_question = ?,
                  citizen_summary = ?,
                  impact_if_approved = ?,
                  impact_if_rejected = ?,
                  affected_groups = ?,
                  evidence_quote = ?,
                  final_implication_kind = ?,
                  final_binding_strength = ?,
                  confidence = ?,
                  note = ?,
                  raw_payload_json = ?,
                  updated_at = ?
                WHERE review_key = ?
                """,
                updates,
            )
    updated = len(updates)

    return {
        "source_id": _norm(source_id),
        "dry_run": bool(dry_run),
        "rows_seen": int(seen),
        "rows_with_decision": int(decision_rows),
        "updated": int(updated),
        "skipped_blank_status": int(skipped_blank_status),
        "skipped_invalid_status": int(skipped_invalid_status),
        "skipped_missing_key": int(skipped_missing_key),
        "skipped_not_found": int(skipped_not_found),
        "skipped_source_mismatch": int(skipped_source_mismatch),
        "invalid_confidence_values": int(invalid_confidence_values),
        "invalid_kind_values": int(invalid_kind_values),
        "invalid_binding_values": int(invalid_binding_values),
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    in_path = Path(args.in_file)

    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2
    if not in_path.exists():
        print(f"ERROR: input CSV not found: {in_path}", file=sys.stderr)
        return 2

    rows = _read_csv(in_path)
    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        result = apply_review_decisions(
            conn,
            rows=rows,
            source_id=str(args.source_id or ""),
            dry_run=bool(args.dry_run),
        )

    out_path = _norm(args.out)
    if out_path:
        Path(out_path).write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
