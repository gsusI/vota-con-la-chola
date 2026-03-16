#!/usr/bin/env python3
"""Export initiative-document review queue for citizen-facing measure points.

This lane operates at the initiative bundle level rather than the single-vote
level. Workers review one official initiative dossier, extract concrete measures
people would recognize in everyday language, and point to the vote events that
best represent support/opposition to those measures.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws, now_utc_iso, stable_json
from scripts.backfill_initiative_doc_excerpts import (
    extract_from_pdf,
    extract_from_xml_or_html,
    should_parse_as_pdf,
)


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_INITIATIVE_SOURCE_IDS = "congreso_iniciativas,senado_iniciativas"
DEFAULT_DOC_SOURCE_ID = "parl_initiative_docs"
DEFAULT_REVIEW_REASON = "official_docs_bundle"
ALLOWED_REVIEW_REASONS = {"official_docs_bundle", "boe_law_bundle", "keyword_priority"}
PRIORITY_TERMS = (
    ("movilidad", 12),
    ("bajas emisiones", 12),
    ("tráfico", 10),
    ("trafico", 10),
    ("energ", 10),
    ("hidrocarb", 10),
    ("impuesto", 10),
    ("gravamen", 10),
    ("residuos", 8),
    ("moves", 8),
    ("movilidad eléctrica", 8),
    ("movilidad electrica", 8),
    ("diesel", 10),
    ("diésel", 10),
    ("baliza", 10),
    ("v16", 12),
)
SAFE_SLUG_RE = re.compile(r"[^a-z0-9]+")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export initiative measure review queue")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument(
        "--initiative-source-ids",
        default=DEFAULT_INITIATIVE_SOURCE_IDS,
        help="CSV of parl_initiatives.source_id values to include",
    )
    p.add_argument("--doc-source-id", default=DEFAULT_DOC_SOURCE_ID, help="text_documents.source_id")
    p.add_argument("--only-pending", action="store_true", help="Only export rows still pending")
    p.add_argument(
        "--contains",
        action="append",
        default=[],
        help="Case-insensitive text filter across initiative title and linked vote text",
    )
    p.add_argument(
        "--doc-contains",
        action="append",
        default=[],
        help="Case-insensitive text filter across extracted dossier document text",
    )
    p.add_argument("--min-priority", type=int, default=0, help="Minimum priority for exported rows")
    p.add_argument("--limit", type=int, default=0, help="0 means no limit")
    p.add_argument("--offset", type=int, default=0, help="Row offset for deterministic batching")
    p.add_argument("--max-bocg-docs", type=int, default=2, help="Max dossier docs to materialize per task")
    p.add_argument(
        "--evidence-root",
        default="tmp/codex-subagents/initiative-measures/evidence",
        help="Directory where evidence bundles will be materialized",
    )
    p.add_argument("--out", required=True, help="Output CSV path")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _parse_source_ids(raw: str) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").split(","):
        item = _norm(token)
        if not item or item in seen:
            continue
        values.append(item)
        seen.add(item)
    return tuple(values)


def _task_id(initiative_id: str) -> str:
    return _norm(initiative_id)


def _slug(value: str) -> str:
    token = SAFE_SLUG_RE.sub("-", _norm(value).lower()).strip("-")
    return token or "task"


def _priority_for_title(title: str, linked_vote_count: int) -> int:
    lower = _norm(title).lower()
    score = 50 + min(max(int(linked_vote_count or 0), 0), 12)
    for term, boost in PRIORITY_TERMS:
        if term in lower:
            score += boost
    if lower.startswith("proyecto de ley") or lower.startswith("proposición de ley"):
        score += 6
    return max(0, min(100, score))


def _pick_doc_rows(rows: list[dict[str, Any]], max_docs: int) -> list[dict[str, Any]]:
    if max_docs <= 0 or len(rows) <= max_docs:
        return rows
    if max_docs == 1:
        return [rows[0]]
    picked = [rows[0], rows[-1]]
    if max_docs == 2:
        return picked
    middle = rows[1 : 1 + max_docs - 2]
    return [rows[0], *middle, rows[-1]]


def _materialize_doc_text(raw_path: Path, content_type: str) -> str:
    raw_bytes = raw_path.read_bytes()
    if should_parse_as_pdf(content_type, raw_path):
        return extract_from_pdf(raw_bytes, raw_path)
    return extract_from_xml_or_html(raw_bytes)


def _load_doc_text(doc: dict[str, Any]) -> str:
    cached_path = Path(_norm(doc.get("full_text_path")))
    if cached_path.exists() and cached_path.is_file():
        return cached_path.read_text(encoding="utf-8")
    raw_path = Path(str(doc["raw_path"]))
    return _materialize_doc_text(raw_path, str(doc["content_type"]))


def sync_review_queue(
    conn: Any,
    *,
    initiative_source_ids: tuple[str, ...],
    doc_source_id: str = DEFAULT_DOC_SOURCE_ID,
    review_reason: str = DEFAULT_REVIEW_REASON,
) -> dict[str, int]:
    if not initiative_source_ids:
        return {"candidate_rows": 0, "upserted": 0}
    if review_reason not in ALLOWED_REVIEW_REASONS:
        raise ValueError(f"unsupported review_reason: {review_reason}")

    marks = ",".join("?" for _ in initiative_source_ids)
    candidates = conn.execute(
        f"""
        SELECT
          pi.initiative_id,
          pi.source_id,
          pi.title,
          COUNT(DISTINCT pve.vote_event_id) AS linked_vote_count
        FROM parl_initiatives pi
        JOIN parl_vote_event_initiatives pvi ON pvi.initiative_id = pi.initiative_id
        JOIN parl_vote_events pve ON pve.vote_event_id = pvi.vote_event_id
        WHERE pi.source_id IN ({marks})
          AND EXISTS (
            SELECT 1
            FROM parl_initiative_documents pid
            JOIN text_documents td
              ON td.source_record_pk = pid.source_record_pk
             AND td.source_id = ?
            WHERE pid.initiative_id = pi.initiative_id
              AND pid.doc_kind = 'bocg'
          )
        GROUP BY pi.initiative_id, pi.source_id, pi.title
        ORDER BY pi.initiative_id ASC
        """,
        [*initiative_source_ids, _norm(doc_source_id)],
    ).fetchall()

    now_iso = now_utc_iso()
    upserts: list[tuple[Any, ...]] = []
    for row in candidates:
        initiative_id = _norm(row["initiative_id"])
        payload = {
            "initiative_title": _norm(row["title"]),
            "linked_vote_count": int(row["linked_vote_count"] or 0),
        }
        upserts.append(
            (
                _task_id(initiative_id),
                initiative_id,
                _norm(row["source_id"]),
                review_reason,
                _priority_for_title(_norm(row["title"]), int(row["linked_vote_count"] or 0)),
                stable_json(payload),
                now_iso,
                now_iso,
            )
        )

    if upserts:
        with conn:
            conn.executemany(
                """
                INSERT INTO parl_initiative_measure_review_tasks (
                  task_id, initiative_id, source_id, review_reason, priority,
                  raw_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                  source_id = excluded.source_id,
                  review_reason = excluded.review_reason,
                  priority = excluded.priority,
                  raw_payload_json = excluded.raw_payload_json,
                  updated_at = excluded.updated_at
                """,
                upserts,
            )
    return {"candidate_rows": len(candidates), "upserted": len(upserts)}


def _fetch_doc_rows(conn: Any, initiative_id: str, doc_source_id: str) -> list[dict[str, Any]]:
    has_extractions = _table_exists(conn, "parl_initiative_doc_extractions")
    extraction_join = ""
    extraction_select = (
        "'' AS text_extraction_method, '' AS text_quality, 0 AS needs_ocr, '' AS full_text_path"
    )
    quality_order_expr = "4"
    if has_extractions:
        extraction_join = """
        LEFT JOIN parl_initiative_doc_extractions ex
          ON ex.source_record_pk = td.source_record_pk
         AND ex.source_id = td.source_id
        """
        extraction_select = """
          COALESCE(ex.text_extraction_method, '') AS text_extraction_method,
          COALESCE(ex.text_quality, '') AS text_quality,
          COALESCE(ex.needs_ocr, 0) AS needs_ocr,
          COALESCE(ex.full_text_path, '') AS full_text_path
        """
        quality_order_expr = """
          CASE
            WHEN COALESCE(ex.text_quality, '') IN ('structured_good', 'html_good', 'pdf_text_good', 'ocr_good', 'text_good') THEN 0
            WHEN COALESCE(ex.text_quality, '') = 'too_short' THEN 1
            WHEN COALESCE(ex.text_quality, '') = 'shell_html' THEN 2
            WHEN COALESCE(ex.text_quality, '') = 'needs_ocr' THEN 3
            ELSE 4
          END
        """
    rows = conn.execute(
        f"""
        SELECT
          pid.doc_kind,
          td.source_url,
          td.source_record_pk,
          td.raw_path,
          COALESCE(td.content_type, '') AS content_type,
          td.text_chars,
          {extraction_select}
        FROM parl_initiative_documents pid
        JOIN text_documents td
          ON td.source_record_pk = pid.source_record_pk
         AND td.source_id = ?
        {extraction_join}
        WHERE pid.initiative_id = ?
          AND pid.doc_kind = 'bocg'
          AND td.raw_path IS NOT NULL
          AND TRIM(td.raw_path) <> ''
        ORDER BY
          {quality_order_expr} ASC,
          td.source_url ASC
        """,
        (_norm(doc_source_id), _norm(initiative_id)),
    ).fetchall()
    return [
        {
            "doc_kind": _norm(row["doc_kind"]),
            "source_url": _norm(row["source_url"]),
            "source_record_pk": int(row["source_record_pk"] or 0),
            "raw_path": _norm(row["raw_path"]),
            "content_type": _norm(row["content_type"]),
            "text_chars": int(row["text_chars"] or 0),
            "text_extraction_method": _norm(row["text_extraction_method"]),
            "text_quality": _norm(row["text_quality"]),
            "needs_ocr": int(row["needs_ocr"] or 0),
            "full_text_path": _norm(row["full_text_path"]),
        }
        for row in rows
    ]


GOOD_TEXT_QUALITIES = {"structured_good", "html_good", "pdf_text_good", "ocr_good", "text_good"}


def _fetch_doc_search_blob(conn: Any, initiative_id: str, doc_source_id: str) -> str:
    if not _table_exists(conn, "parl_initiative_doc_extractions"):
        return ""
    rows = conn.execute(
        """
        SELECT
          COALESCE(ex.extracted_title, '') AS extracted_title,
          COALESCE(ex.extracted_subject, '') AS extracted_subject,
          COALESCE(ex.extracted_excerpt, '') AS extracted_excerpt,
          COALESCE(ex.text_quality, '') AS text_quality,
          COALESCE(ex.full_text_path, '') AS full_text_path
        FROM parl_initiative_documents pid
        JOIN text_documents td
          ON td.source_record_pk = pid.source_record_pk
         AND td.source_id = ?
        JOIN parl_initiative_doc_extractions ex
          ON ex.source_record_pk = td.source_record_pk
         AND ex.source_id = td.source_id
        WHERE pid.initiative_id = ?
          AND pid.doc_kind = 'bocg'
        ORDER BY td.source_url ASC
        """,
        (_norm(doc_source_id), _norm(initiative_id)),
    ).fetchall()
    chunks: list[str] = []
    for row in rows:
        for key in ("extracted_title", "extracted_subject", "extracted_excerpt"):
            value = _norm(row[key])
            if value:
                chunks.append(value)
        if _norm(row["text_quality"]) not in GOOD_TEXT_QUALITIES:
            continue
        full_text_path = Path(_norm(row["full_text_path"]))
        if not full_text_path.exists() or not full_text_path.is_file():
            continue
        try:
            text = full_text_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = full_text_path.read_text(encoding="utf-8", errors="ignore")
        value = _norm(text)
        if value:
            chunks.append(value)
    return "\n".join(chunks).lower()


def _fetch_linked_votes(conn: Any, initiative_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          pve.vote_event_id,
          pve.vote_date,
          pve.source_id AS vote_source_id,
          pve.title,
          pve.subgroup_title,
          pve.subgroup_text,
          pve.expediente_text,
          pve.totals_yes,
          pve.totals_no,
          pve.totals_abstain
        FROM parl_vote_event_initiatives pvi
        JOIN parl_vote_events pve ON pve.vote_event_id = pvi.vote_event_id
        WHERE pvi.initiative_id = ?
        ORDER BY pve.vote_date ASC, pve.vote_event_id ASC
        """,
        (_norm(initiative_id),),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "vote_event_id": _norm(row["vote_event_id"]),
                "vote_date": _norm(row["vote_date"]),
                "vote_source_id": _norm(row["vote_source_id"]),
                "title": _norm(row["title"]),
                "subgroup_title": _norm(row["subgroup_title"]),
                "subgroup_text": _norm(row["subgroup_text"]),
                "expediente_text": _norm(row["expediente_text"]),
                "totals_yes": int(row["totals_yes"] or 0),
                "totals_no": int(row["totals_no"] or 0),
                "totals_abstain": int(row["totals_abstain"] or 0),
            }
        )
    return out


