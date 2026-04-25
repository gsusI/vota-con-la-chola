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
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.util import normalize_ws, now_utc_iso, stable_json
from scripts.backfill_initiative_doc_excerpts import (
    extract_from_pdf,
    extract_from_xml_or_html,
    should_parse_as_pdf,
)


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_INITIATIVE_SOURCE_IDS = "congreso_iniciativas,senado_iniciativas"
DEFAULT_EXTRACTOR_VERSION = "heuristic_subject_v3"
DEFAULT_TEXT_OUTPUT_ROOT = Path("etl/data/derived/parl_initiative_doc_texts")

_KEYWORD_PATTERN = re.compile(
    r"((?:proyecto|proposici[oó]n|moci[oó]n|interpelaci[oó]n|pregunta|decreto-ley|real\s+decreto-ley|"
    r"tratado|convenio|acuerdo|enmienda|veto|dictamen|propuesta)"
    r"[^\.;:]{20,320})",
    re.I,
)
_SHELL_PATTERNS = (
    re.compile(r"\biniciativas parlamentarias\s*\|\s*senado de espa", re.I),
    re.compile(r"\bir al contenido\b", re.I),
    re.compile(r"\bpreguntas frecuentes\b", re.I),
    re.compile(r"\bmapa web\b", re.I),
    re.compile(r"\bdiccionario parlamentario\b", re.I),
    re.compile(r"\bcontactar s[íi]guenos\b", re.I),
    re.compile(r"\bactividad parlamentaria actualidad pleno y diputaci[oó]n permanente\b", re.I),
    re.compile(r"!function\(", re.I),
    re.compile(r"\bs\.go-mpulse\.net/boomerang\b", re.I),
)
_GOOD_TEXT_QUALITIES = {"structured_good", "html_good", "pdf_text_good", "ocr_good", "excerpt_only"}
_FORCE_REVIEW_TEXT_QUALITIES = {"shell_html", "garbled", "empty"}
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


def _looks_like_noisy_subject(candidate: str) -> bool:
    token = normalize_ws(candidate).lower()
    if not token:
        return True
    if "!function(" in token or "function(" in token:
        return True
    if "senado de espa" in token and "|" in token:
        return True
    if token.startswith("ir al contenido"):
        return True
    if "preguntas frecuentes" in token and "mapa web" in token:
        return True
    if "diccionario parlamentario" in token:
        return True
    if "contactar síguenos" in token or "contactar siguenos" in token:
        return True
    if "actividad parlamentaria actualidad pleno y diputación permanente" in token:
        return True
    if "actividad parlamentaria actualidad pleno y diputacion permanente" in token:
        return True
    if "var " in token and "http" in token:
        return True
    if "<script" in token or "javascript:" in token:
        return True
    return False


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
    p.add_argument(
        "--text-output-root",
        default=str(DEFAULT_TEXT_OUTPUT_ROOT),
        help="Directory where normalized full-text artifacts will be cached",
    )
    p.add_argument(
        "--ocr-fallback",
        action="store_true",
        help="Run OCR on PDFs only when direct text extraction is empty or too short",
    )
    p.add_argument(
        "--ocr-max-pages",
        type=int,
        default=12,
        help="Max PDF pages to OCR per document when --ocr-fallback is enabled (0 = all)",
    )
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


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {str(row["name"]) for row in rows}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition_sql: str) -> None:
    if column in _table_columns(conn, table):
        return
    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {definition_sql}')


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
          text_extraction_method TEXT,
          text_quality TEXT,
          needs_ocr INTEGER NOT NULL DEFAULT 0 CHECK (needs_ocr IN (0, 1)),
          full_text_chars INTEGER,
          full_text_path TEXT,
          extracted_title TEXT,
          extracted_subject TEXT,
          extracted_excerpt TEXT,
          confidence REAL,
          needs_review INTEGER NOT NULL DEFAULT 0 CHECK (needs_review IN (0, 1)),
          analysis_payload_json TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )
    compat_columns = {
        "text_extraction_method": "text_extraction_method TEXT",
        "text_quality": "text_quality TEXT",
        "needs_ocr": "needs_ocr INTEGER NOT NULL DEFAULT 0 CHECK (needs_ocr IN (0, 1))",
        "full_text_chars": "full_text_chars INTEGER",
        "full_text_path": "full_text_path TEXT",
    }
    for column, definition_sql in compat_columns.items():
        _ensure_column(conn, "parl_initiative_doc_extractions", column, definition_sql)
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_source_id ON parl_initiative_doc_extractions(source_id);
        CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_needs_review ON parl_initiative_doc_extractions(needs_review);
        CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_sample_initiative_id ON parl_initiative_doc_extractions(sample_initiative_id);
        CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_needs_ocr ON parl_initiative_doc_extractions(needs_ocr);
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


