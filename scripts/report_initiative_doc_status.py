#!/usr/bin/env python3
"""Deterministic status report for initiative document ingestion.

This report combines:
- link coverage (`parl_initiative_documents`)
- download coverage (`text_documents`)
- fetch traceability and error buckets (`document_fetches`)
- linked-to-votes download coverage
- excerpt coverage for downloaded docs
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
_ENM_CANTIDAD_RE = re.compile(
    r"<enmCantidad>\s*(?:<!\[CDATA\[(?P<cdata>.*?)\]\]>|(?P<plain>[^<]*))\s*</enmCantidad>",
    re.I | re.S,
)
_ENM_URL_RE = re.compile(
    r"<enmURL>\s*(?:<!\[CDATA\[(?P<cdata>.*?)\]\]>|(?P<plain>[^<]*))\s*</enmURL>",
    re.I | re.S,
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_source_ids(csv_value: str) -> list[str]:
    vals = [x.strip() for x in str(csv_value or "").split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for v in vals:
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Initiative document ingestion status report")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument(
        "--initiative-source-ids",
        default="congreso_iniciativas,senado_iniciativas",
        help="CSV of parl_initiatives.source_id values",
    )
    p.add_argument("--doc-source-id", default="parl_initiative_docs", help="text_documents/document_fetches source_id")
    p.add_argument(
        "--missing-sample-limit",
        type=int,
        default=20,
        help="Sample size for missing URL list per source (0 disables)",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args()


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (str(table),),
    ).fetchone()
    return row is not None


def _base_counts(
    conn: sqlite3.Connection,
    *,
    source_ids: list[str],
    doc_source_id: str,
) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in source_ids)
    return conn.execute(
        f"""
        SELECT
          i.source_id AS source_id,
          COUNT(DISTINCT i.initiative_id) AS initiatives_total,
          COUNT(DISTINCT CASE WHEN (
            (i.links_bocg_json IS NOT NULL AND TRIM(i.links_bocg_json) <> '')
            OR (i.links_ds_json IS NOT NULL AND TRIM(i.links_ds_json) <> '')
          ) THEN i.initiative_id END) AS initiatives_with_doc_links,
          COUNT(DISTINCT d.initiative_document_id) AS total_doc_links,
          SUM(CASE WHEN td.source_record_pk IS NOT NULL THEN 1 ELSE 0 END) AS downloaded_doc_links,
          SUM(CASE WHEN td.source_record_pk IS NOT NULL AND td.text_excerpt IS NOT NULL AND TRIM(td.text_excerpt) <> '' THEN 1 ELSE 0 END) AS downloaded_with_excerpt,
          SUM(CASE WHEN td.source_record_pk IS NOT NULL AND (td.text_excerpt IS NULL OR TRIM(td.text_excerpt) = '') THEN 1 ELSE 0 END) AS downloaded_missing_excerpt,
          SUM(CASE WHEN df.doc_url IS NOT NULL THEN 1 ELSE 0 END) AS doc_links_with_fetch_status
        FROM parl_initiatives i
        LEFT JOIN parl_initiative_documents d ON d.initiative_id = i.initiative_id
        LEFT JOIN text_documents td ON td.source_record_pk = d.source_record_pk AND td.source_id = ?
        LEFT JOIN document_fetches df ON df.doc_url = d.doc_url AND df.source_id = ?
        WHERE i.source_id IN ({placeholders})
        GROUP BY i.source_id
        ORDER BY i.source_id
        """,
        (doc_source_id, doc_source_id, *source_ids),
    ).fetchall()


def _extraction_counts(
    conn: sqlite3.Connection,
    *,
    source_ids: list[str],
    doc_source_id: str,
) -> dict[str, dict[str, int]]:
    if not _table_exists(conn, "parl_initiative_doc_extractions"):
        return {}

    placeholders = ",".join("?" for _ in source_ids)
    rows = conn.execute(
        f"""
        SELECT
          i.source_id AS source_id,
          SUM(CASE WHEN td.source_record_pk IS NOT NULL AND ex.source_record_pk IS NOT NULL THEN 1 ELSE 0 END) AS downloaded_with_extraction,
          SUM(CASE WHEN td.source_record_pk IS NOT NULL AND ex.source_record_pk IS NOT NULL AND ex.needs_review = 1 THEN 1 ELSE 0 END) AS extraction_needs_review
        FROM parl_initiatives i
        LEFT JOIN parl_initiative_documents d ON d.initiative_id = i.initiative_id
        LEFT JOIN text_documents td ON td.source_record_pk = d.source_record_pk AND td.source_id = ?
        LEFT JOIN parl_initiative_doc_extractions ex ON ex.source_record_pk = td.source_record_pk AND ex.source_id = ?
        WHERE i.source_id IN ({placeholders})
        GROUP BY i.source_id
        ORDER BY i.source_id
        """,
        (doc_source_id, doc_source_id, *source_ids),
    ).fetchall()

    out: dict[str, dict[str, int]] = {}
    for r in rows:
        sid = str(r["source_id"] or "")
        out[sid] = {
            "downloaded_with_extraction": int(r["downloaded_with_extraction"] or 0),
            "extraction_needs_review": int(r["extraction_needs_review"] or 0),
        }
    return out


def _linked_to_votes_counts(
    conn: sqlite3.Connection,
    *,
    source_ids: list[str],
    doc_source_id: str,
) -> dict[str, dict[str, int]]:
    placeholders = ",".join("?" for _ in source_ids)
    rows = conn.execute(
        f"""
        SELECT
          i.source_id AS source_id,
          COUNT(DISTINCT i.initiative_id) AS linked_total,
          COUNT(DISTINCT CASE WHEN EXISTS (
            SELECT 1
            FROM parl_initiative_documents d2
            JOIN text_documents td2 ON td2.source_record_pk = d2.source_record_pk
            WHERE d2.initiative_id = i.initiative_id
              AND td2.source_id = ?
          ) THEN i.initiative_id END) AS linked_with_downloaded_docs
        FROM parl_initiatives i
        JOIN parl_vote_event_initiatives vi ON vi.initiative_id = i.initiative_id
        WHERE i.source_id IN ({placeholders})
        GROUP BY i.source_id
        """,
        (doc_source_id, *source_ids),
    ).fetchall()
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        sid = str(r["source_id"] or "")
        out[sid] = {
            "linked_total": int(r["linked_total"] or 0),
            "linked_with_downloaded_docs": int(r["linked_with_downloaded_docs"] or 0),
        }
    return out


def _status_buckets(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    doc_source_id: str,
) -> list[dict[str, int]]:
    rows = conn.execute(
        """
        SELECT
          COALESCE(df.last_http_status, 0) AS status,
          COUNT(*) AS count
        FROM parl_initiative_documents d
        JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
        LEFT JOIN text_documents td ON td.source_record_pk = d.source_record_pk AND td.source_id = ?
        LEFT JOIN document_fetches df ON df.doc_url = d.doc_url AND df.source_id = ?
        WHERE i.source_id = ?
          AND td.source_record_pk IS NULL
        GROUP BY COALESCE(df.last_http_status, 0)
        ORDER BY count DESC, status DESC
        """,
        (doc_source_id, doc_source_id, source_id),
    ).fetchall()
    return [{"status": int(r["status"] or 0), "count": int(r["count"] or 0)} for r in rows]


def _missing_sample(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    doc_source_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    rows = conn.execute(
        """
        SELECT
          d.initiative_id,
          d.doc_kind,
          d.doc_url,
          COALESCE(df.last_http_status, 0) AS last_http_status,
          COALESCE(df.attempts, 0) AS attempts,
          COALESCE(df.last_attempt_at, '') AS last_attempt_at
        FROM parl_initiative_documents d
        JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
        LEFT JOIN text_documents td ON td.source_record_pk = d.source_record_pk AND td.source_id = ?
        LEFT JOIN document_fetches df ON df.doc_url = d.doc_url AND df.source_id = ?
        WHERE i.source_id = ?
          AND td.source_record_pk IS NULL
        ORDER BY
          COALESCE(df.last_http_status, 0) DESC,
          COALESCE(df.attempts, 0) DESC,
          d.initiative_id ASC,
          d.doc_kind ASC,
          d.doc_url ASC
        LIMIT ?
        """,
        (doc_source_id, doc_source_id, source_id, int(limit)),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "initiative_id": str(r["initiative_id"] or ""),
                "doc_kind": str(r["doc_kind"] or ""),
                "doc_url": str(r["doc_url"] or ""),
                "last_http_status": int(r["last_http_status"] or 0),
                "attempts": int(r["attempts"] or 0),
                "last_attempt_at": str(r["last_attempt_at"] or ""),
            }
        )
    return out


def _doc_kind_breakdown(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    doc_source_id: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          d.doc_kind AS doc_kind,
          COUNT(*) AS total_links,
          SUM(CASE WHEN td.source_record_pk IS NOT NULL THEN 1 ELSE 0 END) AS downloaded_links,
          SUM(CASE WHEN td.source_record_pk IS NULL THEN 1 ELSE 0 END) AS missing_links
        FROM parl_initiative_documents d
        JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
        LEFT JOIN text_documents td ON td.source_record_pk = d.source_record_pk AND td.source_id = ?
        WHERE i.source_id = ?
        GROUP BY d.doc_kind
        ORDER BY d.doc_kind
        """,
        (doc_source_id, source_id),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        total = int(r["total_links"] or 0)
        downloaded = int(r["downloaded_links"] or 0)
        out.append(
            {
                "doc_kind": str(r["doc_kind"] or ""),
                "total_links": total,
                "downloaded_links": downloaded,
                "missing_links": int(r["missing_links"] or 0),
                "downloaded_pct": round((100.0 * downloaded / total), 2) if total else 0.0,
            }
        )
    return out


