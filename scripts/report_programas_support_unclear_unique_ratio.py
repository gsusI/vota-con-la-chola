#!/usr/bin/env python3
"""Report support vs deduped-unclear ratio for programas_partidos."""

from __future__ import annotations

import argparse
import csv
import json
import re
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
    p.add_argument("--parties", default=DEFAULT_PARTIES, help=f"CSV party list (default: {DEFAULT_PARTIES})")
    p.add_argument(
        "--min-support-unclear-unique-ratio",
        type=float,
        default=1.0,
        help="Strict threshold for support_to_unclear_unique_ratio per source URL row",
    )
    p.add_argument("--out", required=True, help="JSON report output path")
    p.add_argument("--csv-out", default="", help="Optional breakdown CSV output path")
    p.add_argument(
        "--near-duplicate-jaccard-min",
        type=float,
        default=0.42,
        help="Jaccard threshold to collapse near-duplicate unclear excerpts",
    )
    p.add_argument(
        "--near-duplicate-containment-min",
        type=float,
        default=0.40,
        help="Containment threshold to collapse near-duplicate unclear excerpts",
    )
    p.add_argument(
        "--near-duplicate-ngram-size",
        type=int,
        default=6,
        help="Minimum token ngram size used as overlap guard for containment dedupe",
    )
    p.add_argument(
        "--disable-near-duplicate-dedupe",
        action="store_true",
        help="Use exact excerpt dedupe only (no near-duplicate collapse)",
    )
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


def _tokenize(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-z0-9]+", str(text or "").lower()) if len(tok) >= 3]


def _build_ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    size = max(1, int(n))
    if len(tokens) < size:
        return set()
    return {tuple(tokens[i : i + size]) for i in range(0, len(tokens) - size + 1)}


def _is_near_duplicate(
    *,
    left_set: set[str],
    right_set: set[str],
    left_ngrams: set[tuple[str, ...]],
    right_ngrams: set[tuple[str, ...]],
    jaccard_min: float,
    containment_min: float,
) -> bool:
    if not left_set or not right_set:
        return False
    inter = len(left_set & right_set)
    if inter <= 0:
        return False
    union = len(left_set | right_set)
    jaccard = (float(inter) / float(union)) if union > 0 else 0.0
    if jaccard >= float(jaccard_min):
        return True
    min_size = min(len(left_set), len(right_set))
    containment = (float(inter) / float(min_size)) if min_size > 0 else 0.0
    if containment < float(containment_min):
        return False
    if not left_ngrams or not right_ngrams:
        return False
    return bool(left_ngrams & right_ngrams)


def _collapse_unclear_unique_excerpts(
    *,
    excerpts: list[str],
    near_duplicate_dedupe_enabled: bool,
    near_duplicate_jaccard_min: float,
    near_duplicate_containment_min: float,
    near_duplicate_ngram_size: int,
) -> tuple[int, int]:
    unique_exact = sorted({str(v or "").strip() for v in excerpts if str(v or "").strip()})
    if not unique_exact:
        return 0, 0
    if not near_duplicate_dedupe_enabled or len(unique_exact) <= 1:
        return len(unique_exact), len(unique_exact)

    tokenized: list[list[str]] = [_tokenize(text) for text in unique_exact]
    token_sets: list[set[str]] = [set(tokens) for tokens in tokenized]
    ngrams: list[set[tuple[str, ...]]] = [
        _build_ngrams(tokens, near_duplicate_ngram_size) for tokens in tokenized
    ]
    parent = list(range(len(unique_exact)))

    def find(idx: int) -> int:
        root = idx
        while parent[root] != root:
            root = parent[root]
        while parent[idx] != idx:
            nxt = parent[idx]
            parent[idx] = root
            idx = nxt
        return root

    def union(i: int, j: int) -> None:
        ri = find(i)
        rj = find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(len(unique_exact)):
        for j in range(i + 1, len(unique_exact)):
            if _is_near_duplicate(
                left_set=token_sets[i],
                right_set=token_sets[j],
                left_ngrams=ngrams[i],
                right_ngrams=ngrams[j],
                jaccard_min=near_duplicate_jaccard_min,
                containment_min=near_duplicate_containment_min,
            ):
                union(i, j)

    clusters = {find(i) for i in range(len(unique_exact))}
    unique_deduped = len(clusters)
    return len(unique_exact), unique_deduped