def _looks_like_shell_text(text: str) -> bool:
    token = normalize_ws(text)
    if not token:
        return False
    lower = token.lower()
    if "senado de espa" in lower and "!function(" in lower:
        return True
    hits = sum(1 for pattern in _SHELL_PATTERNS if pattern.search(lower))
    return hits >= 2 or ("iniciativas parlamentarias | senado de espa" in lower)


def _looks_garbled(text: str) -> bool:
    token = normalize_ws(text)
    if not token:
        return False
    bad = token.count("�")
    if bad >= 3:
        return True
    return (bad / max(len(token), 1)) >= 0.01


def _has_command(name: str) -> bool:
    return bool(shutil.which(name))


def _ocr_pdf_text(raw_path: Path, *, max_pages: int) -> str:
    if not (_has_command("pdftoppm") and _has_command("tesseract")):
        return ""
    with tempfile.TemporaryDirectory(prefix="initdoc-ocr-") as td:
        workdir = Path(td)
        prefix = workdir / "page"
        cmd = ["pdftoppm", "-png"]
        if int(max_pages or 0) > 0:
            cmd.extend(["-f", "1", "-l", str(int(max_pages))])
        cmd.extend([str(raw_path), str(prefix)])
        try:
            cp = subprocess.run(cmd, check=False, capture_output=True, timeout=120)
        except Exception:  # noqa: BLE001
            return ""
        if cp.returncode != 0:
            return ""
        page_paths = sorted(workdir.glob("page-*.png"))
        texts: list[str] = []
        for page_path in page_paths:
            try:
                ocr = subprocess.run(
                    ["tesseract", str(page_path), "stdout", "-l", "spa+eng"],
                    check=False,
                    capture_output=True,
                    timeout=120,
                )
            except Exception:  # noqa: BLE001
                continue
            if ocr.returncode != 0 or not ocr.stdout:
                continue
            texts.append(ocr.stdout.decode("utf-8", errors="replace"))
        return normalize_ws("\n".join(texts))


def _classify_text_quality(
    *,
    text: str,
    doc_format: str,
    extraction_method: str,
    source_url: str,
) -> tuple[str, int]:
    token = normalize_ws(text)
    if not token:
        if extraction_method == "excerpt_only":
            return "excerpt_only", 0
        if doc_format == "pdf":
            return "needs_ocr", 1
        return "empty", 0
    if _looks_like_shell_text(token):
        return "shell_html", 0
    if _looks_garbled(token):
        return "garbled", 0
    if extraction_method == "excerpt_only":
        return "excerpt_only", 0
    if extraction_method == "ocr":
        return "ocr_good", 0
    if doc_format == "xml" and len(token) >= 60:
        return "structured_good", 0
    if doc_format == "html" and len(token) >= 120:
        return "html_good", 0
    if doc_format == "pdf" and len(token) >= 120:
        return "pdf_text_good", 0
    if len(token) < 120:
        if doc_format == "pdf":
            return "needs_ocr", 1
        return "too_short", 0
    if source_url.lower().endswith(".xml"):
        return "structured_good", 0
    return "text_good", 0


def _materialize_text_artifact(
    *,
    source_record_pk: int,
    doc_format: str,
    text: str,
    text_output_root: Path,
    dry_run: bool,
) -> str | None:
    token = normalize_ws(text)
    if not token:
        return None
    out_dir = text_output_root / f"{int(source_record_pk) // 1000:05d}"
    out_path = out_dir / f"{int(source_record_pk)}-{doc_format or 'txt'}.txt"
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(token + "\n", encoding="utf-8")
    return str(out_path)


