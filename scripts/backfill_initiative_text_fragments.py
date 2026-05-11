#!/usr/bin/env python3
"""Backfill deterministic fragments over versioned initiative texts."""

from __future__ import annotations

import argparse
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
from etl.politicos_es.util import normalize_ws, now_utc_iso, sha256_bytes, stable_json
from scripts.backfill_initiative_doc_excerpts import (
    extract_from_pdf,
    extract_from_xml_or_html,
    should_parse_as_pdf,
)
from etl.parlamentario_es.text_documents import _maybe_decompress_gzip_payload


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_INITIATIVE_SOURCE_IDS = "congreso_iniciativas,senado_iniciativas"
DEFAULT_DOC_SOURCE_ID = "parl_initiative_docs"
FRAGMENTER_VERSION = "legal_markers_v1"
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[\.;:!?])\s+")
HEADER_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?:(?<=^)|(?<=[\.;:]))\s*((?:CAP[IÍ]TULO|Cap[ií]tulo)\s+[IVXLCDM0-9]+(?:\s+[A-ZÁÉÍÓÚÑ][^\.]{0,80})?)"
        ),
        "chapter",
    ),
    (
        re.compile(
            r"(?:(?<=^)|(?<=[\.;:]))\s*((?:SECCI[ÓO]N|Secci[oó]n)\s+[IVXLCDM0-9]+(?:\s+[A-ZÁÉÍÓÚÑ][^\.]{0,80})?)"
        ),
        "section",
    ),
    (
        re.compile(
            r"(?:(?<=^)|(?<=[\.;:]))\s*((?:Art[ií]culo|ART[IÍ]CULO)\s+(?:\d+[A-Za-zªº]*|[Uu][Nn][Ii][Cc][Oo])(?:\.[A-Za-z0-9ªº]+)?(?:\s+[A-ZÁÉÍÓÚÑ][^\.]{0,80})?)"
        ),
        "article",
    ),
    (
        re.compile(
            r"(?:(?<=^)|(?<=[\.;:]))\s*((?:Art\.)\s*\d+[A-Za-zªº]*(?:\.[A-Za-z0-9ªº]+)?(?:\s+[A-ZÁÉÍÓÚÑ][^\.]{0,80})?)"
        ),
        "article",
    ),
    (
        re.compile(
            r"(?:(?<=^)|(?<=[\.;:]))\s*((?:Disposici[oó]n|DISPOSICI[ÓO]N)\s+(?:adicional|transitoria|derogatoria|final|única|unica)\s*[A-Za-z0-9ªº]*)"
        ),
        "disposition",
    ),
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill deterministic initiative text fragments")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument(
        "--initiative-source-ids",
        default=DEFAULT_INITIATIVE_SOURCE_IDS,
        help="CSV of parl_initiatives.source_id values to include",
    )
    p.add_argument(
        "--initiative-id",
        action="append",
        default=[],
        help="Specific initiative_id to include (repeatable)",
    )
    p.add_argument("--doc-source-id", default=DEFAULT_DOC_SOURCE_ID, help="text_documents.source_id")
    p.add_argument(
        "--only-vote-linked",
        action="store_true",
        help="Restrict to initiatives already linked in parl_vote_event_initiatives",
    )
    p.add_argument("--limit-initiatives", type=int, default=0, help="0 means no limit")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", default="", help="Optional JSON summary output path")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _parse_source_ids(raw: str) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").split(","):
        item = _norm(token)
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return tuple(out)


