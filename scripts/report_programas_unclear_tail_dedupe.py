#!/usr/bin/env python3
"""Report and export deduped unclear-tail queue for programas_partidos."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_PARTIES = "BNG,VOX"
STRICT_FAIL_EXIT = 4


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-id", default="programas_partidos")
    p.add_argument(
        "--parties",
        default=DEFAULT_PARTIES,
        help=f"CSV of party names (default: {DEFAULT_PARTIES})",
    )
    p.add_argument("--excerpt-len", type=int, default=320, help="Excerpt length in outputs")
    p.add_argument(
        "--max-duplicate-share",
        type=float,
        default=1.0,
        help="Max allowed duplicate share in strict mode (0..1, default 1.0)",
    )
    p.add_argument("--out", required=True, help="JSON report output path")
    p.add_argument("--queue-out", default="", help="Optional deduped queue CSV output path")
    p.add_argument("--profile-out", default="", help="Optional per-source profile CSV output path")
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


def _normalize_excerpt(raw: Any) -> str:
    txt = str(raw or "").replace("\n", " ").replace("\r", " ")
    return " ".join(txt.split()).lower()


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_unclear_rows(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    parties: list[str],
    excerpt_len: int,
) -> list[dict[str, Any]]:
    if not parties:
        return []
    placeholders = ",".join(["?"] * len(parties))
    params: list[Any] = [max(1, int(excerpt_len or 320)), str(source_id), *parties]
    rows = conn.execute(
        f"""
        SELECT
          p.full_name AS party_name,
          te.source_url,
          te.evidence_id,
          SUBSTR(
            REPLACE(REPLACE(COALESCE(te.excerpt, ''), CHAR(10), ' '), CHAR(13), ' '),
            1,
            ?
          ) AS excerpt
        FROM topic_evidence te
        JOIN persons p ON p.person_id = te.person_id
        WHERE te.source_id = ?
          AND te.stance = 'unclear'
          AND p.full_name IN ({placeholders})
        ORDER BY p.full_name ASC, te.source_url ASC, te.evidence_id ASC
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def build_report(
    *,
    source_id: str,
    parties: list[str],
    rows: list[dict[str, Any]],
    max_duplicate_share: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    profile: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        party_name = str(row.get("party_name") or "")
        source_url = str(row.get("source_url") or "")
        evidence_id = int(row.get("evidence_id") or 0)
        excerpt = str(row.get("excerpt") or "")
        excerpt_norm = _normalize_excerpt(excerpt)

        pkey = (party_name, source_url)
        p = profile.setdefault(
            pkey,
            {
                "party_name": party_name,
                "source_url": source_url,
                "unclear_rows": 0,
                "_unique_norm": set(),
            },
        )
        p["unclear_rows"] = int(p["unclear_rows"]) + 1
        p["_unique_norm"].add(excerpt_norm)

        gkey = (party_name, source_url, excerpt_norm)
        g = groups.get(gkey)
        if g is None:
            groups[gkey] = {
                "party_name": party_name,
                "source_url": source_url,
                "excerpt_norm": excerpt_norm,
                "excerpt": excerpt,
                "evidence_id": evidence_id,
                "occurrences": 1,
                "evidence_ids": [evidence_id],
            }
            continue
        g["occurrences"] = int(g["occurrences"]) + 1
        g["evidence_ids"].append(evidence_id)

    deduped_queue = sorted(
        [
            {
                "party_name": str(g["party_name"]),
                "source_url": str(g["source_url"]),
                "evidence_id": int(g["evidence_id"]),
                "occurrences": int(g["occurrences"]),
                "duplicate_count": max(0, int(g["occurrences"]) - 1),
                "evidence_ids": ",".join(str(int(ev)) for ev in sorted(set(g["evidence_ids"]))),
                "excerpt": str(g["excerpt"]),
                "excerpt_norm": str(g["excerpt_norm"]),
            }
            for g in groups.values()
        ],
        key=lambda item: (
            str(item["party_name"]),
            str(item["source_url"]),
            int(item["evidence_id"]),
        ),
    )

    profile_rows = []
    for p in profile.values():
        unique_count = len(set(p["_unique_norm"]))
        raw_count = int(p["unclear_rows"])
        profile_rows.append(
            {
                "party_name": str(p["party_name"]),
                "source_url": str(p["source_url"]),
                "unclear_rows": raw_count,
                "unclear_unique_excerpt_rows": unique_count,
                "unclear_duplicate_rows": max(0, raw_count - unique_count),
            }
        )
    profile_rows.sort(
        key=lambda item: (
            -int(item["unclear_duplicate_rows"]),
            -int(item["unclear_rows"]),
            str(item["party_name"]),
            str(item["source_url"]),
        )
    )

    raw_total = len(rows)
    unique_total = len(deduped_queue)
    duplicate_total = max(0, raw_total - unique_total)
    duplicate_share = (float(duplicate_total) / float(raw_total)) if raw_total > 0 else 0.0
    threshold = max(0.0, min(1.0, float(max_duplicate_share)))

    checks = {
        "non_negative_counts": raw_total >= unique_total >= 0,
        "queue_unique_keys": len(deduped_queue) == len(
            {
                (
                    str(r["party_name"]),
                    str(r["source_url"]),
                    str(r["excerpt_norm"]),
                )
                for r in deduped_queue
            }
        ),
        "duplicate_share_within_threshold": float(duplicate_share) <= float(threshold),
    }
    strict_fail_reasons: list[str] = []
    if not checks["non_negative_counts"]:
        strict_fail_reasons.append("invalid_count_invariant")
    if not checks["queue_unique_keys"]:
        strict_fail_reasons.append("queue_has_duplicate_keys")
    if not checks["duplicate_share_within_threshold"]:
        strict_fail_reasons.append("duplicate_share_above_threshold")

    status = "ok" if len(strict_fail_reasons) == 0 else "degraded"
    report = {
        "source_id": str(source_id),
        "parties": list(parties),
        "raw_unclear_rows_total": int(raw_total),
        "unclear_unique_excerpt_rows_total": int(unique_total),
        "unclear_duplicate_rows_total": int(duplicate_total),
        "duplicate_share": float(duplicate_share),
        "max_duplicate_share": float(threshold),
        "deduped_queue_rows_total": int(unique_total),
        "by_source_url": profile_rows,
        "checks": checks,
        "status": status,
        "passed": status == "ok",
        "strict_fail_reasons": strict_fail_reasons,
    }
    return report, deduped_queue, profile_rows


def _write_queue_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "sample_id",
                "party_name",
                "source_url",
                "evidence_id",
                "occurrences",
                "duplicate_count",
                "evidence_ids",
                "excerpt",
            ]
        )
        for idx, row in enumerate(rows, start=1):
            writer.writerow(
                [
                    f"UQ{idx:04d}",
                    row["party_name"],
                    row["source_url"],
                    int(row["evidence_id"]),
                    int(row["occurrences"]),
                    int(row["duplicate_count"]),
                    row["evidence_ids"],
                    row["excerpt"],
                ]
            )


