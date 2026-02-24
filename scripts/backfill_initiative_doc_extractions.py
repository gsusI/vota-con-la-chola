#!/usr/bin/env python3
"""Backfill derived semantic extraction rows for initiative documents.

Reads downloaded `text_documents` rows linked to `parl_initiative_documents` and
stores deterministic heuristic outputs in `parl_initiative_doc_extractions`.

Purpose: make "what was voted" extraction state queryable/idempotent in SQLite
for downstream subagents and review workflows.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.util import normalize_ws, now_utc_iso, stable_json


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_INITIATIVE_SOURCE_IDS = "congreso_iniciativas,senado_iniciativas"
DEFAULT_EXTRACTOR_VERSION = "heuristic_subject_v2"

_KEYWORD_PATTERN = re.compile(
    r"((?:proyecto|proposici[oó]n|moci[oó]n|interpelaci[oó]n|pregunta|decreto-ley|real\s+decreto-ley|"
    r"tratado|convenio|acuerdo|enmienda|veto|dictamen|propuesta)"
    r"[^\.;:]{20,320})",
    re.I,
)
_SENTENCE_SPLIT_RE = re.compile(r"[\.;:!?]+")
_STRONG_TITLE_PATTERNS = (
    re.compile(r"\bproyecto\s+de\s+ley\b", re.I),
    re.compile(r"\bproposici[oó]n\s+de\s+ley\b", re.I),
    re.compile(r"\bley\s+org[aá]nica\b", re.I),
    re.compile(r"\breal\s+decreto-ley\b", re.I),
    re.compile(r"\bdecreto-ley\b", re.I),
    re.compile(r"\bconvenio\b", re.I),
    re.compile(r"\btratado\b", re.I),
    re.compile(r"\bacuerdo\b", re.I),
    re.compile(r"\bpropuesta\s+de\s+reforma\b", re.I),
    re.compile(r"\bproposici[oó]n\s+de\s+reforma\b", re.I),
    re.compile(r"\bmoci[oó]n\b", re.I),
    re.compile(r"\binterpelaci[oó]n\b", re.I),
    re.compile(r"\bpregunta\b", re.I),
    re.compile(r"\bdictamen\b", re.I),
    re.compile(r"\bprotocolo\b", re.I),
    re.compile(r"\bconvenci[oó]n\b", re.I),
    re.compile(r"\bacta(?:s)?\b", re.I),
    re.compile(r"\bmemor[aá]ndum\b", re.I),
    re.compile(r"\bmemorando\b", re.I),
    re.compile(r"\bdeclaraci[oó]n(?:es)?\b", re.I),
    re.compile(r"\bresoluci[oó]n(?:es)?\b", re.I),
    re.compile(r"\bdecisi[oó]n(?:es)?\b", re.I),
    re.compile(r"\bcanje\b", re.I),
    re.compile(r"\bcarta(?:s)?\b", re.I),
    re.compile(r"\btexto\s+refundido\b", re.I),
    re.compile(r"\bestatuto(?:s)?\b", re.I),
    re.compile(r"\binstrumento\b", re.I),
    re.compile(r"\bdenuncia\b", re.I),
    re.compile(r"\bretirada\b", re.I),
    re.compile(r"\bc[oó]digo\b", re.I),
    re.compile(r"\banejo(?:s)?\b", re.I),
    re.compile(r"\badenda\b", re.I),
    re.compile(r"\badhesi[oó]n\b", re.I),
    re.compile(r"\bextensi[oó]n\b", re.I),
    re.compile(r"\bsolicitud\b", re.I),
    re.compile(r"\bnota\b", re.I),
    re.compile(r"\bdocumento(?:s)?\b", re.I),
    re.compile(r"\bmodificaci[oó]n(?:es)?\b", re.I),
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill semantic initiative-doc extractions")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--doc-source-id", default="parl_initiative_docs", help="text_documents.source_id filter")
    p.add_argument(
        "--initiative-source-ids",
        default=DEFAULT_INITIATIVE_SOURCE_IDS,
        help="CSV of parl_initiatives.source_id values",
    )
    p.add_argument("--extractor-version", default=DEFAULT_EXTRACTOR_VERSION)
    p.add_argument("--limit", type=int, default=0, help="0 means no limit")
    p.add_argument("--only-missing", action="store_true", help="Only rows not present in extraction table")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args()


def _parse_source_ids(raw: str) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").split(","):
        t = normalize_ws(token)
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return tuple(out)


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_extraction_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS parl_initiative_doc_extractions (
          source_record_pk INTEGER PRIMARY KEY REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
          source_id TEXT NOT NULL REFERENCES sources(source_id),
          sample_initiative_id TEXT REFERENCES parl_initiatives(initiative_id) ON DELETE SET NULL,
          initiatives_count INTEGER NOT NULL DEFAULT 0,
          doc_refs_count INTEGER NOT NULL DEFAULT 0,
          doc_kinds_csv TEXT,
          content_sha256 TEXT,
          doc_format TEXT,
          extractor_version TEXT NOT NULL,
          extracted_title TEXT,
          extracted_subject TEXT,
          extracted_excerpt TEXT,
          confidence REAL,
          needs_review INTEGER NOT NULL DEFAULT 0 CHECK (needs_review IN (0, 1)),
          analysis_payload_json TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_source_id ON parl_initiative_doc_extractions(source_id);
        CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_needs_review ON parl_initiative_doc_extractions(needs_review);
        CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_sample_initiative_id ON parl_initiative_doc_extractions(sample_initiative_id);
        """
    )