def _build_query(
    *,
    initiative_source_ids: tuple[str, ...],
    initiative_ids: tuple[str, ...],
    doc_source_id: str,
    only_vote_linked: bool,
    limit_initiatives: int,
) -> tuple[str, list[Any]]:
    marks = ",".join("?" for _ in initiative_source_ids)
    params: list[Any] = [*initiative_source_ids]
    vote_clause = ""
    initiative_clause = ""
    if initiative_ids:
        initiative_marks = ",".join("?" for _ in initiative_ids)
        initiative_clause = f" AND i.initiative_id IN ({initiative_marks})"
        params.extend(initiative_ids)
    if only_vote_linked:
        vote_clause = """
          AND EXISTS (
            SELECT 1
            FROM parl_vote_event_initiatives pvei
            WHERE pvei.initiative_id = i.initiative_id
          )
        """

    limit_sql = ""
    if int(limit_initiatives or 0) > 0:
        limit_sql = "LIMIT ?"
        params.append(int(limit_initiatives))

    sql = f"""
    WITH target_initiatives AS (
      SELECT i.initiative_id
      FROM parl_initiatives i
      WHERE i.source_id IN ({marks})
      {initiative_clause}
      {vote_clause}
      ORDER BY i.initiative_id ASC
      {limit_sql}
    )
    SELECT
      tv.initiative_text_version_id,
      tv.initiative_id,
      tv.source_id,
      tv.source_record_pk,
      tv.source_url,
      ex.full_text_path,
      td.raw_path,
      td.content_type,
      td.text_excerpt
    FROM parl_initiative_text_versions tv
    JOIN target_initiatives ti
      ON ti.initiative_id = tv.initiative_id
    LEFT JOIN parl_initiative_doc_extractions ex
      ON ex.source_record_pk = tv.source_record_pk
    LEFT JOIN text_documents td
      ON td.source_id = ?
     AND (
       (tv.source_record_pk IS NOT NULL AND td.source_record_pk = tv.source_record_pk)
       OR ((tv.source_record_pk IS NULL OR td.source_record_pk IS NULL) AND td.source_url = tv.source_url)
     )
    ORDER BY tv.initiative_id ASC,
             CASE WHEN tv.published_date IS NULL OR TRIM(tv.published_date) = '' THEN 1 ELSE 0 END ASC,
             tv.published_date ASC,
             COALESCE(tv.version_order, 0) ASC,
             tv.initiative_text_version_id ASC
    """
    return sql, [*params, _norm(doc_source_id)]


def _load_materialized_text(path_value: str) -> str:
    text_path = Path(path_value)
    if not text_path.exists() or not text_path.is_file():
        return ""
    return _norm(text_path.read_text(encoding="utf-8", errors="replace"))


def _load_raw_text(row: Any) -> str:
    raw_path_value = _norm(row["raw_path"])
    if not raw_path_value:
        return ""
    raw_path = Path(raw_path_value)
    if not raw_path.exists() or not raw_path.is_file():
        return ""
    raw_bytes = _maybe_decompress_gzip_payload(raw_path.read_bytes())
    if should_parse_as_pdf(_norm(row["content_type"]), raw_path):
        return _norm(extract_from_pdf(raw_bytes, raw_path))
    return _norm(extract_from_xml_or_html(raw_bytes))


def _prefer_raw_text(row: Any) -> bool:
    raw_path_value = _norm(row["raw_path"])
    if not raw_path_value:
        return False
    raw_path = Path(raw_path_value)
    content_type = _norm(row["content_type"]).lower()
    if should_parse_as_pdf(content_type, raw_path):
        return False
    suffix = raw_path.suffix.lower()
    if suffix in {".html", ".htm", ".xhtml", ".xml"}:
        return True
    return any(token in content_type for token in ("html", "xml", "text/"))


def _load_version_text(row: Any) -> str:
    if _prefer_raw_text(row):
        token = _load_raw_text(row)
        if token:
            return token

    full_text_path = _norm(row["full_text_path"])
    if full_text_path:
        token = _load_materialized_text(full_text_path)
        if token:
            return token

    token = _load_raw_text(row)
    if token:
        return token
    return _norm(row["text_excerpt"])


