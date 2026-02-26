#!/usr/bin/env python3
"""Import policy axes (Tier 1) from docs/codebook_tier1_es.md into SQLite."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.politicos_es.db import apply_schema, open_db, upsert_policy_axis
from etl.politicos_es.util import normalize_ws


DEFAULT_DOC = "docs/codebook_tier1_es.md"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


DOMAIN_SECTION_RE = re.compile(r"^###\s*\d+\)\s*`([^`]+)`")
AXIS_HEADER_RE = re.compile(r"^\s*\d+\.\s*`([^`]+)`\s*$")
AXIS_SIGN_RE = re.compile(r"^\s*-\s*`([+-]1)`:\s*(.+?)\s*$")
MAPPING_SECTION_RE = re.compile(r"^\s*##\s*Mapeo al esquema SQLite", re.IGNORECASE)


def _axis_label(axis_key: str) -> str:
    return axis_key.replace("_", " ").replace("-", " ").strip().title()


def _axis_description(directions: dict[str, str]) -> str | None:
    parts: list[str] = []
    if "+1" in directions:
        parts.append(f"+1: {directions['+1']}")
    if "-1" in directions:
        parts.append(f"-1: {directions['-1']}")
    joined = "; ".join(parts)
    return joined if joined else None


def _parse_policy_axes_rows(doc_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    current_domain_key: str | None = None
    current_axis_key: str | None = None
    current_axis_order = 0
    current_directions: dict[str, str] = {}

    def flush() -> None:
        if current_domain_key is None or current_axis_key is None:
            return
        rows.append(
            {
                "domain_canonical_key": current_domain_key,
                "axis_canonical_key": current_axis_key,
                "axis_order": current_axis_order,
                "label": _axis_label(current_axis_key),
                "description": _axis_description(current_directions),
            }
        )

    for raw_line in doc_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if MAPPING_SECTION_RE.match(line):
            break

        domain_match = DOMAIN_SECTION_RE.match(line)
        if domain_match:
            flush()
            current_domain_key = _norm(domain_match.group(1))
            current_axis_key = None
            current_axis_order = 0
            current_directions = {}
            continue

        if current_domain_key is None:
            continue

        axis_match = AXIS_HEADER_RE.match(line)
        if axis_match:
            flush()
            current_axis_order += 1
            current_axis_key = _norm(axis_match.group(1))
            current_directions = {}
            continue

        direction_match = AXIS_SIGN_RE.match(line)
        if direction_match and current_axis_key is not None:
            direction = direction_match.group(1)
            text = _norm(direction_match.group(2))
            if text:
                current_directions[direction] = text

    flush()
    return rows


def import_seed(
    conn,
    *,
    axis_rows: list[dict[str, Any]],
    snapshot_date: str,
) -> dict[str, Any]:
    ts = now_utc_iso()
    counts: dict[str, int] = {
        "rows_seen": 0,
        "rows_inserted": 0,
        "rows_updated": 0,
        "rows_skipped": 0,
        "rows_skipped_missing_domain": 0,
    }
    by_domain: dict[str, int] = {}

    for row in axis_rows:
        counts["rows_seen"] += 1
        domain_key = _norm(row.get("domain_canonical_key"))
        axis_key = _norm(row.get("axis_canonical_key"))
        axis_order = row.get("axis_order")
        label = _norm(row.get("label"))
        description = row.get("description")

        if not domain_key or not axis_key or not axis_order:
            counts["rows_skipped"] += 1
            continue

        domain_row = conn.execute(
            "SELECT domain_id FROM domains WHERE canonical_key = ?",
            (domain_key,),
        ).fetchone()
        if domain_row is None:
            counts["rows_skipped"] += 1
            counts["rows_skipped_missing_domain"] += 1
            continue

        domain_id = int(domain_row["domain_id"])
        exists = conn.execute(
            "SELECT 1 FROM policy_axes WHERE domain_id = ? AND canonical_key = ?",
            (domain_id, axis_key),
        ).fetchone()

        upsert_policy_axis(
            conn,
            domain_id=domain_id,
            canonical_key_value=axis_key,
            label=label,
            description=_norm(description),
            axis_order=int(axis_order),
            now_iso=ts,
        )
        if exists:
            counts["rows_updated"] += 1
        else:
            counts["rows_inserted"] += 1

        by_domain[domain_key] = by_domain.get(domain_key, 0) + 1

    conn.commit()

    totals = conn.execute(
        "SELECT COUNT(*) AS total FROM policy_axes"
    ).fetchone()

    return {
        "status": "ok",
        "snapshot_date": snapshot_date,
        "counts": {
            **counts,
            "by_domain": by_domain,
            "policy_axes_total": int(totals["total"] if totals else 0),
        },
        "generated_at": ts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import tier1 policy axes from docs/codebook_tier1_es.md")
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

    axis_rows = _parse_policy_axes_rows(doc_path.read_text(encoding="utf-8"))
    conn = open_db(db_path)
    try:
        apply_schema(conn, schema_path)
        report = import_seed(
            conn,
            axis_rows=axis_rows,
            snapshot_date=str(args.snapshot_date),
        )
    finally:
        conn.close()

    payload = {
        "generated_at": now_utc_iso(),
        "db_path": str(db_path),
        "source_doc": str(doc_path),
        "rows_total": len(axis_rows),
        "import": report,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