def _infer_doc_format(content_type: str, source_url: str, raw_path: str) -> str:
    ct = normalize_ws(content_type).lower()
    su = normalize_ws(source_url).lower()
    rp = normalize_ws(raw_path).lower()
    if "pdf" in ct or su.endswith(".pdf") or rp.endswith(".pdf"):
        return "pdf"
    if "html" in ct or su.endswith(".html") or su.endswith(".htm") or rp.endswith(".html") or rp.endswith(".htm"):
        return "html"
    if "xml" in ct or su.endswith(".xml") or rp.endswith(".xml"):
        return "xml"
    return "other"


def _safe_trim(text: str, *, max_chars: int) -> str:
    token = normalize_ws(text)
    if len(token) <= max_chars:
        return token
    return token[: max_chars - 1].rstrip() + "…"


def _is_strong_title_subject(title_hint: str) -> bool:
    title = normalize_ws(title_hint)
    if len(title) < 35:
        return False
    return any(p.search(title) for p in _STRONG_TITLE_PATTERNS)


def _extract_subject(text_excerpt: str, title_hint: str) -> tuple[str, float, str]:
    text = normalize_ws(text_excerpt)
    title = normalize_ws(title_hint)
    if not text and title:
        if _is_strong_title_subject(title):
            return _safe_trim(title, max_chars=320), 0.74, "title_fallback_strong"
        return _safe_trim(title, max_chars=320), 0.72, "title_fallback"
    if not text:
        return "", 0.0, "empty"

    m = _KEYWORD_PATTERN.search(text)
    if m:
        candidate = _safe_trim(m.group(1), max_chars=320)
        if len(candidate) < 40 and title and _is_strong_title_subject(title):
            return _safe_trim(title, max_chars=320), 0.74, "title_hint_strong_from_short_window"
        return candidate, 0.82, "keyword_window"

    for raw_sentence in _SENTENCE_SPLIT_RE.split(text):
        s = normalize_ws(raw_sentence)
        if len(s) < 40:
            continue
        if len(s) > 320:
            s = _safe_trim(s, max_chars=320)
        lowered = s.lower()
        if any(
            kw in lowered
            for kw in (
                "proyecto",
                "proposición",
                "proposicion",
                "moción",
                "mocion",
                "interpelación",
                "interpelacion",
                "pregunta",
                "decreto-ley",
                "acuerdo",
                "enmienda",
                "veto",
            )
        ):
            return s, 0.76, "keyword_sentence"

    if title:
        if _is_strong_title_subject(title):
            return _safe_trim(title, max_chars=320), 0.74, "title_hint_strong"
        return _safe_trim(title, max_chars=320), 0.68, "title_hint"

    fallback = _safe_trim(text, max_chars=220)
    return fallback, 0.56, "excerpt_fallback"