def _vote_candidate_score(vote: dict[str, Any]) -> tuple[int, str, int]:
    title = _norm(vote.get("title")).lower()
    subgroup_title = _norm(vote.get("subgroup_title")).lower()
    subgroup_text = _norm(vote.get("subgroup_text")).lower()
    priority = 9
    if "convalidación" in title or "convalidacion" in title or "derogación" in title or "derogacion" in title:
        priority = 0
    elif "votación de conjunto" in subgroup_title or "votación de conjunto" in subgroup_text:
        priority = 1
    elif "texto final" in subgroup_title or "texto final" in subgroup_text:
        priority = 1
    elif title.startswith("enmiendas del senado"):
        priority = 2
    elif title.startswith("toma en consideración") or title.startswith("toma en consideracion"):
        priority = 3
    elif title.startswith("debates de totalidad"):
        priority = 4
    margin = abs(int(vote.get("totals_yes") or 0) - int(vote.get("totals_no") or 0))
    return (priority, _norm(vote.get("vote_date")), margin)


def _pick_key_vote_candidates(linked_votes: list[dict[str, Any]], max_candidates: int = 12) -> list[dict[str, Any]]:
    ordered = sorted(linked_votes, key=_vote_candidate_score)
    return ordered[: max(1, int(max_candidates or 1))]


