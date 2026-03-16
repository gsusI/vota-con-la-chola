#!/usr/bin/env python3
"""Audit fiscal snippets assigned to Empleo in programas_partidos."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_FISCAL_TERMS = "imposto de sociedades,fiscalidad,fiscalitat,impuesto,impostos,tribut,irpf,iva,sociedades"
DEFAULT_EMPLOYMENT_ANCHORS = "emple,trabaj,traballo,emprego,laboral,paro,salari,ocupacion,ocupacio"
STRICT_FAIL_EXIT = 4


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-id", default="programas_partidos")
    p.add_argument("--topic-key", default="concern:v1:empleo")
    p.add_argument("--parties", default="BNG", help="CSV party list")
    p.add_argument("--fiscal-terms", default=DEFAULT_FISCAL_TERMS, help="CSV lowercase fiscal terms")
    p.add_argument("--employment-anchor-terms", default=DEFAULT_EMPLOYMENT_ANCHORS, help="CSV lowercase employment anchors")
    p.add_argument(
        "--max-suspicious-support-rows",
        type=int,
        default=0,
        help="Strict threshold for support rows with fiscal terms but no employment anchors",
    )
    p.add_argument("--out", required=True, help="JSON report output path")
    p.add_argument("--csv-out", default="", help="Optional CSV rows output path")
    p.add_argument("--strict", action="store_true", help="Exit non-zero unless status=ok")
    return p.parse_args(argv)


def _parse_csv_list(raw: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").split(","):
        value = token.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _norm_excerpt(value: str) -> str:
    return " ".join(str(value or "").replace("\n", " ").replace("\r", " ").lower().split())


def build_report(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    topic_key: str,
    parties: list[str],
    fiscal_terms: list[str],
    employment_anchor_terms: list[str],
    max_suspicious_support_rows: int,
) -> dict[str, Any]:
    strict_fail_reasons: list[str] = []
    if not parties:
        strict_fail_reasons.append("empty_parties")
    if not fiscal_terms:
        strict_fail_reasons.append("empty_fiscal_terms")

    if strict_fail_reasons:
        return {
            "source_id": str(source_id),
            "topic_key": str(topic_key),
            "parties": parties,
            "fiscal_terms": fiscal_terms,
            "employment_anchor_terms": employment_anchor_terms,
            "max_suspicious_support_rows": int(max_suspicious_support_rows),
            "rows_total": 0,
            "support_rows": 0,
            "unclear_rows": 0,
            "suspicious_support_rows": 0,
            "checks": {
                "rows_present": False,
                "suspicious_support_within_threshold": False,
            },
            "status": "degraded",
            "passed": False,
            "strict_fail_reasons": strict_fail_reasons,
            "rows": [],
            "parties_breakdown": [],
        }

    placeholders = ",".join(["?"] * len(parties))
    params: list[Any] = [str(source_id), str(topic_key), *parties]
    db_rows = conn.execute(
        f"""
        SELECT
          te.evidence_id,
          p.full_name AS party_name,
          t.canonical_key AS topic_key,
          te.stance,
          te.stance_method,
          te.source_url,
          COALESCE(te.excerpt, '') AS excerpt
        FROM topic_evidence te
        JOIN persons p ON p.person_id = te.person_id
        JOIN topics t ON t.topic_id = te.topic_id
        WHERE te.source_id = ?
          AND t.canonical_key = ?
          AND p.full_name IN ({placeholders})
        ORDER BY p.full_name ASC, te.evidence_id ASC
        """,
        params,
    ).fetchall()

    rows: list[dict[str, Any]] = []
    parties_breakdown_map: dict[str, dict[str, Any]] = {}
    support_rows = 0
    unclear_rows = 0
    suspicious_support_rows = 0

    for raw in db_rows:
        excerpt_norm = _norm_excerpt(str(raw["excerpt"] or ""))
        matched_terms = [term for term in fiscal_terms if term in excerpt_norm]
        if not matched_terms:
            continue
        stance = str(raw["stance"] or "").strip().lower()
        has_employment_anchor = any(term in excerpt_norm for term in employment_anchor_terms)
        suspicious_support = stance == "support" and not has_employment_anchor

        party_name = str(raw["party_name"] or "")
        if party_name not in parties_breakdown_map:
            parties_breakdown_map[party_name] = {
                "party_name": party_name,
                "rows_total": 0,
                "support_rows": 0,
                "unclear_rows": 0,
                "suspicious_support_rows": 0,
            }
        party_entry = parties_breakdown_map[party_name]
        party_entry["rows_total"] = int(party_entry["rows_total"]) + 1
        if stance == "support":
            support_rows += 1
            party_entry["support_rows"] = int(party_entry["support_rows"]) + 1
        if stance == "unclear":
            unclear_rows += 1
            party_entry["unclear_rows"] = int(party_entry["unclear_rows"]) + 1
        if suspicious_support:
            suspicious_support_rows += 1
            party_entry["suspicious_support_rows"] = int(party_entry["suspicious_support_rows"]) + 1

        rows.append(
            {
                "evidence_id": int(raw["evidence_id"]),
                "party_name": party_name,
                "topic_key": str(raw["topic_key"] or ""),
                "stance": stance,
                "stance_method": str(raw["stance_method"] or ""),
                "source_url": str(raw["source_url"] or ""),
                "matched_fiscal_terms": matched_terms,
                "has_employment_anchor": bool(has_employment_anchor),
                "suspicious_support": bool(suspicious_support),
                "excerpt": str(raw["excerpt"] or "").replace("\n", " ").replace("\r", " ")[:360],
            }
        )

    rows_total = len(rows)
    checks = {
        "rows_present": rows_total > 0,
        "suspicious_support_within_threshold": suspicious_support_rows <= int(max_suspicious_support_rows),
    }

    if not checks["rows_present"]:
        strict_fail_reasons.append("no_matching_rows")
    if not checks["suspicious_support_within_threshold"]:
        strict_fail_reasons.append("suspicious_support_rows_above_threshold")

    status = "ok" if all(checks.values()) else "degraded"
    parties_breakdown = sorted(parties_breakdown_map.values(), key=lambda x: str(x["party_name"]))

    return {
        "source_id": str(source_id),
        "topic_key": str(topic_key),
        "parties": parties,
        "fiscal_terms": fiscal_terms,
        "employment_anchor_terms": employment_anchor_terms,
        "max_suspicious_support_rows": int(max_suspicious_support_rows),
        "rows_total": rows_total,
        "support_rows": int(support_rows),
        "unclear_rows": int(unclear_rows),
        "suspicious_support_rows": int(suspicious_support_rows),
        "checks": checks,
        "status": status,
        "passed": status == "ok",
        "strict_fail_reasons": strict_fail_reasons,
        "parties_breakdown": parties_breakdown,
        "rows": rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "evidence_id",
        "party_name",
        "topic_key",
        "stance",
        "stance_method",
        "source_url",
        "matched_fiscal_terms",
        "has_employment_anchor",
        "suspicious_support",
        "excerpt",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out_row = dict(row)
            out_row["matched_fiscal_terms"] = "|".join(str(v) for v in list(row.get("matched_fiscal_terms", [])))
            writer.writerow(out_row)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = open_db(db_path)
    try:
        report = build_report(
            conn,
            source_id=str(args.source_id),
            topic_key=str(args.topic_key),
            parties=_parse_csv_list(str(args.parties)),
            fiscal_terms=[term.lower() for term in _parse_csv_list(str(args.fiscal_terms))],
            employment_anchor_terms=[term.lower() for term in _parse_csv_list(str(args.employment_anchor_terms))],
            max_suspicious_support_rows=int(args.max_suspicious_support_rows),
        )
    finally:
        conn.close()

    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.csv_out:
        write_csv(Path(args.csv_out), list(report.get("rows", [])))

    if args.strict and str(report.get("status", "")).lower() != "ok":
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    sys.exit(main())