def _write_profile_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "party_name",
                "source_url",
                "unclear_rows",
                "unclear_unique_excerpt_rows",
                "unclear_duplicate_rows",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["party_name"],
                    row["source_url"],
                    int(row["unclear_rows"]),
                    int(row["unclear_unique_excerpt_rows"]),
                    int(row["unclear_duplicate_rows"]),
                ]
            )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    out_path = Path(args.out)
    queue_out = Path(args.queue_out) if str(args.queue_out or "").strip() else None
    profile_out = Path(args.profile_out) if str(args.profile_out or "").strip() else None
    parties = _parse_csv_list(str(args.parties or ""))
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2
    if not parties:
        print("ERROR: parties empty", file=sys.stderr)
        return 2

    with open_db(db_path) as conn:
        rows = fetch_unclear_rows(
            conn,
            source_id=str(args.source_id),
            parties=parties,
            excerpt_len=max(1, int(args.excerpt_len or 320)),
        )
    report, queue_rows, profile_rows = build_report(
        source_id=str(args.source_id),
        parties=parties,
        rows=rows,
        max_duplicate_share=float(args.max_duplicate_share),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    if queue_out is not None:
        _write_queue_csv(queue_out, queue_rows)
    if profile_out is not None:
        _write_profile_csv(profile_out, profile_rows)

    print(json.dumps(report, ensure_ascii=True, indent=2))
    if bool(args.strict) and str(report.get("status")) != "ok":
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
