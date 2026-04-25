#!/usr/bin/env python3
"""Export deterministic support-sample CSV for programas_partidos precision audits."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_PARTIES = "BNG,VOX,FORO Asturias,PP"
STRICT_FAIL_EXIT = 4
DEDUPE_KEYS = ("none", "content_sha256", "excerpt_norm", "source_url", "excerpt_norm+source_url")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    parser.add_argument("--source-id", default="programas_partidos")
    parser.add_argument(
        "--parties",
        default=DEFAULT_PARTIES,
        help=f"CSV party names (default: {DEFAULT_PARTIES})",
    )
    parser.add_argument("--per-party-limit", type=int, default=10, help="Rows per party (0=all)")
    parser.add_argument("--limit", type=int, default=0, help="Global output limit (0=all)")
    parser.add_argument("--excerpt-len", type=int, default=320, help="Excerpt length in CSV")
    parser.add_argument(
        "--excerpt-window-words",
        type=int,
        default=0,
        help="Deterministic window size in words for sampling excerpt diversity (0 disables)",
    )
    parser.add_argument(
        "--excerpt-window-stride",
        type=int,
        default=0,
        help="Window stride in words (0 => half of window size)",
    )
    parser.add_argument(
        "--excerpt-window-min-words",
        type=int,
        default=12,
        help="Minimum words required to emit a windowed excerpt",
    )
    parser.add_argument(
        "--dedupe-key",
        default="none",
        choices=DEDUPE_KEYS,
        help="Optional deterministic dedupe key for per-party sampling",
    )
    parser.add_argument(
        "--min-unique-per-party",
        type=int,
        default=0,
        help="Minimum unique rows per target party for summary check (0 disables)",
    )
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--summary-out", default="", help="Optional JSON summary output path")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless status=ok")
    return parser.parse_args(argv)


def _parse_parties(raw: str) -> list[str]:
    parts: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").split(","):
        party = token.strip()
        if not party:
            continue
        if party in seen:
            continue
        seen.add(party)
        parts.append(party)
    return parts


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _normalize_ws_local(raw: str) -> str:
    return " ".join(str(raw).split())


def _normalize_excerpt(raw: Any) -> str:
    txt = _normalize_ws_local(str(raw or "")).lower()
    return txt


def _dedupe_token(
    *,
    evidence_id: str,
    content_sha256: str,
    excerpt: str,
    source_url: str,
    dedupe_key: str,
) -> str:
    ev_id = str(evidence_id or "")
    if dedupe_key == "none":
        return f"evidence_id:{ev_id}"
    if dedupe_key == "content_sha256":
        sha = _normalize_ws_local(str(content_sha256 or "")).lower()
        if sha:
            return f"sha:{sha}"
        return f"missing_sha:{ev_id}"
    if dedupe_key == "excerpt_norm":
        return _normalize_excerpt(excerpt)
    src = _normalize_ws_local(str(source_url or "")).lower()
    if dedupe_key == "source_url":
        return src
    return f"{_normalize_excerpt(excerpt)}|{src}"


def _stable_text_seed(raw: str) -> int:
    txt = str(raw or "")
    if not txt:
        return 0
    seed = 0
    for ch in txt:
        seed = (seed * 131 + ord(ch)) % 2147483647
    return int(seed)


def _windowed_excerpt(
    *,
    evidence_id: str,
    excerpt: str,
    window_words: int,
    window_stride: int,
    min_words: int,
) -> tuple[str, int, int]:
    text = _normalize_ws_local(str(excerpt or ""))
    words = [w for w in text.split(" ") if w]
    wsize = max(0, int(window_words or 0))
    wmin = max(1, int(min_words or 1))
    if wsize <= 0 or len(words) < max(wsize, wmin):
        return text, 0, 1
    stride = max(1, int(window_stride or 0))
    if stride <= 1 and int(window_stride or 0) <= 0:
        stride = max(1, wsize // 2)
    windows: list[str] = []
    last_start = max(0, len(words) - wmin)
    for start in range(0, last_start + 1, stride):
        chunk = words[start : start + wsize]
        if len(chunk) < wmin:
            continue
        windows.append(" ".join(chunk))
    if not windows:
        return text, 0, 1
    try:
        seed = int(str(evidence_id).strip())
    except ValueError:
        seed = _stable_text_seed(str(evidence_id))
    idx = abs(int(seed)) % len(windows)
    return windows[idx], int(idx), len(windows)


def fetch_support_rows(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    parties: list[str],
    per_party_limit: int,
    limit: int,
    excerpt_len: int,
    dedupe_key: str,
    excerpt_window_words: int,
    excerpt_window_stride: int,
    excerpt_window_min_words: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not parties:
        return [], {
            "dedupe_key": str(dedupe_key),
            "candidate_total_before_dedupe": 0,
            "dropped_duplicates_total": 0,
            "dropped_duplicates_by_party": {},
        }
    placeholders = ",".join(["?"] * len(parties))
    per_limit = max(0, int(per_party_limit or 0))
    global_limit = max(0, int(limit or 0))
    sql_excerpt_len = max(1, int(excerpt_len or 320))
    if int(excerpt_window_words or 0) > 0:
        sql_excerpt_len = max(sql_excerpt_len, 4000)
    params: list[object] = [sql_excerpt_len, str(source_id), *parties]
    sql = f"""
    SELECT
      p.full_name AS party_name,
      te.source_url,
      te.evidence_id,
      te.source_record_pk,
      COALESCE(sr.content_sha256, '') AS content_sha256,
      SUBSTR(
        REPLACE(REPLACE(COALESCE(te.excerpt, ''), CHAR(10), ' '), CHAR(13), ' '),
        1,
        ?
      ) AS excerpt
    FROM topic_evidence te
    JOIN persons p ON p.person_id = te.person_id
    LEFT JOIN source_records sr ON sr.source_record_pk = te.source_record_pk
    WHERE te.source_id = ?
      AND te.stance = 'support'
      AND p.full_name IN ({placeholders})
    ORDER BY party_name ASC, source_url ASC, evidence_id ASC
    """
    candidates = conn.execute(sql, params).fetchall()
    selected: list[dict[str, Any]] = []
    party_counts: dict[str, int] = {}
    seen_keys_by_party: dict[str, set[str]] = {}
    dropped_duplicates_by_party: dict[str, int] = {}
    dropped_total = 0
    windowed_rows = 0
    for row in candidates:
        party = str(row["party_name"] or "")
        raw_excerpt = str(row["excerpt"] or "")
        sampled_excerpt, window_idx, window_count = _windowed_excerpt(
            evidence_id=str(row["evidence_id"] or ""),
            excerpt=raw_excerpt,
            window_words=int(excerpt_window_words or 0),
            window_stride=int(excerpt_window_stride or 0),
            min_words=int(excerpt_window_min_words or 0),
        )
        if int(window_count) > 1:
            windowed_rows += 1
        sampled_excerpt = sampled_excerpt[: max(1, int(excerpt_len or 320))]
        token = _dedupe_token(
            evidence_id=str(row["evidence_id"] or ""),
            content_sha256=str(row["content_sha256"] or ""),
            excerpt=sampled_excerpt,
            source_url=str(row["source_url"] or ""),
            dedupe_key=dedupe_key,
        )
        seen_party = seen_keys_by_party.setdefault(party, set())
        if token in seen_party:
            dropped_total += 1
            dropped_duplicates_by_party[party] = int(dropped_duplicates_by_party.get(party, 0)) + 1
            continue
        seen_party.add(token)
        if per_limit > 0 and int(party_counts.get(party, 0)) >= per_limit:
            continue
        if global_limit > 0 and len(selected) >= global_limit:
            break
        selected.append(
            {
                "party_name": party,
                "source_url": str(row["source_url"] or ""),
                "evidence_id": str(row["evidence_id"] or ""),
                "source_record_pk": str(row["source_record_pk"] or ""),
                "content_sha256": str(row["content_sha256"] or ""),
                "excerpt": sampled_excerpt,
                "window_index": int(window_idx),
                "window_count": int(window_count),
            }
        )
        party_counts[party] = int(party_counts.get(party, 0)) + 1
    meta = {
        "dedupe_key": str(dedupe_key),
        "candidate_total_before_dedupe": len(candidates),
        "dropped_duplicates_total": int(dropped_total),
        "dropped_duplicates_by_party": dropped_duplicates_by_party,
        "available_unique_by_party": {party: len(keys) for party, keys in seen_keys_by_party.items()},
        "excerpt_window_words": int(excerpt_window_words or 0),
        "excerpt_window_stride": int(excerpt_window_stride or 0),
        "excerpt_window_min_words": int(excerpt_window_min_words or 0),
        "windowed_rows_total": int(windowed_rows),
    }
    return selected, meta


def build_summary(
    *,
    rows: list[dict[str, Any]],
    parties: list[str],
    source_id: str,
    dedupe_key: str,
    min_unique_per_party: int,
    candidate_total_before_dedupe: int,
    dropped_duplicates_total: int,
    dropped_duplicates_by_party: dict[str, int],
    available_unique_by_party: dict[str, int],
    excerpt_window_words: int,
    excerpt_window_stride: int,
    excerpt_window_min_words: int,
    windowed_rows_total: int,
) -> dict[str, object]:
    by_party: dict[str, int] = {party: 0 for party in parties}
    for row in rows:
        party = str(row["party_name"] or "")
        by_party[party] = int(by_party.get(party, 0)) + 1
    missing_parties = [party for party in parties if int(by_party.get(party, 0)) <= 0]
    min_unique = max(0, int(min_unique_per_party or 0))
    unique_by_party = {party: int(by_party.get(party, 0)) for party in parties}
    available_unique = {party: int(available_unique_by_party.get(party, 0)) for party in parties}
    effective_min_unique_by_party = {
        party: min(int(min_unique), int(available_unique.get(party, 0))) for party in parties
    }
    parties_below_min_unique = [party for party in parties if int(unique_by_party.get(party, 0)) < min_unique]
    parties_below_effective_min_unique = [
        party
        for party in parties
        if int(unique_by_party.get(party, 0)) < int(effective_min_unique_by_party.get(party, 0))
    ]
    parties_capped_by_available_unique = [
        party for party in parties if int(available_unique.get(party, 0)) < int(min_unique)
    ]
    checks = {
        "required_parties_covered": len(missing_parties) == 0,
        "min_unique_per_party_met": len(parties_below_min_unique) == 0,
        "min_unique_per_party_effective_met": len(parties_below_effective_min_unique) == 0,
    }
    status = (
        "ok"
        if bool(checks["required_parties_covered"]) and bool(checks["min_unique_per_party_effective_met"])
        else "degraded"
    )
    reasons: list[str] = []
    if not checks["required_parties_covered"]:
        reasons.append("missing_parties")
    if not checks["min_unique_per_party_effective_met"]:
        reasons.append("min_unique_per_party_effective_not_met")
    return {
        "source_id": source_id,
        "dedupe_key": str(dedupe_key),
        "candidate_total_before_dedupe": int(candidate_total_before_dedupe),
        "dropped_duplicates_total": int(dropped_duplicates_total),
        "dropped_duplicates_by_party": dropped_duplicates_by_party,
        "excerpt_window_words": int(excerpt_window_words),
        "excerpt_window_stride": int(excerpt_window_stride),
        "excerpt_window_min_words": int(excerpt_window_min_words),
        "windowed_rows_total": int(windowed_rows_total),
        "sample_total": len(rows),
        "target_parties": parties,
        "by_party": by_party,
        "unique_by_party": unique_by_party,
        "available_unique_by_party": available_unique,
        "min_unique_per_party": min_unique,
        "effective_min_unique_per_party_by_party": effective_min_unique_by_party,
        "parties_below_min_unique": parties_below_min_unique,
        "parties_below_effective_min_unique": parties_below_effective_min_unique,
        "parties_capped_by_available_unique": parties_capped_by_available_unique,
        "missing_parties": missing_parties,
        "checks": checks,
        "status": status,
        "passed": status == "ok",
        "strict_fail_reasons": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    out_path = Path(args.out)
    summary_out = Path(args.summary_out) if str(args.summary_out or "").strip() else None
    parties = _parse_parties(str(args.parties or ""))
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2
    if not parties:
        print("ERROR: --parties empty after parsing", file=sys.stderr)
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if summary_out is not None:
        summary_out.parent.mkdir(parents=True, exist_ok=True)

    with open_db(db_path) as conn:
        rows, meta = fetch_support_rows(
            conn,
            source_id=str(args.source_id),
            parties=parties,
            per_party_limit=int(args.per_party_limit or 0),
            limit=int(args.limit or 0),
            excerpt_len=int(args.excerpt_len or 320),
            dedupe_key=str(args.dedupe_key),
            excerpt_window_words=int(args.excerpt_window_words or 0),
            excerpt_window_stride=int(args.excerpt_window_stride or 0),
            excerpt_window_min_words=int(args.excerpt_window_min_words or 0),
        )

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "sample_id",
                "party_name",
                "source_url",
                "evidence_id",
                "window_index",
                "window_count",
                "excerpt",
                "manual_label",
                "manual_note",
            ]
        )
        for idx, row in enumerate(rows, start=1):
            writer.writerow(
                [
                    f"S{idx:03d}",
                    str(row["party_name"] or ""),
                    str(row["source_url"] or ""),
                    str(row["evidence_id"] or ""),
                    int(row.get("window_index") or 0),
                    int(row.get("window_count") or 1),
                    str(row["excerpt"] or ""),
                    "",
                    "",
                ]
            )

    summary = build_summary(
        rows=rows,
        parties=parties,
        source_id=str(args.source_id),
        dedupe_key=str(args.dedupe_key),
        min_unique_per_party=int(args.min_unique_per_party or 0),
        candidate_total_before_dedupe=int(meta["candidate_total_before_dedupe"]),
        dropped_duplicates_total=int(meta["dropped_duplicates_total"]),
        dropped_duplicates_by_party=dict(meta["dropped_duplicates_by_party"]),
        available_unique_by_party=dict(meta["available_unique_by_party"]),
        excerpt_window_words=int(meta["excerpt_window_words"]),
        excerpt_window_stride=int(meta["excerpt_window_stride"]),
        excerpt_window_min_words=int(meta["excerpt_window_min_words"]),
        windowed_rows_total=int(meta["windowed_rows_total"]),
    )
    if summary_out is not None:
        summary_out.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"OK wrote {out_path} (rows={len(rows)})")
    if summary_out is not None:
        print(f"OK wrote {summary_out}")
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if bool(args.strict) and str(summary.get("status")) != "ok":
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