def _table_exists(conn: Any, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (_norm(table_name),),
    ).fetchone()
    return row is not None


def _fetch_text_versions(conn: Any, initiative_id: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, "parl_initiative_text_versions"):
        return []
    rows = conn.execute(
        """
        SELECT
          initiative_text_version_id,
          chamber,
          doc_kind,
          document_code,
          doc_series,
          doc_number,
          version_order,
          published_date,
          stage_kind,
          stage_label,
          source_id,
          source_url,
          source_record_pk
        FROM parl_initiative_text_versions
        WHERE initiative_id = ?
        ORDER BY COALESCE(published_date, ''), COALESCE(version_order, 0), COALESCE(document_code, '')
        """,
        (_norm(initiative_id),),
    ).fetchall()
    return [{key: row[key] for key in row.keys()} for row in rows]


def _fetch_vote_text_versions(conn: Any, initiative_id: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, "parl_vote_event_text_versions"):
        return []
    rows = conn.execute(
        """
        SELECT
          vt.vote_event_id,
          vt.initiative_text_version_id,
          vt.link_method,
          vt.confidence,
          vt.is_primary,
          tv.published_date,
          tv.stage_kind,
          tv.stage_label,
          tv.document_code
        FROM parl_vote_event_text_versions vt
        JOIN parl_initiative_text_versions tv
          ON tv.initiative_text_version_id = vt.initiative_text_version_id
        WHERE vt.initiative_id = ?
        ORDER BY vt.vote_event_id ASC
        """,
        (_norm(initiative_id),),
    ).fetchall()
    return [{key: row[key] for key in row.keys()} for row in rows]