def _build_query(initiative_source_ids: tuple[str, ...], *, only_missing: bool, has_limit: bool) -> tuple[str, list[Any]]:
    marks = ",".join("?" for _ in initiative_source_ids)
    params: list[Any] = list(initiative_source_ids)

    missing_clause = "AND ex.source_record_pk IS NULL" if only_missing else ""
    limit_sql = "LIMIT ?" if has_limit else ""

    sql = f"""
    WITH refs AS (
      SELECT
        pid.source_record_pk,
        MIN(pid.initiative_id) AS sample_initiative_id,
        COUNT(DISTINCT pid.initiative_id) AS initiatives_count,
        COUNT(*) AS doc_refs_count,
        GROUP_CONCAT(DISTINCT pid.doc_kind) AS doc_kinds_csv,
        MIN(COALESCE(NULLIF(TRIM(i.title), ''), pid.initiative_id)) AS sample_title
      FROM parl_initiative_documents pid
      JOIN parl_initiatives i ON i.initiative_id = pid.initiative_id
      WHERE i.source_id IN ({marks})
        AND pid.source_record_pk IS NOT NULL
      GROUP BY pid.source_record_pk
    )
    SELECT
      td.source_record_pk,
      td.source_id,
      td.source_url,
      td.content_type,
      td.content_sha256,
      td.raw_path,
      td.text_excerpt,
      refs.sample_initiative_id,
      refs.initiatives_count,
      refs.doc_refs_count,
      refs.doc_kinds_csv,
      refs.sample_title
    FROM text_documents td
    JOIN refs ON refs.source_record_pk = td.source_record_pk
    LEFT JOIN parl_initiative_doc_extractions ex ON ex.source_record_pk = td.source_record_pk
    WHERE td.text_excerpt IS NOT NULL
      AND TRIM(td.text_excerpt) <> ''
      {missing_clause}
    ORDER BY td.bytes DESC, td.source_record_pk ASC
    {limit_sql}
    """
    return sql, params