def _header_matches(text: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen_starts: set[int] = set()
    for pattern, kind in HEADER_PATTERNS:
        for match in pattern.finditer(text):
            label = _norm(match.group(1))
            start = int(match.start(1))
            if not label or start in seen_starts:
                continue
            seen_starts.add(start)
            matches.append(
                {
                    "start": start,
                    "label": label,
                    "kind": kind,
                }
            )
    return sorted(matches, key=lambda item: (int(item["start"]), _norm(item["label"]).lower()))


def _slice_fragment(text: str, start: int, end: int) -> str:
    return _norm(text[start:end])


def _fallback_chunks(text: str, *, start_order: int) -> list[dict[str, Any]]:
    token = _norm(text)
    if not token:
        return []
    if len(token) <= 900:
        return [
            {
                "fragment_order": start_order,
                "fragment_kind": "chunk",
                "fragment_label": "Chunk 1",
                "char_start": 0,
                "char_end": len(token),
                "fragment_text": token,
            }
        ]

    pieces = [piece for piece in SENTENCE_BOUNDARY_RE.split(token) if _norm(piece)]
    if not pieces:
        pieces = [token[i : i + 900] for i in range(0, len(token), 900)]

    fragments: list[dict[str, Any]] = []
    cursor = 0
    current = ""
    current_start = 0
    target = 900
    max_chars = 1200
    min_chars = 350
    for sentence in pieces:
        sentence_text = _norm(sentence)
        if not sentence_text:
            continue
        if not current:
            current = sentence_text
            current_start = cursor
            cursor += len(sentence_text) + 1
            continue
        proposed = f"{current} {sentence_text}"
        if len(proposed) > max_chars or (len(current) >= min_chars and len(proposed) >= target):
            fragments.append(
                {
                    "fragment_order": start_order + len(fragments),
                    "fragment_kind": "chunk",
                    "fragment_label": f"Chunk {len(fragments) + 1}",
                    "char_start": current_start,
                    "char_end": current_start + len(current),
                    "fragment_text": current,
                }
            )
            current = sentence_text
            current_start = cursor
        else:
            current = proposed
        cursor += len(sentence_text) + 1

    if current:
        fragments.append(
            {
                "fragment_order": start_order + len(fragments),
                "fragment_kind": "chunk",
                "fragment_label": f"Chunk {len(fragments) + 1}",
                "char_start": current_start,
                "char_end": current_start + len(current),
                "fragment_text": current,
            }
        )
    return fragments


def _header_fragments(text: str) -> list[dict[str, Any]]:
    headers = _header_matches(text)
    if not headers:
        return []

    fragments: list[dict[str, Any]] = []
    first_start = int(headers[0]["start"])
    if first_start >= 80:
        preamble = _slice_fragment(text, 0, first_start)
        if preamble:
            fragments.append(
                {
                    "fragment_order": 1,
                    "fragment_kind": "paragraph",
                    "fragment_label": "Preamble",
                    "char_start": 0,
                    "char_end": first_start,
                    "fragment_text": preamble,
                }
            )

    for idx, header in enumerate(headers):
        start = int(header["start"])
        end = len(text) if idx + 1 >= len(headers) else int(headers[idx + 1]["start"])
        fragment_text = _slice_fragment(text, start, end)
        if not fragment_text:
            continue
        fragments.append(
            {
                "fragment_order": len(fragments) + 1,
                "fragment_kind": _norm(header["kind"]) or "unknown",
                "fragment_label": _norm(header["label"]),
                "char_start": start,
                "char_end": end,
                "fragment_text": fragment_text,
            }
        )

    if not fragments:
        return []
    average_len = sum(len(str(item["fragment_text"])) for item in fragments) / max(len(fragments), 1)
    if len(fragments) >= 12 and average_len < 120:
        return []
    return fragments


def _build_fragments_for_text(text: str) -> list[dict[str, Any]]:
    token = _norm(text)
    if not token:
        return []
    fragments = _header_fragments(token)
    if fragments:
        return fragments
    return _fallback_chunks(token, start_order=1)


def backfill_fragments(
    conn: Any,
    *,
    initiative_source_ids: tuple[str, ...],
    initiative_ids: tuple[str, ...] = (),
    doc_source_id: str,
    only_vote_linked: bool,
    limit_initiatives: int,
    dry_run: bool,
) -> dict[str, Any]:
    sql, params = _build_query(
        initiative_source_ids=initiative_source_ids,
        initiative_ids=initiative_ids,
        doc_source_id=doc_source_id,
        only_vote_linked=only_vote_linked,
        limit_initiatives=limit_initiatives,
    )
    rows = conn.execute(sql, params).fetchall()
    now_iso = now_utc_iso()
    initiative_ids = {_norm(row["initiative_id"]) for row in rows if _norm(row["initiative_id"])}
    versions_with_text = 0
    versions_without_text = 0
    delete_version_ids: list[str] = []
    fragment_rows: list[tuple[Any, ...]] = []

    for row in rows:
        version_id = _norm(row["initiative_text_version_id"])
        initiative_id = _norm(row["initiative_id"])
        source_id = _norm(row["source_id"])
        text = _load_version_text(row)
        if not text:
            versions_without_text += 1
            continue
        versions_with_text += 1
        delete_version_ids.append(version_id)
        for fragment in _build_fragments_for_text(text):
            fragment_text = _norm(fragment["fragment_text"])
            fragment_label = _norm(fragment["fragment_label"])
            fragment_kind = _norm(fragment["fragment_kind"]) or "unknown"
            fragment_order = int(fragment["fragment_order"])
            char_start = int(fragment["char_start"])
            char_end = int(fragment["char_end"])
            text_hash = sha256_bytes(fragment_text.encode("utf-8"))
            fragment_id = "pfrag:" + sha256_bytes(
                f"{version_id}|{fragment_order}|{fragment_kind}|{fragment_label}|{text_hash}".encode("utf-8")
            )[:32]
            raw_payload = {
                "fragmenter_version": FRAGMENTER_VERSION,
                "text_chars": len(_norm(text)),
            }
            fragment_rows.append(
                (
                    fragment_id,
                    version_id,
                    initiative_id,
                    source_id,
                    row["source_record_pk"],
                    fragment_order,
                    fragment_kind,
                    fragment_label or None,
                    char_start,
                    char_end,
                    fragment_text,
                    text_hash,
                    stable_json(raw_payload),
                    now_iso,
                    now_iso,
                )
            )

    if not dry_run and delete_version_ids:
        seen_delete_ids: set[str] = set()
        for version_id in delete_version_ids:
            if version_id in seen_delete_ids:
                continue
            seen_delete_ids.add(version_id)
            conn.execute(
                "DELETE FROM parl_text_fragments WHERE initiative_text_version_id = ?",
                (version_id,),
            )
        if fragment_rows:
            conn.executemany(
                """
                INSERT INTO parl_text_fragments (
                  fragment_id, initiative_text_version_id, initiative_id, source_id, source_record_pk,
                  fragment_order, fragment_kind, fragment_label, char_start, char_end, fragment_text,
                  text_hash, raw_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                fragment_rows,
            )

    return {
        "initiative_source_ids": list(initiative_source_ids),
        "initiative_ids": list(initiative_ids),
        "doc_source_id": _norm(doc_source_id),
        "dry_run": bool(dry_run),
        "initiatives_seen": len(initiative_ids),
        "versions_seen": len(rows),
        "versions_with_text": versions_with_text,
        "versions_without_text": versions_without_text,
        "fragments_upserted": len(fragment_rows),
        "fragmenter_version": FRAGMENTER_VERSION,
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    initiative_source_ids = _parse_source_ids(args.initiative_source_ids)
    initiative_ids = tuple(_norm(value) for value in (args.initiative_id or ()) if _norm(value))
    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        with conn:
            result = backfill_fragments(
                conn,
                initiative_source_ids=initiative_source_ids,
                initiative_ids=initiative_ids,
                doc_source_id=_norm(args.doc_source_id) or DEFAULT_DOC_SOURCE_ID,
                only_vote_linked=bool(args.only_vote_linked),
                limit_initiatives=max(0, int(args.limit_initiatives or 0)),
                dry_run=bool(args.dry_run),
            )

    if _norm(args.out):
        Path(args.out).write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