def _parse_ini_enmiendas_meta(raw_path: str) -> dict[str, Any]:
    token = str(raw_path or "").strip()
    if not token:
        return {"state": "no_ini_raw_path"}
    p = Path(token)
    if not p.exists():
        return {"state": "ini_raw_path_missing", "raw_path": token}
    try:
        text = p.read_bytes().decode("latin-1", errors="replace")
    except OSError:
        return {"state": "ini_read_error", "raw_path": token}
    m_cant = _ENM_CANTIDAD_RE.search(text)
    m_url = _ENM_URL_RE.search(text)
    enm_cantidad = ""
    if m_cant:
        enm_cantidad = str(m_cant.group("cdata") or m_cant.group("plain") or "").strip()
    enm_url = ""
    if m_url:
        enm_url = html_lib.unescape(str(m_url.group("cdata") or m_url.group("plain") or "").strip())
    return {
        "state": "ok",
        "raw_path": token,
        "enm_cantidad": enm_cantidad,
        "enm_url": enm_url,
    }


def _senado_global_enmiendas_analysis(
    conn: sqlite3.Connection,
    *,
    doc_source_id: str,
    sample_limit: int,
) -> dict[str, Any]:
    rows = conn.execute(
        """
        WITH ini_docs AS (
          SELECT
            pid.initiative_id,
            MIN(td.raw_path) AS ini_raw_path
          FROM parl_initiative_documents pid
          JOIN parl_initiatives i2 ON i2.initiative_id = pid.initiative_id
          JOIN text_documents td ON td.source_record_pk = pid.source_record_pk
          WHERE i2.source_id = 'senado_iniciativas'
            AND td.source_id = ?
            AND pid.doc_url LIKE '%/xml/INI-3-%'
          GROUP BY pid.initiative_id
        ),
        downloaded_bocg_alt AS (
          SELECT
            pid.initiative_id,
            SUM(
              CASE
                WHEN pid.doc_kind = 'bocg'
                  AND (
                    pid.doc_url LIKE '%/xml/INI-3-%'
                    OR pid.doc_url LIKE '%/publicaciones/pdf/senado/bocg/%'
                    OR pid.doc_url LIKE '%tipoFich=3%'
                  )
                THEN 1
                ELSE 0
              END
            ) AS downloaded_bocg_alt_count
          FROM parl_initiative_documents pid
          JOIN parl_initiatives i2 ON i2.initiative_id = pid.initiative_id
          JOIN text_documents td ON td.source_record_pk = pid.source_record_pk
          WHERE i2.source_id = 'senado_iniciativas'
            AND td.source_id = ?
          GROUP BY pid.initiative_id
        ),
        detail_docs AS (
          SELECT
            pid.initiative_id,
            MIN(td.raw_path) AS detail_raw_path
          FROM parl_initiative_documents pid
          JOIN parl_initiatives i2 ON i2.initiative_id = pid.initiative_id
          JOIN text_documents td ON td.source_record_pk = pid.source_record_pk
          WHERE i2.source_id = 'senado_iniciativas'
            AND td.source_id = ?
            AND pid.doc_url LIKE '%tipoFich=3%'
          GROUP BY pid.initiative_id
        )
        SELECT
          d.initiative_id,
          d.doc_url,
          COALESCE(df.last_http_status, 0) AS last_http_status,
          COALESCE(df.attempts, 0) AS attempts,
          COALESCE(df.last_attempt_at, '') AS last_attempt_at,
          COALESCE(ini.ini_raw_path, '') AS ini_raw_path,
          COALESCE(dd.detail_raw_path, '') AS detail_raw_path,
          COALESCE(alt.downloaded_bocg_alt_count, 0) AS downloaded_bocg_alt_count
        FROM parl_initiative_documents d
        JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
        LEFT JOIN text_documents td ON td.source_record_pk = d.source_record_pk AND td.source_id = ?
        LEFT JOIN document_fetches df ON df.doc_url = d.doc_url AND df.source_id = ?
        LEFT JOIN ini_docs ini ON ini.initiative_id = d.initiative_id
        LEFT JOIN downloaded_bocg_alt alt ON alt.initiative_id = d.initiative_id
        LEFT JOIN detail_docs dd ON dd.initiative_id = d.initiative_id
        WHERE i.source_id = 'senado_iniciativas'
          AND td.source_record_pk IS NULL
          AND d.doc_url LIKE '%global_enmiendas_vetos%'
        ORDER BY
          COALESCE(df.last_http_status, 0) DESC,
          COALESCE(df.attempts, 0) DESC,
          d.initiative_id ASC,
          d.doc_url ASC
        """,
        (doc_source_id, doc_source_id, doc_source_id, doc_source_id, doc_source_id),
    ).fetchall()

    meta_cache: dict[str, dict[str, Any]] = {}
    classification_counts: dict[str, int] = {}
    actionable_rows: list[dict[str, Any]] = []
    likely_not_expected = 0
    likely_not_expected_zero_enmiendas = 0
    likely_not_expected_redundant_global = 0
    no_ini_downloaded = 0

    def bump(key: str) -> None:
        classification_counts[key] = int(classification_counts.get(key, 0)) + 1

    for r in rows:
        initiative_id = str(r["initiative_id"] or "")
        doc_url = str(r["doc_url"] or "")
        status = int(r["last_http_status"] or 0)
        attempts = int(r["attempts"] or 0)
        last_attempt_at = str(r["last_attempt_at"] or "")
        ini_raw_path = str(r["ini_raw_path"] or "").strip()
        detail_raw_path = str(r["detail_raw_path"] or "").strip()
        downloaded_bocg_alt_count = int(r["downloaded_bocg_alt_count"] or 0)
        meta_source = ini_raw_path or detail_raw_path

        enm_cantidad = ""
        enm_url = ""
        state = ""
        if downloaded_bocg_alt_count <= 0:
            meta = meta_cache.get(meta_source)
            if meta is None:
                meta = _parse_ini_enmiendas_meta(meta_source)
                meta_cache[meta_source] = meta
            enm_cantidad = str(meta.get("enm_cantidad") or "").strip()
            enm_url = str(meta.get("enm_url") or "").strip()
            state = str(meta.get("state") or "")

        classification = ""
        if downloaded_bocg_alt_count > 0:
            classification = "likely_not_expected_redundant_global_url"
            likely_not_expected += 1
            likely_not_expected_redundant_global += 1
        elif not meta_source:
            classification = "no_ini_downloaded"
            no_ini_downloaded += 1
        elif state != "ok":
            classification = state or "ini_meta_unavailable"
        elif enm_cantidad == "0":
            classification = "likely_not_expected_zero_enmiendas"
            likely_not_expected += 1
            likely_not_expected_zero_enmiendas += 1
        elif enm_cantidad:
            classification = "has_enmiendas_or_unknown"
        else:
            classification = "no_enm_cantidad"

        bump(classification)
        if classification not in {
            "likely_not_expected_zero_enmiendas",
            "likely_not_expected_redundant_global_url",
        }:
            actionable_rows.append(
                {
                    "initiative_id": initiative_id,
                    "doc_url": doc_url,
                    "last_http_status": status,
                    "attempts": attempts,
                    "last_attempt_at": last_attempt_at,
                    "classification": classification,
                    "downloaded_bocg_alt_count": downloaded_bocg_alt_count,
                    "ini_raw_path": ini_raw_path,
                    "detail_raw_path": detail_raw_path,
                    "enm_cantidad": enm_cantidad,
                    "enm_url": enm_url,
                }
            )

    actionable_rows = sorted(
        actionable_rows,
        key=lambda x: (
            -int(x.get("last_http_status", 0)),
            -int(x.get("attempts", 0)),
            str(x.get("initiative_id", "")),
        ),
    )
    return {
        "total_global_enmiendas_missing": len(rows),
        "likely_not_expected_zero_enmiendas": int(likely_not_expected_zero_enmiendas),
        "likely_not_expected_redundant_global_url": int(likely_not_expected_redundant_global),
        "likely_not_expected_total": int(likely_not_expected),
        "actionable_missing_count": max(0, len(rows) - int(likely_not_expected)),
        "no_ini_downloaded": int(no_ini_downloaded),
        "classification_counts": classification_counts,
        "actionable_missing_sample": actionable_rows[: max(0, int(sample_limit))],
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2

    source_ids = parse_source_ids(args.initiative_source_ids)
    if not source_ids:
        print(json.dumps({"error": "initiative-source-ids empty"}, ensure_ascii=False))
        return 2

    doc_source_id = str(args.doc_source_id or "").strip() or "parl_initiative_docs"

    with open_db(db_path) as conn:
        base_rows = _base_counts(conn, source_ids=source_ids, doc_source_id=doc_source_id)
        extraction = _extraction_counts(conn, source_ids=source_ids, doc_source_id=doc_source_id)
        linked = _linked_to_votes_counts(conn, source_ids=source_ids, doc_source_id=doc_source_id)

        by_source: dict[str, Any] = {}
        for r in base_rows:
            sid = str(r["source_id"] or "")
            initiatives_total = int(r["initiatives_total"] or 0)
            initiatives_with_doc_links = int(r["initiatives_with_doc_links"] or 0)
            total_doc_links = int(r["total_doc_links"] or 0)
            downloaded_doc_links = int(r["downloaded_doc_links"] or 0)
            downloaded_with_excerpt = int(r["downloaded_with_excerpt"] or 0)
            downloaded_missing_excerpt = int(r["downloaded_missing_excerpt"] or 0)
            doc_links_with_fetch_status = int(r["doc_links_with_fetch_status"] or 0)
            downloaded_with_extraction = int(extraction.get(sid, {}).get("downloaded_with_extraction", 0))
            extraction_needs_review = int(extraction.get(sid, {}).get("extraction_needs_review", 0))
            downloaded_missing_extraction = max(0, downloaded_doc_links - downloaded_with_extraction)

            linked_total = int(linked.get(sid, {}).get("linked_total", 0))
            linked_with_downloaded_docs = int(linked.get(sid, {}).get("linked_with_downloaded_docs", 0))

            by_source[sid] = {
                "initiatives_total": initiatives_total,
                "initiatives_with_doc_links": initiatives_with_doc_links,
                "initiatives_with_doc_links_pct": round((100.0 * initiatives_with_doc_links / initiatives_total), 2)
                if initiatives_total
                else 0.0,
                "total_doc_links": total_doc_links,
                "downloaded_doc_links": downloaded_doc_links,
                "missing_doc_links": max(0, total_doc_links - downloaded_doc_links),
                "downloaded_doc_links_pct": round((100.0 * downloaded_doc_links / total_doc_links), 2)
                if total_doc_links
                else 0.0,
                "doc_links_with_fetch_status": doc_links_with_fetch_status,
                "doc_links_missing_fetch_status": max(0, total_doc_links - doc_links_with_fetch_status),
                "fetch_status_coverage_pct": round((100.0 * doc_links_with_fetch_status / total_doc_links), 2)
                if total_doc_links
                else 0.0,
                "downloaded_with_excerpt": downloaded_with_excerpt,
                "downloaded_missing_excerpt": downloaded_missing_excerpt,
                "excerpt_coverage_pct": round((100.0 * downloaded_with_excerpt / downloaded_doc_links), 2)
                if downloaded_doc_links
                else 0.0,
                "downloaded_with_extraction": downloaded_with_extraction,
                "downloaded_missing_extraction": downloaded_missing_extraction,
                "extraction_coverage_pct": round((100.0 * downloaded_with_extraction / downloaded_doc_links), 2)
                if downloaded_doc_links
                else 0.0,
                "extraction_needs_review": extraction_needs_review,
                "extraction_needs_review_pct": round((100.0 * extraction_needs_review / downloaded_with_extraction), 2)
                if downloaded_with_extraction
                else 0.0,
                "linked_to_votes_total": linked_total,
                "linked_to_votes_with_downloaded_docs": linked_with_downloaded_docs,
                "linked_to_votes_with_downloaded_docs_pct": round((100.0 * linked_with_downloaded_docs / linked_total), 2)
                if linked_total
                else 0.0,
                "missing_status_buckets": _status_buckets(conn, source_id=sid, doc_source_id=doc_source_id),
                "missing_urls_sample": _missing_sample(
                    conn,
                    source_id=sid,
                    doc_source_id=doc_source_id,
                    limit=int(args.missing_sample_limit or 0),
                ),
                "doc_kind_breakdown": _doc_kind_breakdown(conn, source_id=sid, doc_source_id=doc_source_id),
            }

            if sid == "senado_iniciativas":
                senado_analysis = _senado_global_enmiendas_analysis(
                    conn,
                    doc_source_id=doc_source_id,
                    sample_limit=int(args.missing_sample_limit or 0),
                )
                likely_not_expected = min(
                    int(by_source[sid]["missing_doc_links"]),
                    int(
                        senado_analysis.get(
                            "likely_not_expected_total",
                            senado_analysis.get("likely_not_expected_zero_enmiendas", 0),
                        )
                    ),
                )
                by_source[sid]["global_enmiendas_vetos_analysis"] = senado_analysis
                by_source[sid]["missing_doc_links_likely_not_expected"] = int(likely_not_expected)
                by_source[sid]["missing_doc_links_actionable"] = max(
                    0,
                    int(by_source[sid]["missing_doc_links"]) - int(likely_not_expected),
                )
            else:
                by_source[sid]["missing_doc_links_likely_not_expected"] = 0
                by_source[sid]["missing_doc_links_actionable"] = int(by_source[sid]["missing_doc_links"])

            adjusted_den = max(
                0,
                int(by_source[sid]["total_doc_links"]) - int(by_source[sid]["missing_doc_links_likely_not_expected"]),
            )
            by_source[sid]["effective_downloaded_doc_links_pct"] = round(
                (100.0 * int(by_source[sid]["downloaded_doc_links"]) / adjusted_den) if adjusted_den else 0.0,
                2,
            )

    overall = {
        "initiatives_total": 0,
        "initiatives_with_doc_links": 0,
        "total_doc_links": 0,
        "downloaded_doc_links": 0,
        "missing_doc_links": 0,
        "doc_links_with_fetch_status": 0,
        "doc_links_missing_fetch_status": 0,
        "downloaded_with_excerpt": 0,
        "downloaded_missing_excerpt": 0,
        "downloaded_with_extraction": 0,
        "downloaded_missing_extraction": 0,
        "extraction_needs_review": 0,
        "linked_to_votes_total": 0,
        "linked_to_votes_with_downloaded_docs": 0,
        "missing_doc_links_likely_not_expected": 0,
        "missing_doc_links_actionable": 0,
    }
    for values in by_source.values():
        for key in overall.keys():
            overall[key] += int(values.get(key, 0))

    overall["initiatives_with_doc_links_pct"] = round(
        (100.0 * overall["initiatives_with_doc_links"] / overall["initiatives_total"]) if overall["initiatives_total"] else 0.0,
        2,
    )
    overall["downloaded_doc_links_pct"] = round(
        (100.0 * overall["downloaded_doc_links"] / overall["total_doc_links"]) if overall["total_doc_links"] else 0.0,
        2,
    )
    overall["fetch_status_coverage_pct"] = round(
        (100.0 * overall["doc_links_with_fetch_status"] / overall["total_doc_links"]) if overall["total_doc_links"] else 0.0,
        2,
    )
    overall["excerpt_coverage_pct"] = round(
        (100.0 * overall["downloaded_with_excerpt"] / overall["downloaded_doc_links"]) if overall["downloaded_doc_links"] else 0.0,
        2,
    )
    overall["extraction_coverage_pct"] = round(
        (100.0 * overall["downloaded_with_extraction"] / overall["downloaded_doc_links"])
        if overall["downloaded_doc_links"]
        else 0.0,
        2,
    )
    overall["extraction_needs_review_pct"] = round(
        (100.0 * overall["extraction_needs_review"] / overall["downloaded_with_extraction"])
        if overall["downloaded_with_extraction"]
        else 0.0,
        2,
    )
    overall["linked_to_votes_with_downloaded_docs_pct"] = round(
        (100.0 * overall["linked_to_votes_with_downloaded_docs"] / overall["linked_to_votes_total"])
        if overall["linked_to_votes_total"]
        else 0.0,
        2,
    )
    adjusted_overall_den = max(0, overall["total_doc_links"] - overall["missing_doc_links_likely_not_expected"])
    overall["effective_downloaded_doc_links_pct"] = round(
        (100.0 * overall["downloaded_doc_links"] / adjusted_overall_den) if adjusted_overall_den else 0.0,
        2,
    )

    result = {
        "generated_at": now_utc_iso(),
        "db": str(db_path),
        "doc_source_id": doc_source_id,
        "initiative_source_ids": source_ids,
        "overall": overall,
        "by_source": by_source,
    }

    if args.out:
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