def backfill_initiative_doc_extractions(
    conn: sqlite3.Connection,
    *,
    doc_source_id: str,
    initiative_source_ids: tuple[str, ...],
    extractor_version: str,
    limit: int,
    only_missing: bool,
    dry_run: bool,
) -> dict[str, Any]:
    ensure_extraction_table(conn)

    has_limit = int(limit or 0) > 0
    sql, params = _build_query(initiative_source_ids, only_missing=bool(only_missing), has_limit=has_limit)
    if has_limit:
        params.append(int(limit))

    rows = conn.execute(sql, params).fetchall()

    seen = 0
    upsert_rows: list[tuple[Any, ...]] = []
    by_method: dict[str, int] = {}
    by_format: dict[str, int] = {}
    needs_review = 0
    sample: list[dict[str, Any]] = []
    now_iso = now_utc_iso()

    for r in rows:
        source_id = normalize_ws(str(r["source_id"] or ""))
        if source_id and source_id != normalize_ws(doc_source_id):
            continue

        seen += 1
        sr_pk = int(r["source_record_pk"])
        source_url = normalize_ws(str(r["source_url"] or ""))
        content_type = normalize_ws(str(r["content_type"] or ""))
        raw_path = normalize_ws(str(r["raw_path"] or ""))
        content_sha = normalize_ws(str(r["content_sha256"] or "")) or None
        title_hint = normalize_ws(str(r["sample_title"] or ""))
        excerpt = normalize_ws(str(r["text_excerpt"] or ""))
        sample_initiative_id = normalize_ws(str(r["sample_initiative_id"] or "")) or None
        initiatives_count = int(r["initiatives_count"] or 0)
        doc_refs_count = int(r["doc_refs_count"] or 0)
        doc_kinds_csv = normalize_ws(str(r["doc_kinds_csv"] or "")) or None

        subject, confidence, method = _extract_subject(excerpt, title_hint)
        extracted_title = _safe_trim(title_hint, max_chars=320) if title_hint else None
        extracted_excerpt = _safe_trim(excerpt, max_chars=700) if excerpt else None
        doc_format = _infer_doc_format(content_type, source_url, raw_path)
        min_subject_len = 40
        if method in {"title_hint_strong", "title_fallback_strong", "title_hint_strong_from_short_window"}:
            min_subject_len = 38
        review_flag = 1 if (confidence < 0.72 or len(subject) < min_subject_len) else 0
        if review_flag:
            needs_review += 1

        by_method[method] = int(by_method.get(method, 0)) + 1
        by_format[doc_format] = int(by_format.get(doc_format, 0)) + 1

        payload = {
            "subject_method": method,
            "source_url": source_url,
            "doc_refs_count": doc_refs_count,
            "initiatives_count": initiatives_count,
        }

        upsert_rows.append(
            (
                sr_pk,
                doc_source_id,
                sample_initiative_id,
                initiatives_count,
                doc_refs_count,
                doc_kinds_csv,
                content_sha,
                doc_format,
                extractor_version,
                extracted_title,
                subject,
                extracted_excerpt,
                float(confidence),
                int(review_flag),
                stable_json(payload),
                now_iso,
                now_iso,
            )
        )

        if len(sample) < 20:
            sample.append(
                {
                    "source_record_pk": sr_pk,
                    "sample_initiative_id": sample_initiative_id,
                    "doc_format": doc_format,
                    "subject_method": method,
                    "confidence": round(float(confidence), 3),
                    "needs_review": int(review_flag),
                    "extracted_subject": subject,
                }
            )

    if upsert_rows and not dry_run:
        with conn:
            conn.executemany(
                """
                INSERT INTO parl_initiative_doc_extractions (
                  source_record_pk,
                  source_id,
                  sample_initiative_id,
                  initiatives_count,
                  doc_refs_count,
                  doc_kinds_csv,
                  content_sha256,
                  doc_format,
                  extractor_version,
                  extracted_title,
                  extracted_subject,
                  extracted_excerpt,
                  confidence,
                  needs_review,
                  analysis_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_record_pk) DO UPDATE SET
                  source_id = excluded.source_id,
                  sample_initiative_id = excluded.sample_initiative_id,
                  initiatives_count = excluded.initiatives_count,
                  doc_refs_count = excluded.doc_refs_count,
                  doc_kinds_csv = excluded.doc_kinds_csv,
                  content_sha256 = excluded.content_sha256,
                  doc_format = excluded.doc_format,
                  extractor_version = excluded.extractor_version,
                  extracted_title = excluded.extracted_title,
                  extracted_subject = excluded.extracted_subject,
                  extracted_excerpt = excluded.extracted_excerpt,
                  confidence = excluded.confidence,
                  needs_review = excluded.needs_review,
                  analysis_payload_json = excluded.analysis_payload_json,
                  updated_at = excluded.updated_at
                """,
                upsert_rows,
            )

    result: dict[str, Any] = {
        "doc_source_id": doc_source_id,
        "initiative_source_ids": list(initiative_source_ids),
        "extractor_version": extractor_version,
        "only_missing": bool(only_missing),
        "dry_run": bool(dry_run),
        "seen": int(seen),
        "upserted": int(len(upsert_rows)),
        "needs_review": int(needs_review),
        "by_method": {k: int(v) for k, v in sorted(by_method.items())},
        "by_doc_format": {k: int(v) for k, v in sorted(by_format.items())},
        "sample": sample,
    }
    return result


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2

    initiative_source_ids = _parse_source_ids(str(args.initiative_source_ids))
    if not initiative_source_ids:
        print(json.dumps({"error": "initiative-source-ids empty"}, ensure_ascii=False))
        return 2

    with open_db(db_path) as conn:
        result = backfill_initiative_doc_extractions(
            conn,
            doc_source_id=normalize_ws(str(args.doc_source_id or "")) or "parl_initiative_docs",
            initiative_source_ids=initiative_source_ids,
            extractor_version=normalize_ws(str(args.extractor_version or "")) or DEFAULT_EXTRACTOR_VERSION,
            limit=int(args.limit or 0),
            only_missing=bool(args.only_missing),
            dry_run=bool(args.dry_run),
        )

    result["db"] = str(db_path)

    if normalize_ws(str(args.out or "")):
        out_path = Path(str(args.out)).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
