#!/usr/bin/env python3
"""Export upgrade queue for sanction evidence rows still backed by seed source_records."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def build_queue_rows(
    conn: Any,
    *,
    seed_schema_version: str = "sanction_norms_seed_v1",
    limit: int = 0,
) -> list[dict[str, Any]]:
    like_pattern = f'%"seed_schema_version": "{_norm(seed_schema_version)}"%'
    sql = """
        SELECT
          e.responsibility_evidence_id,
          e.responsibility_id,
          r.role,
          r.actor_label,
          r.fragment_id,
          f.fragment_type,
          f.fragment_label,
          f.norm_id,
          n.boe_id,
          n.title AS norm_title,
          e.evidence_type,
          e.source_id AS evidence_source_id,
          e.source_url AS evidence_source_url,
          e.evidence_date,
          e.evidence_quote,
          e.source_record_pk,
          sr.source_id AS source_record_source_id,
          sr.source_record_id,
          sr.source_snapshot_date,
          sr.created_at AS source_record_created_at
        FROM legal_fragment_responsibility_evidence e
        JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
        JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        JOIN source_records sr ON sr.source_record_pk = e.source_record_pk
        WHERE COALESCE(sr.raw_payload, '') LIKE ?
        ORDER BY n.norm_id, f.fragment_order, r.role, e.responsibility_evidence_id
    """
    params: list[Any] = [like_pattern]
    if int(limit) > 0:
        sql += " LIMIT ?"
        params.append(int(limit))

    rows = conn.execute(sql, tuple(params)).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        evidence_id = int(row["responsibility_evidence_id"])
        out.append(
            {
                "queue_key": f"responsibility_evidence_id:{evidence_id}",
                "responsibility_evidence_id": evidence_id,
                "responsibility_id": int(row["responsibility_id"]),
                "norm_id": _norm(row["norm_id"]),
                "boe_id": _norm(row["boe_id"]),
                "norm_title": _norm(row["norm_title"]),
                "fragment_id": _norm(row["fragment_id"]),
                "fragment_type": _norm(row["fragment_type"]),
                "fragment_label": _norm(row["fragment_label"]),
                "role": _norm(row["role"]),
                "actor_label": _norm(row["actor_label"]),
                "evidence_type": _norm(row["evidence_type"]),
                "evidence_source_id": _norm(row["evidence_source_id"]),
                "evidence_source_url": _norm(row["evidence_source_url"]),
                "evidence_date": _norm(row["evidence_date"]),
                "evidence_quote": _norm(row["evidence_quote"]),
                "source_record_pk": int(row["source_record_pk"]),
                "source_record_source_id": _norm(row["source_record_source_id"]),
                "source_record_id": _norm(row["source_record_id"]),
                "source_snapshot_date": _norm(row["source_snapshot_date"]),
                "source_record_created_at": _norm(row["source_record_created_at"]),
                "next_action": "replace_source_record_with_non_seed_ingest_reference",
            }
        )
    return out


def build_queue_report(
    conn: Any,
    *,
    seed_schema_version: str = "sanction_norms_seed_v1",
    limit: int = 0,
) -> dict[str, Any]:
    queue_rows = build_queue_rows(
        conn,
        seed_schema_version=seed_schema_version,
        limit=int(limit),
    )
    norms = {str(r.get("norm_id") or "") for r in queue_rows if _norm(r.get("norm_id"))}
    fragments = {str(r.get("fragment_id") or "") for r in queue_rows if _norm(r.get("fragment_id"))}
    responsibilities = {
        int(r.get("responsibility_id") or 0)
        for r in queue_rows
        if int(r.get("responsibility_id") or 0) > 0
    }
    evidence_types = {str(r.get("evidence_type") or "") for r in queue_rows if _norm(r.get("evidence_type"))}
    rows_total = len(queue_rows)
    status = "ok" if rows_total == 0 else "degraded"
    return {
        "generated_at": now_utc_iso(),
        "seed_schema_version": _norm(seed_schema_version) or "sanction_norms_seed_v1",
        "status": status,
        "totals": {
            "queue_rows_total": rows_total,
            "queue_norms_total": len(norms),
            "queue_fragments_total": len(fragments),
            "queue_responsibilities_total": len(responsibilities),
            "queue_evidence_types_total": len(evidence_types),
        },
        "checks": {
            "queue_visible": rows_total > 0,
            "queue_empty": rows_total == 0,
        },
        "queue_rows": queue_rows,
    }


def write_queue_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "queue_key",
        "responsibility_evidence_id",
        "responsibility_id",
        "norm_id",
        "boe_id",
        "norm_title",
        "fragment_id",
        "fragment_type",
        "fragment_label",
        "role",
        "actor_label",
        "evidence_type",
        "evidence_source_id",
        "evidence_source_url",
        "evidence_date",
        "evidence_quote",
        "source_record_pk",
        "source_record_source_id",
        "source_record_id",
        "source_snapshot_date",
        "source_record_created_at",
        "next_action",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Export queue for non-seed source_record provenance upgrades")
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed-schema-version", default="sanction_norms_seed_v1")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--strict-empty", action="store_true")
    ap.add_argument("--out", default="", help="optional JSON output path")
    ap.add_argument("--csv-out", default="", help="optional CSV output path")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    conn = open_db(db_path)
    try:
        report = build_queue_report(
            conn,
            seed_schema_version=_norm(args.seed_schema_version) or "sanction_norms_seed_v1",
            limit=int(args.limit),
        )
    finally:
        conn.close()

    payload = {
        **report,
        "db_path": str(db_path),
        "limit": int(args.limit),
        "strict_empty": bool(args.strict_empty),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    if _norm(args.csv_out):
        write_queue_csv(report.get("queue_rows", []), Path(args.csv_out))
    print(rendered)

    if bool(args.strict_empty) and int(payload["totals"].get("queue_rows_total", 0)) > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