def _extract_full_text(
    *,
    raw_path: Path,
    content_type: str,
    source_url: str,
    excerpt: str,
    ocr_fallback: bool,
    ocr_max_pages: int,
) -> tuple[str, str, str, int]:
    doc_format = _infer_doc_format(content_type, source_url, str(raw_path))
    if not raw_path.exists() or not raw_path.is_file():
        quality, needs_ocr = _classify_text_quality(
            text=excerpt,
            doc_format=doc_format,
            extraction_method="excerpt_only",
            source_url=source_url,
        )
        return normalize_ws(excerpt), "excerpt_only", quality, needs_ocr

    raw_bytes = raw_path.read_bytes()
    if should_parse_as_pdf(content_type, raw_path):
        text = extract_from_pdf(raw_bytes, raw_path)
        quality, needs_ocr = _classify_text_quality(
            text=text,
            doc_format=doc_format,
            extraction_method="pdf_text",
            source_url=source_url,
        )
        if needs_ocr and bool(ocr_fallback):
            ocr_text = _ocr_pdf_text(raw_path, max_pages=max(0, int(ocr_max_pages or 0)))
            if ocr_text:
                ocr_quality, _ = _classify_text_quality(
                    text=ocr_text,
                    doc_format=doc_format,
                    extraction_method="ocr",
                    source_url=source_url,
                )
                return ocr_text, "ocr", ocr_quality, 0
        return text, "pdf_text", quality, needs_ocr

    text = extract_from_xml_or_html(raw_bytes)
    method = "xml_structured" if doc_format == "xml" else "html_text" if doc_format == "html" else "other_text"
    quality, needs_ocr = _classify_text_quality(
        text=text,
        doc_format=doc_format,
        extraction_method=method,
        source_url=source_url,
    )
    return text, method, quality, needs_ocr


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
        if _looks_like_noisy_subject(candidate):
            m = None
        else:
            if len(candidate) < 40 and title and _is_strong_title_subject(title):
                return _safe_trim(title, max_chars=320), 0.74, "title_hint_strong_from_short_window"
            return candidate, 0.82, "keyword_window"

    for raw_sentence in _SENTENCE_SPLIT_RE.split(text):
        s = normalize_ws(raw_sentence)
        if len(s) < 40:
            continue
        if len(s) > 320:
            s = _safe_trim(s, max_chars=320)
        if _looks_like_noisy_subject(s):
            continue
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
    WHERE (
      (td.text_excerpt IS NOT NULL AND TRIM(td.text_excerpt) <> '')
      OR (refs.sample_title IS NOT NULL AND TRIM(refs.sample_title) <> '')
    )
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
    text_output_root: Path = DEFAULT_TEXT_OUTPUT_ROOT,
    ocr_fallback: bool = False,
    ocr_max_pages: int = 12,
    limit: int,
    only_missing: bool,
    dry_run: bool,
) -> dict[str, Any]:
    ensure_extraction_table(conn)
    text_output_root = Path(text_output_root)

    has_limit = int(limit or 0) > 0
    sql, params = _build_query(initiative_source_ids, only_missing=bool(only_missing), has_limit=has_limit)
    if has_limit:
        params.append(int(limit))

    rows = conn.execute(sql, params).fetchall()

    seen = 0
    upsert_rows: list[tuple[Any, ...]] = []
    by_method: dict[str, int] = {}
    by_format: dict[str, int] = {}
    by_text_quality: dict[str, int] = {}
    needs_review = 0
    needs_ocr_count = 0
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

        full_text, text_extraction_method, text_quality, needs_ocr = _extract_full_text(
            raw_path=Path(raw_path) if raw_path else Path(""),
            content_type=content_type,
            source_url=source_url,
            excerpt=excerpt,
            ocr_fallback=bool(ocr_fallback),
            ocr_max_pages=max(0, int(ocr_max_pages or 0)),
        )
        subject_source_text = normalize_ws(full_text or excerpt)
        subject, confidence, method = _extract_subject(subject_source_text[:120000], title_hint)
        extracted_title = _safe_trim(title_hint, max_chars=320) if title_hint else None
        extracted_excerpt = _safe_trim(subject_source_text, max_chars=700) if subject_source_text else None
        doc_format = _infer_doc_format(content_type, source_url, raw_path)
        full_text_path = _materialize_text_artifact(
            source_record_pk=sr_pk,
            doc_format=doc_format,
            text=full_text,
            text_output_root=text_output_root,
            dry_run=bool(dry_run),
        )
        full_text_chars = len(normalize_ws(full_text)) if normalize_ws(full_text) else 0
        min_subject_len = 40
        if method in {"title_hint_strong", "title_fallback_strong", "title_hint_strong_from_short_window"}:
            min_subject_len = 38
        review_flag = 1 if (confidence < 0.72 or len(subject) < min_subject_len) else 0
        if text_quality in _FORCE_REVIEW_TEXT_QUALITIES or int(needs_ocr) == 1:
            review_flag = 1
        if review_flag:
            needs_review += 1
        if int(needs_ocr) == 1:
            needs_ocr_count += 1

        by_method[method] = int(by_method.get(method, 0)) + 1
        by_format[doc_format] = int(by_format.get(doc_format, 0)) + 1
        by_text_quality[text_quality] = int(by_text_quality.get(text_quality, 0)) + 1

        payload = {
            "subject_method": method,
            "source_url": source_url,
            "doc_refs_count": doc_refs_count,
            "initiatives_count": initiatives_count,
            "text_extraction_method": text_extraction_method,
            "text_quality": text_quality,
            "needs_ocr": int(needs_ocr),
            "full_text_chars": int(full_text_chars),
            "full_text_path": full_text_path,
            "subject_source": "full_text" if full_text else "excerpt",
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
                text_extraction_method,
                text_quality,
                int(needs_ocr),
                int(full_text_chars) if full_text_chars > 0 else None,
                full_text_path,
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
                    "text_extraction_method": text_extraction_method,
                    "text_quality": text_quality,
                    "needs_ocr": int(needs_ocr),
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
                  text_extraction_method,
                  text_quality,
                  needs_ocr,
                  full_text_chars,
                  full_text_path,
                  extracted_title,
                  extracted_subject,
                  extracted_excerpt,
                  confidence,
                  needs_review,
                  analysis_payload_json,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_record_pk) DO UPDATE SET
                  source_id = excluded.source_id,
                  sample_initiative_id = excluded.sample_initiative_id,
                  initiatives_count = excluded.initiatives_count,
                  doc_refs_count = excluded.doc_refs_count,
                  doc_kinds_csv = excluded.doc_kinds_csv,
                  content_sha256 = excluded.content_sha256,
                  doc_format = excluded.doc_format,
                  extractor_version = excluded.extractor_version,
                  text_extraction_method = excluded.text_extraction_method,
                  text_quality = excluded.text_quality,
                  needs_ocr = excluded.needs_ocr,
                  full_text_chars = excluded.full_text_chars,
                  full_text_path = excluded.full_text_path,
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
        "needs_ocr": int(needs_ocr_count),
        "by_method": {k: int(v) for k, v in sorted(by_method.items())},
        "by_doc_format": {k: int(v) for k, v in sorted(by_format.items())},
        "by_text_quality": {k: int(v) for k, v in sorted(by_text_quality.items())},
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
            text_output_root=Path(str(args.text_output_root)).resolve(),
            ocr_fallback=bool(args.ocr_fallback),
            ocr_max_pages=max(0, int(args.ocr_max_pages or 0)),
            limit=int(args.limit or 0),
            only_missing=bool(args.only_missing),
            dry_run=bool(args.dry_run),
        )

    result["db"] = str(db_path)
    result["text_output_root"] = str(Path(str(args.text_output_root)).resolve())
    result["ocr_fallback"] = bool(args.ocr_fallback)
    result["ocr_max_pages"] = max(0, int(args.ocr_max_pages or 0))

    if normalize_ws(str(args.out or "")):
        out_path = Path(str(args.out)).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