def _pick_materialized_doc_rows(
    doc_rows: list[dict[str, Any]],
    *,
    linked_votes: list[dict[str, Any]],
    text_versions: list[dict[str, Any]],
    vote_text_versions: list[dict[str, Any]],
    max_docs: int,
) -> list[dict[str, Any]]:
    if not doc_rows:
        return []
    max_i = int(max_docs or 0)
    if max_i <= 0:
        return doc_rows
    if len(doc_rows) <= max_i and not vote_text_versions:
        return doc_rows

    doc_by_source_record_pk = {
        int(doc["source_record_pk"] or 0): doc
        for doc in doc_rows
        if int(doc["source_record_pk"] or 0) > 0
    }
    version_by_id = {
        _norm(version["initiative_text_version_id"]): version
        for version in text_versions
        if _norm(version["initiative_text_version_id"])
    }
    primary_vote_version = {
        _norm(vote["vote_event_id"]): vote
        for vote in vote_text_versions
        if int(vote.get("is_primary") or 0) == 1
    }

    picked: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    def _append_doc(doc: dict[str, Any]) -> bool:
        sr_pk = int(doc["source_record_pk"] or 0)
        key = ("sr", str(sr_pk)) if sr_pk > 0 else ("url", _norm(doc.get("source_url")))
        if key in seen_keys:
            return False
        seen_keys.add(key)
        picked.append(doc)
        return True

    for vote in _pick_key_vote_candidates(linked_votes):
        matched = primary_vote_version.get(_norm(vote["vote_event_id"]))
        if not matched:
            continue
        version = version_by_id.get(_norm(matched.get("initiative_text_version_id")))
        if not version:
            continue
        doc = doc_by_source_record_pk.get(int(version.get("source_record_pk") or 0))
        if doc and _append_doc(doc) and len(picked) >= max_i:
            return picked

    for doc in _pick_doc_rows(doc_rows, max_i):
        _append_doc(doc)
        if len(picked) >= max_i:
            break

    return picked or _pick_doc_rows(doc_rows, max_i)


