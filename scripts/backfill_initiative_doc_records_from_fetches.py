#!/usr/bin/env python3
"""Rehydrate initiative-doc records from successful document_fetches rows.

Use this to repair historical cases where:
- `document_fetches` says `fetched_ok=1` and has a `raw_path`, but
- `parl_initiative_documents.source_record_pk` is still NULL.

The backfill is local-only (no network):
1) upsert `source_records` keyed by `doc_url`,
2) upsert `text_documents` from `raw_path`,
3) relink `parl_initiative_documents.source_record_pk`.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow running as a standalone script from repo root without installation.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.db import open_db, upsert_source_records_with_content_sha256
from etl.politicos_es.util import normalize_ws, sha256_bytes


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
INITDOC_SOURCE_ID = "parl_initiative_docs"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (str(table),),
    ).fetchone()
    return row is not None


def _coverage(conn: sqlite3.Connection, *, source_id: str, initiative_source_id: str) -> dict[str, int]:
    where = ["i.source_id IS NOT NULL"]
    params: list[Any] = []
    if initiative_source_id:
        where.append("i.source_id = ?")
        params.append(initiative_source_id)

    row = conn.execute(
        f"""
        SELECT
          COUNT(*) AS total_doc_links,
          SUM(CASE WHEN d.source_record_pk IS NOT NULL THEN 1 ELSE 0 END) AS linked_doc_links,
          SUM(CASE WHEN d.source_record_pk IS NULL THEN 1 ELSE 0 END) AS missing_doc_links,
          SUM(CASE WHEN d.source_record_pk IS NULL AND COALESCE(df.fetched_ok, 0) = 1 THEN 1 ELSE 0 END) AS fetched_ok_missing_doc_links,
          SUM(CASE WHEN d.source_record_pk IS NULL AND COALESCE(df.fetched_ok, 0) = 1 AND TRIM(COALESCE(df.raw_path, '')) <> '' THEN 1 ELSE 0 END) AS fetched_ok_missing_doc_links_with_raw_path
        FROM parl_initiative_documents d
        JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
        LEFT JOIN document_fetches df ON df.doc_url = d.doc_url AND df.source_id = ?
        WHERE {' AND '.join(where)}
        """,
        [source_id, *params],
    ).fetchone()
    if row is None:
        return {
            "total_doc_links": 0,
            "linked_doc_links": 0,
            "missing_doc_links": 0,
            "fetched_ok_missing_doc_links": 0,
            "fetched_ok_missing_doc_links_with_raw_path": 0,
        }

    return {
        "total_doc_links": int(row["total_doc_links"] or 0),
        "linked_doc_links": int(row["linked_doc_links"] or 0),
        "missing_doc_links": int(row["missing_doc_links"] or 0),
        "fetched_ok_missing_doc_links": int(row["fetched_ok_missing_doc_links"] or 0),
        "fetched_ok_missing_doc_links_with_raw_path": int(row["fetched_ok_missing_doc_links_with_raw_path"] or 0),
    }


def _candidate_rows(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    initiative_source_id: str,
    limit: int,
) -> list[sqlite3.Row]:
    where = [
        "d.source_record_pk IS NULL",
        "COALESCE(df.fetched_ok, 0) = 1",
        "TRIM(COALESCE(df.raw_path, '')) <> ''",
        "TRIM(COALESCE(d.doc_url, '')) <> ''",
        "d.doc_url LIKE 'http%'",
    ]
    params: list[Any] = [source_id]
    if initiative_source_id:
        where.append("i.source_id = ?")
        params.append(initiative_source_id)

    limit_sql = ""
    if int(limit) > 0:
        limit_sql = " LIMIT ?"
        params.append(int(limit))

    return conn.execute(
        f"""
        SELECT
          d.doc_url,
          MAX(COALESCE(df.content_type, '')) AS content_type,
          MAX(COALESCE(df.content_sha256, '')) AS content_sha256,
          MAX(COALESCE(df.bytes, 0)) AS bytes,
          MAX(COALESCE(df.raw_path, '')) AS raw_path,
          MAX(COALESCE(df.last_attempt_at, df.first_attempt_at, '')) AS fetched_at,
          COUNT(*) AS refs
        FROM parl_initiative_documents d
        JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
        JOIN document_fetches df ON df.doc_url = d.doc_url AND df.source_id = ?
        WHERE {' AND '.join(where)}
        GROUP BY d.doc_url
        ORDER BY d.doc_url ASC
        {limit_sql}
        """,
        params,
    ).fetchall()


def _guess_content_type(raw_path: str, current_content_type: str) -> str | None:
    ct = _norm(current_content_type)
    if ct:
        return ct
    suffix = Path(raw_path).suffix.lower()
    if suffix in {".html", ".htm", ".xhtml"}:
        return "text/html"
    if suffix == ".xml":
        return "application/xml"
    if suffix == ".pdf":
        return "application/pdf"
    return None


def _to_text_excerpt(payload: bytes, *, content_type: str | None, raw_path: str) -> tuple[str | None, int | None]:
    ct = _norm(content_type)
    suffix = Path(raw_path).suffix.lower()
    is_markup = ("html" in ct) or ("xml" in ct) or (suffix in {".html", ".htm", ".xhtml", ".xml"})
    if not is_markup:
        return None, None
    text = payload.decode("utf-8", errors="replace")
    stripped = _TAG_RE.sub(" ", text)
    cleaned = _WS_RE.sub(" ", stripped).strip()
    if not cleaned:
        return None, None
    return cleaned[:4000], len(cleaned)


def backfill(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    initiative_source_id: str,
    snapshot_date: str | None,
    limit: int,
    dry_run: bool,
) -> dict[str, Any]:
    if not _table_exists(conn, "document_fetches"):
        raise RuntimeError("document_fetches table is required")

    now_iso = now_utc_iso()
    before = _coverage(conn, source_id=source_id, initiative_source_id=initiative_source_id)
    candidates = _candidate_rows(
        conn,
        source_id=source_id,
        initiative_source_id=initiative_source_id,
        limit=int(limit),
    )

    refs_total = int(sum(int(r["refs"] or 0) for r in candidates))
    sample_urls = [str(r["doc_url"] or "") for r in candidates[:20]]

    existing_sr_map: dict[str, int] = {}
    if candidates:
        urls = [str(r["doc_url"]) for r in candidates]
        chunk = 400
        for i in range(0, len(urls), chunk):
            batch = urls[i : i + chunk]
            qmarks = ",".join("?" for _ in batch)
            rows = conn.execute(
                f"""
                SELECT source_record_id, source_record_pk
                FROM source_records
                WHERE source_id = ?
                  AND source_record_id IN ({qmarks})
                """,
                [source_id, *batch],
            ).fetchall()
            for row in rows:
                existing_sr_map[str(row["source_record_id"])] = int(row["source_record_pk"])

    candidate_urls_total = len(candidates)
    missing_raw_file_total = 0
    unreadable_raw_file_total = 0
    content_sha_mismatch_total = 0
    usable_candidates_total = 0
    bytes_read_total = 0

    source_rows: list[dict[str, Any]] = []
    text_rows: list[dict[str, Any]] = []

    for row in candidates:
        doc_url = _norm(row["doc_url"])
        raw_path = _norm(row["raw_path"])
        if not doc_url or not raw_path:
            continue

        raw_file = Path(raw_path)
        if not raw_file.exists() or not raw_file.is_file():
            missing_raw_file_total += 1
            continue

        try:
            payload = raw_file.read_bytes()
        except Exception:  # noqa: BLE001
            unreadable_raw_file_total += 1
            continue

        if not payload:
            unreadable_raw_file_total += 1
            continue

        content_sha = sha256_bytes(payload)
        old_sha = _norm(row["content_sha256"])
        if old_sha and old_sha != content_sha:
            content_sha_mismatch_total += 1

        content_type = _guess_content_type(raw_path, _norm(row["content_type"]))
        excerpt, text_chars = _to_text_excerpt(payload, content_type=content_type, raw_path=raw_path)
        fetched_at = _norm(row["fetched_at"]) or now_iso
        bytes_len = len(payload)

        source_rows.append(
            {
                "source_record_id": doc_url,
                "raw_payload": json.dumps(
                    {
                        "url": doc_url,
                        "snapshot_date": _norm(snapshot_date),
                        "record_kind": "initiative_doc_rehydrated_from_fetch_status",
                        "rehydrated_from": "document_fetches",
                        "fetched_at": fetched_at,
                        "raw_path": raw_path,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "content_sha256": content_sha,
            }
        )
        text_rows.append(
            {
                "source_url": doc_url,
                "fetched_at": fetched_at,
                "content_type": content_type,
                "content_sha256": content_sha,
                "bytes": bytes_len,
                "raw_path": raw_path,
                "text_excerpt": excerpt,
                "text_chars": text_chars,
            }
        )

        usable_candidates_total += 1
        bytes_read_total += bytes_len

    source_record_map: dict[str, int] = dict(existing_sr_map)
    source_records_upserted = 0
    source_records_created = 0
    source_records_reused = 0
    text_documents_upserted = 0
    mapping_rows_updated = 0

    if not dry_run and source_rows:
        with conn:
            upsert_map = upsert_source_records_with_content_sha256(
                conn,
                source_id=source_id,
                rows=source_rows,
                snapshot_date=_norm(snapshot_date) or None,
                now_iso=now_iso,
            )
            source_record_map.update(upsert_map)
            source_records_upserted = len(upsert_map)

            for row in source_rows:
                url = str(row["source_record_id"])
                if url in existing_sr_map:
                    source_records_reused += 1
                elif url in upsert_map:
                    source_records_created += 1

            params: list[tuple[Any, ...]] = []
            for row in text_rows:
                url = str(row["source_url"])
                source_record_pk = source_record_map.get(url)
                if source_record_pk is None:
                    continue
                params.append(
                    (
                        source_id,
                        url,
                        int(source_record_pk),
                        str(row["fetched_at"]),
                        row["content_type"],
                        str(row["content_sha256"]),
                        int(row["bytes"]),
                        str(row["raw_path"]),
                        row["text_excerpt"],
                        int(row["text_chars"]) if row["text_chars"] is not None else None,
                        now_iso,
                        now_iso,
                    )
                )

            if params:
                conn.executemany(
                    """
                    INSERT INTO text_documents (
                      source_id, source_url, source_record_pk,
                      fetched_at, content_type, content_sha256, bytes, raw_path,
                      text_excerpt, text_chars,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_record_pk) DO UPDATE SET
                      source_url = excluded.source_url,
                      fetched_at = excluded.fetched_at,
                      content_type = excluded.content_type,
                      content_sha256 = excluded.content_sha256,
                      bytes = excluded.bytes,
                      raw_path = excluded.raw_path,
                      text_excerpt = CASE
                        WHEN excluded.text_excerpt IS NOT NULL AND TRIM(excluded.text_excerpt) <> '' THEN excluded.text_excerpt
                        ELSE text_documents.text_excerpt
                      END,
                      text_chars = CASE
                        WHEN excluded.text_chars IS NOT NULL AND excluded.text_chars > 0 THEN excluded.text_chars
                        ELSE text_documents.text_chars
                      END,
                      updated_at = excluded.updated_at
                    """,
                    params,
                )
                text_documents_upserted = len(params)

            for url, source_record_pk in source_record_map.items():
                if not url:
                    continue
                cur = conn.execute(
                    """
                    UPDATE parl_initiative_documents
                    SET source_record_pk = ?, updated_at = ?
                    WHERE source_record_pk IS NULL
                      AND doc_url = ?
                    """,
                    (int(source_record_pk), now_iso, url),
                )
                mapping_rows_updated += int(cur.rowcount or 0)

    after = _coverage(conn, source_id=source_id, initiative_source_id=initiative_source_id)

    return {
        "generated_at": now_iso,
        "source_id": source_id,
        "initiative_source_id": initiative_source_id,
        "snapshot_date": _norm(snapshot_date),
        "dry_run": bool(dry_run),
        "candidate_urls_total": candidate_urls_total,
        "candidate_refs_total": refs_total,
        "usable_candidates_total": usable_candidates_total,
        "missing_raw_file_total": missing_raw_file_total,
        "unreadable_raw_file_total": unreadable_raw_file_total,
        "content_sha_mismatch_total": content_sha_mismatch_total,
        "bytes_read_total": bytes_read_total,
        "source_records_upserted": source_records_upserted,
        "source_records_created": source_records_created,
        "source_records_reused": source_records_reused,
        "text_documents_upserted": text_documents_upserted,
        "mapping_rows_updated": mapping_rows_updated,
        "coverage_before": before,
        "coverage_after": after,
        "sample_urls": sample_urls,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Rehydrate initiative-doc source_records/text_documents from successful document_fetches")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    ap.add_argument("--source-id", default=INITDOC_SOURCE_ID, help="document/source source_id")
    ap.add_argument(
        "--initiative-source-id",
        default="",
        help="Optional parl_initiatives.source_id filter (e.g. senado_iniciativas)",
    )
    ap.add_argument("--snapshot-date", default="", help="Optional snapshot date for source_records")
    ap.add_argument("--limit", type=int, default=0, help="0 means no limit")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="", help="Optional JSON output path")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2

    conn = open_db(db_path)
    try:
        report = backfill(
            conn,
            source_id=_norm(args.source_id) or INITDOC_SOURCE_ID,
            initiative_source_id=_norm(args.initiative_source_id),
            snapshot_date=_norm(args.snapshot_date),
            limit=int(args.limit),
            dry_run=bool(args.dry_run),
        )
    finally:
        conn.close()

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    out = _norm(args.out)
    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