def build_report(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    parties: list[str],
    min_ratio: float,
    near_duplicate_dedupe_enabled: bool = True,
    near_duplicate_jaccard_min: float = 0.42,
    near_duplicate_containment_min: float = 0.40,
    near_duplicate_ngram_size: int = 6,
) -> dict[str, Any]:
    if not parties:
        return {
            "source_id": str(source_id),
            "parties": [],
            "rows_total": 0,
            "status": "degraded",
            "passed": False,
            "strict_fail_reasons": ["empty_parties"],
            "checks": {
                "rows_present": False,
                "ratio_threshold_met": False,
            },
            "rows": [],
            "min_support_unclear_unique_ratio": float(min_ratio),
        }

    placeholders = ",".join(["?"] * len(parties))
    params: list[Any] = [str(source_id), *parties]
    rows = conn.execute(
        f"""
        SELECT
          p.full_name AS party_name,
          te.source_url,
          te.stance,
          LOWER(TRIM(REPLACE(REPLACE(REPLACE(COALESCE(te.excerpt, ''), CHAR(10), ' '), CHAR(13), ' '), '  ', ' '))) AS excerpt_norm
        FROM topic_evidence te
        JOIN persons p ON p.person_id = te.person_id
        WHERE te.source_id = ?
          AND p.full_name IN ({placeholders})
          AND te.stance IN ('support', 'unclear')
        ORDER BY p.full_name ASC, te.source_url ASC, te.evidence_id ASC
        """,
        params,
    ).fetchall()

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        party_name = str(row["party_name"] or "")
        source_url = str(row["source_url"] or "")
        if not party_name or not source_url:
            continue
        key = (party_name, source_url)
        if key not in grouped:
            grouped[key] = {
                "support_rows": 0,
                "unclear_rows": 0,
                "unclear_excerpts": [],
            }
        stance = str(row["stance"] or "").strip().lower()
        if stance == "support":
            grouped[key]["support_rows"] = int(grouped[key]["support_rows"]) + 1
            continue
        if stance == "unclear":
            grouped[key]["unclear_rows"] = int(grouped[key]["unclear_rows"]) + 1
            grouped[key]["unclear_excerpts"].append(str(row["excerpt_norm"] or ""))

    row_payloads: list[dict[str, Any]] = []
    below_threshold: list[dict[str, Any]] = []
    threshold = max(0.0, float(min_ratio))

    for party_name, source_url in sorted(grouped.keys()):
        group = grouped[(party_name, source_url)]
        unclear_rows = int(group["unclear_rows"] or 0)
        if unclear_rows <= 0:
            continue
        support_rows = int(group["support_rows"] or 0)
        unique_exact, unique_deduped = _collapse_unclear_unique_excerpts(
            excerpts=list(group["unclear_excerpts"] or []),
            near_duplicate_dedupe_enabled=bool(near_duplicate_dedupe_enabled),
            near_duplicate_jaccard_min=float(near_duplicate_jaccard_min),
            near_duplicate_containment_min=float(near_duplicate_containment_min),
            near_duplicate_ngram_size=int(near_duplicate_ngram_size),
        )
        ratio = (float(support_rows) / float(unique_deduped)) if unique_deduped > 0 else None
        near_duplicate_collapsed = max(0, unique_exact - unique_deduped)
        ratio = (
            float(ratio) if ratio is not None else None
        )
        payload = {
            "party_name": party_name,
            "source_url": source_url,
            "support_rows": support_rows,
            "unclear_rows": unclear_rows,
            "unclear_unique_exact_excerpt_rows": unique_exact,
            "unclear_near_duplicate_collapsed_rows": near_duplicate_collapsed,
            "unclear_unique_excerpt_rows": unique_deduped,
            "support_to_unclear_unique_ratio": ratio,
        }
        row_payloads.append(payload)
        if ratio is None or float(ratio) < threshold:
            below_threshold.append(payload)

    checks = {
        "rows_present": len(row_payloads) > 0,
        "ratio_threshold_met": len(below_threshold) == 0,
    }
    strict_fail_reasons: list[str] = []
    if not checks["rows_present"]:
        strict_fail_reasons.append("no_unclear_rows")
    if not checks["ratio_threshold_met"]:
        strict_fail_reasons.append("ratio_below_threshold")

    status = "ok" if len(strict_fail_reasons) == 0 else "degraded"
    return {
        "source_id": str(source_id),
        "parties": list(parties),
        "rows_total": len(row_payloads),
        "min_support_unclear_unique_ratio": float(threshold),
        "near_duplicate_dedupe": {
            "enabled": bool(near_duplicate_dedupe_enabled),
            "jaccard_min": float(max(0.0, near_duplicate_jaccard_min)),
            "containment_min": float(max(0.0, near_duplicate_containment_min)),
            "ngram_size": max(1, int(near_duplicate_ngram_size)),
        },
        "below_threshold_rows": below_threshold,
        "checks": checks,
        "status": status,
        "passed": status == "ok",
        "strict_fail_reasons": strict_fail_reasons,
        "rows": row_payloads,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "party_name",
                "source_url",
                "support_rows",
                "unclear_rows",
                "unclear_unique_exact_excerpt_rows",
                "unclear_near_duplicate_collapsed_rows",
                "unclear_unique_excerpt_rows",
                "support_to_unclear_unique_ratio",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["party_name"],
                    row["source_url"],
                    int(row["support_rows"]),
                    int(row["unclear_rows"]),
                    int(row.get("unclear_unique_exact_excerpt_rows") or 0),
                    int(row.get("unclear_near_duplicate_collapsed_rows") or 0),
                    int(row["unclear_unique_excerpt_rows"]),
                    "" if row["support_to_unclear_unique_ratio"] is None else f"{float(row['support_to_unclear_unique_ratio']):.6f}",
                ]
            )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    out_path = Path(args.out)
    csv_out = Path(args.csv_out) if str(args.csv_out or "").strip() else None
    parties = _parse_csv_list(str(args.parties or ""))
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2
    if not parties:
        print("ERROR: parties empty", file=sys.stderr)
        return 2

    with open_db(db_path) as conn:
        report = build_report(
            conn,
            source_id=str(args.source_id),
            parties=parties,
            min_ratio=float(args.min_support_unclear_unique_ratio),
            near_duplicate_dedupe_enabled=not bool(args.disable_near_duplicate_dedupe),
            near_duplicate_jaccard_min=float(args.near_duplicate_jaccard_min),
            near_duplicate_containment_min=float(args.near_duplicate_containment_min),
            near_duplicate_ngram_size=int(args.near_duplicate_ngram_size),
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    if csv_out is not None:
        _write_csv(csv_out, list(report.get("rows") or []))
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if bool(args.strict) and str(report.get("status")) != "ok":
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
