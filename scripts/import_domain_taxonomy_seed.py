#!/usr/bin/env python3
"""Import domains from docs/domain_taxonomy_es.md into the `domains` table."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.politicos_es.db import apply_schema, open_db, upsert_domain
from etl.politicos_es.util import normalize_ws


DEFAULT_DOC = "docs/domain_taxonomy_es.md"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


TIER_HEADER_RE = re.compile(r"^##\\s*Tier\\s*(\\d+)\\b", re.IGNORECASE)
TABLE_ROW_RE = re.compile(r"^\\s*`?([^`|]+)`?\\s*\\|\\s*([^|]+?)\\s*$")
TABLE_PIPE_RE = re.compile(r"^\\s*\\|")
TABLE_SEPARATOR_RE = re.compile(r"^\\s*\\|\\s*-{3,}")


def _parse_domain_rows(doc_text: str) -> list[dict[str, Any]]:
    current_tier: int | None = None
    rows: list[dict[str, Any]] = []

    for line in doc_text.splitlines():
        if TABLE_SEPARATOR_RE.match(line):
            continue

        tier_match = TIER_HEADER_RE.match(line)
        if tier_match:
            current_tier = int(tier_match.group(1))
            continue

        if not TABLE_PIPE_RE.match(line) or current_tier is None:
            continue

        parts = [part.strip() for part in line.strip().split("|")]
        if len(parts) < 3:
            continue
        key_part = parts[1].strip()
        label_part = parts[2].strip()
        if not key_part or not label_part:
            continue
        canonical_key = TABLE_ROW_RE.sub(lambda m: m.group(1), key_part)
        label = TABLE_ROW_RE.sub(lambda m: m.group(2), label_part)
        key = _norm(canonical_key.strip("`").strip())
        text = _norm(label)
        if not key or not text:
            continue
        rows.append(
            {
                "canonical_key": key,
                "label": text,
                "tier": current_tier,
            }
        )

    return rows


def import_seed(
    conn,
    *,
    domain_rows: list[dict[str, Any]],
    snapshot_date: str,
) -> dict[str, Any]:
    ts = now_utc_iso()
    counts: dict[str, int] = {
        "rows_seen": 0,
        "rows_inserted": 0,
        "rows_updated": 0,
        "rows_skipped": 0,
    }
    by_tier: dict[str, int] = {}

    for row in domain_rows:
        counts["rows_seen"] += 1
        canonical_key = _norm(row.get("canonical_key"))
        label = _norm(row.get("label"))
        tier = row.get("tier")
        if not canonical_key or not label or tier is None:
            counts["rows_skipped"] += 1
            continue
        exists = conn.execute(
            "SELECT 1 FROM domains WHERE canonical_key = ?",
            (canonical_key,),
        ).fetchone()
        upsert_domain(
            conn,
            canonical_key_value=canonical_key,
            label=label,
            description=None,
            tier=int(tier),
            now_iso=ts,
        )
        if exists:
            counts["rows_updated"] += 1
        else:
            counts["rows_inserted"] += 1
        by_tier[str(int(tier))] = by_tier.get(str(int(tier)), 0) + 1

    totals = conn.execute(
        """
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN tier = 1 THEN 1 ELSE 0 END) AS tier1_total,
          SUM(CASE WHEN tier = 2 THEN 1 ELSE 0 END) AS tier2_total,
          SUM(CASE WHEN tier = 3 THEN 1 ELSE 0 END) AS tier3_total
        FROM domains
        """
    ).fetchone()

    conn.commit()

    return {
        "status": "ok",
        "snapshot_date": snapshot_date,
        "counts": {
            **counts,
            "by_tier_seen": by_tier,
            "db_total": int(totals["total"] if totals else 0),
            "db_tier1_total": int(totals["tier1_total"] or 0) if totals else 0,
            "db_tier2_total": int(totals["tier2_total"] or 0) if totals else 0,
            "db_tier3_total": int(totals["tier3_total"] or 0) if totals else 0,
        },
        "generated_at": ts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import domain taxonomy from docs/domain_taxonomy_es.md")
    parser.add_argument("--db", required=True)
    parser.add_argument("--doc", default=DEFAULT_DOC)
    parser.add_argument("--snapshot-date", default=today_utc_date())
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    doc_path = Path(args.doc)
    if not doc_path.exists():
        print(f"Seed doc no encontrado: {doc_path}", flush=True)
        return 2

    db_path = Path(args.db)
    schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"

    domain_rows = _parse_domain_rows(doc_path.read_text(encoding="utf-8"))
    conn = open_db(db_path)
    try:
        apply_schema(conn, schema_path)
        report = import_seed(
            conn,
            domain_rows=domain_rows,
            snapshot_date=str(args.snapshot_date),
        )
    finally:
        conn.close()

    payload = {
        "generated_at": now_utc_iso(),
        "db_path": str(db_path),
        "source_doc": str(doc_path),
        "rows_total": len(domain_rows),
        "import": report,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(str(args.out)):
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