def fetch_review_rows(
    conn: Any,
    *,
    only_pending: bool,
    contains_terms: list[str],
    doc_contains_terms: list[str] | None = None,
    min_priority: int,
    limit: int,
    offset: int,
    doc_source_id: str = DEFAULT_DOC_SOURCE_ID,
) -> list[dict[str, Any]]:
    where = ["1=1"]
    params: list[Any] = []
    if only_pending:
        where.append("t.status = 'pending'")
    if int(min_priority or 0) > 0:
        where.append("t.priority >= ?")
        params.append(int(min_priority))

    limit_sql = ""
    limit_i = max(0, int(limit or 0))
    offset_i = max(0, int(offset or 0))
    contains_norm = [_norm(term).lower() for term in contains_terms if _norm(term)]
    doc_contains_norm = [_norm(term).lower() for term in (doc_contains_terms or []) if _norm(term)]
    if not contains_norm and not doc_contains_norm:
        if limit_i > 0:
            limit_sql = "LIMIT ? OFFSET ?"
            params.extend([limit_i, offset_i])
        elif offset_i > 0:
            limit_sql = "LIMIT -1 OFFSET ?"
            params.append(offset_i)

    rows = conn.execute(
        f"""
        SELECT
          t.task_id,
          t.initiative_id,
          t.source_id,
          t.review_reason,
          t.status,
          t.priority,
          t.evidence_bundle_dir,
          t.note,
          t.raw_payload_json,
          i.expediente,
          i.title AS initiative_title,
          i.type AS initiative_type,
          i.supertype,
          i.procedure_type,
          i.current_status,
          i.source_url AS initiative_source_url
        FROM parl_initiative_measure_review_tasks t
        JOIN parl_initiatives i ON i.initiative_id = t.initiative_id
        WHERE {' AND '.join(where)}
        ORDER BY t.priority DESC, i.title ASC, t.task_id ASC
        {limit_sql}
        """,
        params,
    ).fetchall()

    out: list[dict[str, Any]] = []
    linked_vote_cache: dict[str, list[dict[str, Any]]] = {}
    doc_search_cache: dict[str, str] = {}
    for row in rows:
        item = {key: row[key] for key in row.keys()}
        if contains_norm:
            initiative_id = _norm(item["initiative_id"])
            linked_votes = linked_vote_cache.get(initiative_id)
            if linked_votes is None:
                linked_votes = _fetch_linked_votes(conn, initiative_id)
                linked_vote_cache[initiative_id] = linked_votes
            joined = " ".join(
                [
                    _norm(item["initiative_title"]),
                    _norm(item["expediente"]),
                    *[
                        " ".join(
                            (
                                _norm(v["title"]),
                                _norm(v["subgroup_title"]),
                                _norm(v["subgroup_text"]),
                                _norm(v["expediente_text"]),
                            )
                        )
                        for v in linked_votes
                    ],
                ]
            ).lower()
            if not any(term in joined for term in contains_norm):
                continue
        if doc_contains_norm:
            initiative_id = _norm(item["initiative_id"])
            doc_blob = doc_search_cache.get(initiative_id)
            if doc_blob is None:
                doc_blob = _fetch_doc_search_blob(conn, initiative_id, doc_source_id)
                doc_search_cache[initiative_id] = doc_blob
            if not any(term in doc_blob for term in doc_contains_norm):
                continue
        out.append({key: (_norm(value) if isinstance(value, str) else value) for key, value in item.items()})
    if offset_i > 0 or limit_i > 0:
        sliced = out[offset_i:]
        if limit_i > 0:
            sliced = sliced[:limit_i]
        return sliced
    return out


