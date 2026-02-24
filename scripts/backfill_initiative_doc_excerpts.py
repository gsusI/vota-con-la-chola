#!/usr/bin/env python3
"""Backfill text excerpts for downloaded initiative documents.

Reads local raw files already referenced by `text_documents.raw_path` and fills
`text_excerpt` / `text_chars` when missing.

Primary target: `source_id='parl_initiative_docs'` rows with XML/PDF content.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill text excerpts for initiative docs")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-id", default="parl_initiative_docs", help="text_documents.source_id")
    p.add_argument(
        "--initiative-source-id",
        default="",
        help="Optional parl_initiatives.source_id filter (e.g. senado_iniciativas)",
    )
    p.add_argument("--limit", type=int, default=0, help="0 means no limit")
    p.add_argument("--excerpt-max-chars", type=int, default=4000)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = TAG_RE.sub(" ", text)
    text = WS_RE.sub(" ", text).strip()
    return text


def extract_from_xml_or_html(raw_bytes: bytes) -> str:
    decoded = raw_bytes.decode("utf-8", errors="replace")

    # Prefer XML parsing first so CDATA content is preserved via itertext().
    try:
        root = ET.fromstring(decoded)
        joined = " ".join(t for t in root.itertext() if t)
        out = normalize_text(joined)
        if out:
            return out
    except Exception:
        pass

    # Fallback for non-well-formed HTML/XML.
    return normalize_text(decoded)


def extract_from_pdf(raw_bytes: bytes, raw_path: Path) -> str:
    def _pdftotext_fallback() -> str:
        try:
            cp = subprocess.run(
                ["pdftotext", "-enc", "UTF-8", str(raw_path), "-"],
                check=False,
                capture_output=True,
                timeout=30,
            )
            if cp.returncode == 0 and cp.stdout:
                return normalize_text(cp.stdout.decode("utf-8", errors="replace"))
        except Exception:
            pass
        return ""

    # Lazy import so environments without PDF libs still run XML path.
    reader = None
    try:
        from pypdf import PdfReader  # type: ignore

        from io import BytesIO

        reader = PdfReader(BytesIO(raw_bytes))
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore

            from io import BytesIO

            reader = PdfReader(BytesIO(raw_bytes))
        except Exception:
            return _pdftotext_fallback()

    if reader is None:
        return _pdftotext_fallback()

    chunks: list[str] = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt:
            chunks.append(txt)
    out = normalize_text("\n".join(chunks))
    if out:
        return out
    return _pdftotext_fallback()


def should_parse_as_pdf(content_type: str, raw_path: Path) -> bool:
    ct = (content_type or "").lower()
    if "pdf" in ct:
        return True
    return raw_path.suffix.lower() == ".pdf"


def build_query(filter_initiative_source: str, has_limit: bool) -> str:
    where = [
        "td.source_id = ?",
        "(td.text_excerpt IS NULL OR TRIM(td.text_excerpt) = '')",
        "td.raw_path IS NOT NULL",
        "TRIM(td.raw_path) <> ''",
    ]

    if filter_initiative_source:
        where.append(
            "EXISTS (SELECT 1 FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id = pid.initiative_id WHERE pid.source_record_pk = td.source_record_pk AND i.source_id = ?)"
        )

    limit_sql = " LIMIT ?" if has_limit else ""

    return f"""
    SELECT td.source_record_pk, td.raw_path, COALESCE(td.content_type, '') AS content_type
    FROM text_documents td
    WHERE {' AND '.join(where)}
    ORDER BY td.source_record_pk ASC
    {limit_sql}
    """


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2

    filter_src = str(args.initiative_source_id or "").strip()
    has_limit = int(args.limit or 0) > 0
    sql = build_query(filter_src, has_limit=has_limit)

    params: list[Any] = [str(args.source_id)]
    if filter_src:
        params.append(filter_src)
    if has_limit:
        params.append(int(args.limit))

    seen = 0
    updated = 0
    skipped_missing_file = 0
    skipped_empty_text = 0
    pdf_parse_unavailable = 0
    failures: list[str] = []
    updates: list[tuple[Any, ...]] = []

    with open_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        seen = len(rows)

        for r in rows:
            sr_pk = int(r["source_record_pk"])
            raw_path = Path(str(r["raw_path"]))
            content_type = str(r["content_type"] or "")

            if not raw_path.exists() or not raw_path.is_file():
                skipped_missing_file += 1
                continue

            try:
                raw_bytes = raw_path.read_bytes()
                if should_parse_as_pdf(content_type, raw_path):
                    text = extract_from_pdf(raw_bytes, raw_path)
                    if not text:
                        pdf_parse_unavailable += 1
                else:
                    text = extract_from_xml_or_html(raw_bytes)

                if not text:
                    skipped_empty_text += 1
                    continue

                excerpt = text[: int(args.excerpt_max_chars)]
                text_chars = len(text)
                updates.append((excerpt, text_chars, now_utc_iso(), sr_pk))
            except Exception as exc:  # noqa: BLE001
                failures.append(f"source_record_pk={sr_pk}: {type(exc).__name__}: {exc}")

        if not args.dry_run and updates:
            with conn:
                conn.executemany(
                    """
                    UPDATE text_documents
                    SET text_excerpt = ?,
                        text_chars = ?,
                        updated_at = ?
                    WHERE source_record_pk = ?
                    """,
                    updates,
                )
            updated = len(updates)
        else:
            updated = len(updates)

    result = {
        "db": str(db_path),
        "source_id": str(args.source_id),
        "initiative_source_id": filter_src,
        "dry_run": bool(args.dry_run),
        "seen": seen,
        "updated": updated,
        "skipped_missing_file": skipped_missing_file,
        "skipped_empty_text": skipped_empty_text,
        "pdf_parse_unavailable_or_empty": pdf_parse_unavailable,
        "failures": failures[:30],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