def write_evidence_bundle(
    conn: Any,
    row: dict[str, Any],
    *,
    doc_source_id: str,
    evidence_root: Path,
    max_bocg_docs: int,
) -> str:
    task_id = _norm(row["task_id"])
    initiative_id = _norm(row["initiative_id"])
    bundle_dir = evidence_root / _slug(task_id)
    docs_dir = bundle_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    linked_votes = _fetch_linked_votes(conn, initiative_id)
    text_versions = _fetch_text_versions(conn, initiative_id)
    vote_text_versions = _fetch_vote_text_versions(conn, initiative_id)
    doc_rows = _pick_materialized_doc_rows(
        _fetch_doc_rows(conn, initiative_id, doc_source_id),
        linked_votes=linked_votes,
        text_versions=text_versions,
        vote_text_versions=vote_text_versions,
        max_docs=max(1, int(max_bocg_docs or 1)),
    )
    version_by_source_record_pk = {
        int(v["source_record_pk"] or 0): v
        for v in text_versions
        if int(v["source_record_pk"] or 0) > 0
    }
    primary_vote_version = {
        _norm(v["vote_event_id"]): v
        for v in vote_text_versions
        if int(v["is_primary"] or 0) == 1
    }
    materialized_docs: list[dict[str, Any]] = []

    for idx, doc in enumerate(doc_rows, start=1):
        raw_path = Path(str(doc["raw_path"]))
        text = _load_doc_text(doc)
        out_name = f"{idx:02d}-{_slug(Path(raw_path).stem)}.txt"
        out_path = docs_dir / out_name
        out_path.write_text(text, encoding="utf-8")
        matched_version = version_by_source_record_pk.get(int(doc["source_record_pk"] or 0))
        materialized_docs.append(
            {
                "doc_kind": doc["doc_kind"],
                "source_url": doc["source_url"],
                "source_record_pk": int(doc["source_record_pk"] or 0),
                "raw_path": str(raw_path),
                "content_type": doc["content_type"],
                "text_chars": len(text),
                "text_extraction_method": _norm(doc.get("text_extraction_method")),
                "text_quality": _norm(doc.get("text_quality")),
                "needs_ocr": int(doc.get("needs_ocr") or 0),
                "cached_full_text_path": _norm(doc.get("full_text_path")),
                "materialized_path": str(out_path),
                "initiative_text_version_id": _norm((matched_version or {}).get("initiative_text_version_id")),
                "published_date": _norm((matched_version or {}).get("published_date")),
                "stage_kind": _norm((matched_version or {}).get("stage_kind")),
                "stage_label": _norm((matched_version or {}).get("stage_label")),
                "version_order": int((matched_version or {}).get("version_order") or 0),
                "document_code": _norm((matched_version or {}).get("document_code")),
            }
        )

    key_vote_candidates: list[dict[str, Any]] = []
    for vote in _pick_key_vote_candidates(linked_votes):
        item = dict(vote)
        matched = primary_vote_version.get(_norm(vote["vote_event_id"]))
        if matched:
            item["recommended_text_version_id"] = _norm(matched.get("initiative_text_version_id"))
            item["recommended_text_published_date"] = _norm(matched.get("published_date"))
            item["recommended_text_stage_kind"] = _norm(matched.get("stage_kind"))
            item["recommended_text_stage_label"] = _norm(matched.get("stage_label"))
            item["recommended_link_method"] = _norm(matched.get("link_method"))
            item["recommended_link_confidence"] = float(matched.get("confidence") or 0.0)
        key_vote_candidates.append(item)

    task_payload = {
        "task_id": task_id,
        "initiative": {
            "initiative_id": initiative_id,
            "source_id": _norm(row["source_id"]),
            "expediente": _norm(row["expediente"]),
            "title": _norm(row["initiative_title"]),
            "type": _norm(row["initiative_type"]),
            "supertype": _norm(row["supertype"]),
            "procedure_type": _norm(row["procedure_type"]),
            "current_status": _norm(row["current_status"]),
            "source_url": _norm(row["initiative_source_url"]),
        },
        "linked_votes": linked_votes,
        "key_vote_candidates": key_vote_candidates,
        "text_versions": text_versions,
        "vote_text_versions": vote_text_versions,
        "materialized_docs": materialized_docs,
        "review_goal": (
            "Extract 1-5 concrete citizen-facing measures from this initiative dossier. "
            "For each measure, choose the vote_event_id(s) that best represent support/opposition."
        ),
    }
    (bundle_dir / "task.json").write_text(
        json.dumps(task_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(bundle_dir)


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    evidence_root = Path(args.evidence_root)

    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    initiative_source_ids = _parse_source_ids(args.initiative_source_ids)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)

    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        sync_review_queue(
            conn,
            initiative_source_ids=initiative_source_ids,
            doc_source_id=str(args.doc_source_id),
        )
        rows = fetch_review_rows(
            conn,
            only_pending=bool(args.only_pending),
            contains_terms=list(args.contains or []),
            doc_contains_terms=list(args.doc_contains or []),
            min_priority=int(args.min_priority or 0),
            limit=int(args.limit or 0),
            offset=int(args.offset or 0),
            doc_source_id=str(args.doc_source_id),
        )
        output_rows: list[list[str]] = []
        for row in rows:
            bundle_dir = write_evidence_bundle(
                conn,
                row,
                doc_source_id=str(args.doc_source_id),
                evidence_root=evidence_root,
                max_bocg_docs=max(1, int(args.max_bocg_docs or 1)),
            )
            with conn:
                conn.execute(
                    """
                    UPDATE parl_initiative_measure_review_tasks
                    SET evidence_bundle_dir = ?, updated_at = ?
                    WHERE task_id = ?
                    """,
                    (bundle_dir, now_utc_iso(), _norm(row["task_id"])),
                )
            linked_votes = _fetch_linked_votes(conn, _norm(row["initiative_id"]))
            output_rows.append(
                [
                    _norm(row["task_id"]),
                    _norm(row["initiative_id"]),
                    _norm(row["source_id"]),
                    _norm(row["review_reason"]),
                    _norm(row["status"]),
                    str(int(row["priority"] or 0)),
                    _norm(row["expediente"]),
                    _norm(row["initiative_title"]),
                    str(len(linked_votes)),
                    bundle_dir,
                    "",
                    "",
                    "",
                    "",
                ]
            )

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "task_id",
                "initiative_id",
                "source_id",
                "review_reason",
                "status",
                "priority",
                "expediente",
                "initiative_title",
                "linked_vote_count",
                "evidence_bundle_dir",
                "review_status",
                "review_note",
                "reviewer",
                "result_file",
            ]
        )
        w.writerows(output_rows)

    print(f"OK wrote {out_path} (rows={len(output_rows)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
