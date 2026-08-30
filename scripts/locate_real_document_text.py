#!/usr/bin/env python3
"""Build exact page/span locators for the current real native-text generation."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import resource
import sqlite3
import sys
import time
import uuid
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_docs.extraction import (
    DEFAULT_MARKUP_SECTION_MAX_DEPTH,
    DEFAULT_MAX_SEMANTIC_MARKUP_BYTES,
    DOCUMENT_LOCATOR_ALGORITHM_VERSION,
    DocumentTextLocator,
    build_document_text_locators,
)
from publicdata_docs.generation_manifest import (
    GenerationManifestError,
    iter_generation_rows,
    publish_generation_manifest,
)

DEFAULT_RAW_ROOT = Path("etl/data/raw")
DEFAULT_NATIVE_ROOT = Path("etl/data/derived/real-document-text-corpus-v2")
DEFAULT_NATIVE_MANIFEST = Path(
    "etl/data/published/real-document-text-manifest-latest.jsonl"
)
DEFAULT_STATE_DB = Path("etl/data/staging/real-document-text-locators-v1.db")
DEFAULT_MANIFEST = Path(
    "etl/data/published/real-document-text-locator-manifest-latest.jsonl"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-text-locator-extraction.json"
)
ROW_SCHEMA = "real_document_text_locator_row_v1"
REPORT_SCHEMA = "real_document_text_locator_extraction_v1"
DATASET = "native_text_locator"
NATIVE_DATASET = "native_text"
NATIVE_ROW_SCHEMA = "real_document_text_manifest_row_v1"


class LocatorRunError(RuntimeError):
    """Raised when exact locator evidence cannot be produced."""


@dataclass(frozen=True)
class LocatorOutcome:
    content_sha256: str
    status: str
    locators: tuple[DocumentTextLocator, ...]
    native_text_bytes: int
    raw_bytes: int
    error: str | None


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def safe_child(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise LocatorRunError(f"unsafe relative path: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise LocatorRunError(f"path escapes root: {relative}") from exc
    return candidate


def sha256_path(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def process_usage() -> dict[str, float | int]:
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    multiplier = 1 if sys.platform == "darwin" else 1024
    return {
        "cpu_seconds": float(
            own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime
        ),
        "peak_rss_bytes_self": int(own.ru_maxrss * multiplier),
        "peak_rss_bytes_child_max": int(children.ru_maxrss * multiplier),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--native-root", default=str(DEFAULT_NATIVE_ROOT))
    parser.add_argument("--native-manifest", default=str(DEFAULT_NATIVE_MANIFEST))
    parser.add_argument("--state-db", default=str(DEFAULT_STATE_DB))
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--max-span-chars", type=int, default=8_192)
    parser.add_argument("--max-average-locators-per-content", type=float, default=10.0)
    parser.add_argument("--max-locators-per-content", type=int, default=2_000)
    parser.add_argument(
        "--markup-section-max-depth",
        type=int,
        default=DEFAULT_MARKUP_SECTION_MAX_DEPTH,
    )
    parser.add_argument(
        "--max-semantic-markup-bytes",
        type=int,
        default=DEFAULT_MAX_SEMANTIC_MARKUP_BYTES,
    )
    parser.add_argument("--pdf-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--claim-size", type=int, default=32)
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--manifest-shard-max-rows", type=int, default=10_000)
    parser.add_argument(
        "--manifest-shard-max-uncompressed-bytes",
        type=int,
        default=64 * 1024 * 1024,
    )
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def open_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS locator_metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS document_instances (
          path TEXT PRIMARY KEY,
          content_sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          extension TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          source_group TEXT NOT NULL,
          page_count INTEGER,
          native_text_sha256 TEXT NOT NULL,
          native_text_cas_path TEXT NOT NULL,
          native_text_chars INTEGER NOT NULL,
          native_extraction_method TEXT NOT NULL,
          CHECK (bytes >= 0),
          CHECK (native_text_chars >= 0)
        );

        CREATE INDEX IF NOT EXISTS idx_locator_instances_content
          ON document_instances(content_sha256);

        CREATE TABLE IF NOT EXISTS locator_work (
          content_sha256 TEXT PRIMARY KEY,
          representative_path TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          mime_type TEXT NOT NULL,
          page_count INTEGER,
          native_text_sha256 TEXT NOT NULL,
          native_text_cas_path TEXT NOT NULL,
          native_text_chars INTEGER NOT NULL,
          native_extraction_method TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending',
          attempts INTEGER NOT NULL DEFAULT 0,
          max_attempts INTEGER NOT NULL,
          lease_owner TEXT,
          lease_expires_at TEXT,
          locator_rows INTEGER,
          native_text_bytes INTEGER,
          last_error TEXT,
          started_at TEXT,
          completed_at TEXT,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (representative_path) REFERENCES document_instances(path),
          CHECK (state IN ('pending', 'leased', 'succeeded', 'dead')),
          CHECK (attempts >= 0),
          CHECK (max_attempts >= 1)
        );

        CREATE INDEX IF NOT EXISTS idx_locator_work_claim
          ON locator_work(state, lease_expires_at, content_sha256);

        CREATE TABLE IF NOT EXISTS content_locators (
          content_sha256 TEXT NOT NULL,
          segment_index INTEGER NOT NULL,
          locator_type TEXT NOT NULL,
          locator_value TEXT NOT NULL,
          page_number INTEGER,
          text_start_char INTEGER NOT NULL,
          text_end_char INTEGER NOT NULL,
          text_chars INTEGER NOT NULL,
          text_sha256 TEXT NOT NULL,
          has_text INTEGER NOT NULL,
          PRIMARY KEY (content_sha256, segment_index),
          FOREIGN KEY (content_sha256) REFERENCES locator_work(content_sha256),
          CHECK (segment_index >= 0),
          CHECK (text_start_char >= 0),
          CHECK (text_end_char >= text_start_char),
          CHECK (text_chars = text_end_char - text_start_char),
          CHECK (has_text IN (0, 1))
        );
        """
    )
    conn.commit()


def metadata(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        str(row["key"]): str(row["value"])
        for row in conn.execute("SELECT key, value FROM locator_metadata")
    }


def seed_state(
    conn: sqlite3.Connection,
    *,
    native_manifest: Path,
    max_span_chars: int,
    markup_section_max_depth: int,
    max_semantic_markup_bytes: int,
    max_attempts: int,
) -> dict[str, int]:
    manifest_sha256 = sha256_path(native_manifest)
    existing = metadata(conn)
    if existing:
        if (
            existing.get("native_manifest_sha256") != manifest_sha256
            or int(existing.get("max_span_chars") or 0) != max_span_chars
            or existing.get("locator_algorithm_version")
            != DOCUMENT_LOCATOR_ALGORITHM_VERSION
            or int(existing.get("markup_section_max_depth") or -1)
            != markup_section_max_depth
            or int(existing.get("max_semantic_markup_bytes") or 0)
            != max_semantic_markup_bytes
        ):
            raise LocatorRunError(
                "state DB belongs to another native generation/configuration"
            )
        return {
            "file_instances": int(existing["file_instances"]),
            "distinct_content_objects": int(existing["distinct_content_objects"]),
        }
    if conn.execute("SELECT COUNT(*) FROM document_instances").fetchone()[0]:
        raise LocatorRunError("state DB has rows without metadata")

    file_instances = 0
    for item in iter_generation_rows(
        native_manifest,
        dataset=NATIVE_DATASET,
        row_schema_version=NATIVE_ROW_SCHEMA,
        allow_legacy_jsonl=False,
    ):
        path = str(item.get("path") or "")
        content_sha256 = str(item.get("content_sha256") or "")
        native_sha256 = str(item.get("native_text_sha256") or "")
        native_cas_path = str(item.get("native_text_cas_path") or "")
        if (
            item.get("work_state") != "succeeded"
            or item.get("native_extraction_status") != "native_text_extracted"
            or item.get("native_text_truncated") is not False
            or item.get("synthetic_or_mock") is not False
            or item.get("official_public_domain_personal_information_retained")
            is not True
            or len(content_sha256) != 64
            or len(native_sha256) != 64
            or not native_cas_path
        ):
            raise LocatorRunError(f"native row is not locator-ready: {path}")
        values = (
            path,
            content_sha256,
            int(item["bytes"]),
            str(item.get("extension") or ""),
            str(item.get("mime_type") or ""),
            str(item.get("source_group") or "unknown"),
            item.get("page_count"),
            native_sha256,
            native_cas_path,
            int(item["native_text_chars"]),
            str(item.get("native_extraction_method") or ""),
        )
        conn.execute(
            """
            INSERT INTO document_instances (
              path, content_sha256, bytes, extension, mime_type, source_group,
              page_count, native_text_sha256, native_text_cas_path,
              native_text_chars, native_extraction_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO locator_work (
              content_sha256, representative_path, bytes, mime_type, page_count,
              native_text_sha256, native_text_cas_path, native_text_chars,
              native_extraction_method, max_attempts, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                content_sha256,
                path,
                int(item["bytes"]),
                str(item.get("mime_type") or ""),
                item.get("page_count"),
                native_sha256,
                native_cas_path,
                int(item["native_text_chars"]),
                str(item.get("native_extraction_method") or ""),
                max_attempts,
                utc_now(),
            ),
        )
        canonical = conn.execute(
            """
            SELECT bytes, page_count, native_text_sha256, native_text_cas_path,
                   native_text_chars, native_extraction_method
            FROM locator_work WHERE content_sha256 = ?
            """,
            (content_sha256,),
        ).fetchone()
        observed = (
            int(canonical["bytes"]),
            canonical["page_count"],
            str(canonical["native_text_sha256"]),
            str(canonical["native_text_cas_path"]),
            int(canonical["native_text_chars"]),
            str(canonical["native_extraction_method"]),
        )
        expected = (
            int(item["bytes"]),
            item.get("page_count"),
            native_sha256,
            native_cas_path,
            int(item["native_text_chars"]),
            str(item.get("native_extraction_method") or ""),
        )
        if observed != expected:
            raise LocatorRunError(
                f"duplicate content metadata drifted: {content_sha256}"
            )
        file_instances += 1
        if file_instances % 5_000 == 0:
            conn.commit()
    conn.commit()
    distinct = int(conn.execute("SELECT COUNT(*) FROM locator_work").fetchone()[0])
    if file_instances < 1 or distinct < 1:
        raise LocatorRunError("refusing to seed an empty locator generation")
    conn.executemany(
        "INSERT INTO locator_metadata (key, value) VALUES (?, ?)",
        [
            ("native_manifest_sha256", manifest_sha256),
            ("max_span_chars", str(max_span_chars)),
            ("locator_algorithm_version", DOCUMENT_LOCATOR_ALGORITHM_VERSION),
            ("markup_section_max_depth", str(markup_section_max_depth)),
            ("max_semantic_markup_bytes", str(max_semantic_markup_bytes)),
            ("file_instances", str(file_instances)),
            ("distinct_content_objects", str(distinct)),
            ("seeded_at", utc_now()),
        ],
    )
    conn.commit()
    return {"file_instances": file_instances, "distinct_content_objects": distinct}


def claim_work(
    conn: sqlite3.Connection,
    *,
    owner: str,
    limit: int,
    lease_seconds: int,
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    now_iso = now.isoformat().replace("+00:00", "Z")
    expires = (
        (now + timedelta(seconds=lease_seconds)).isoformat().replace("+00:00", "Z")
    )
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        """
        UPDATE locator_work
        SET state = 'pending', lease_owner = NULL, lease_expires_at = NULL,
            updated_at = ?
        WHERE state = 'leased' AND lease_expires_at < ?
        """,
        (now_iso, now_iso),
    )
    rows = conn.execute(
        """
        SELECT * FROM locator_work
        WHERE state = 'pending'
        ORDER BY content_sha256
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.executemany(
        """
        UPDATE locator_work
        SET state = 'leased', attempts = attempts + 1, lease_owner = ?,
            lease_expires_at = ?, started_at = COALESCE(started_at, ?),
            updated_at = ?
        WHERE content_sha256 = ? AND state = 'pending'
        """,
        [
            (owner, expires, now_iso, now_iso, str(row["content_sha256"]))
            for row in rows
        ],
    )
    conn.commit()
    return [dict(row) for row in rows]


def read_native_text(path: Path, expected_sha256: str, expected_chars: int) -> str:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        text = handle.read()
    if len(text) != expected_chars:
        raise LocatorRunError("native text character count drifted")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != expected_sha256:
        raise LocatorRunError("native text checksum drifted")
    return text


def locate_one(
    row: Mapping[str, Any],
    *,
    raw_root: Path,
    native_root: Path,
    max_span_chars: int,
    pdf_timeout_seconds: float,
    markup_section_max_depth: int,
    max_semantic_markup_bytes: int,
    max_locators_per_content: int,
) -> LocatorOutcome:
    content_sha256 = str(row["content_sha256"])
    try:
        raw_path = safe_child(raw_root, str(row["representative_path"]))
        if not raw_path.is_file() or raw_path.stat().st_size != int(row["bytes"]):
            raise LocatorRunError("raw representative is missing or size-drifted")
        if sha256_path(raw_path) != content_sha256:
            raise LocatorRunError("raw representative checksum drifted")
        native_path = safe_child(native_root, str(row["native_text_cas_path"]))
        if not native_path.is_file():
            raise LocatorRunError("native text CAS is missing")
        text = read_native_text(
            native_path,
            str(row["native_text_sha256"]),
            int(row["native_text_chars"]),
        )
        locators = build_document_text_locators(
            text,
            raw_path=raw_path,
            content_type=str(row["mime_type"]),
            extraction_method=str(row["native_extraction_method"]),
            expected_page_count=row["page_count"],
            max_span_chars=max_span_chars,
            pdf_timeout_seconds=pdf_timeout_seconds,
            markup_section_max_depth=markup_section_max_depth,
            max_semantic_markup_bytes=max_semantic_markup_bytes,
            max_locators_per_content=max_locators_per_content,
        )
        if not locators:
            raise LocatorRunError("locator generation returned no rows")
        return LocatorOutcome(
            content_sha256=content_sha256,
            status="succeeded",
            locators=tuple(locators),
            native_text_bytes=len(text.encode("utf-8")),
            raw_bytes=int(row["bytes"]),
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        return LocatorOutcome(
            content_sha256=content_sha256,
            status="failed",
            locators=(),
            native_text_bytes=0,
            raw_bytes=0,
            error=f"{type(exc).__name__}: {exc}"[:2_000],
        )


def persist_outcomes(
    conn: sqlite3.Connection,
    *,
    owner: str,
    outcomes: list[LocatorOutcome],
) -> dict[str, int]:
    totals = {
        "succeeded": 0,
        "retried": 0,
        "dead": 0,
        "locator_rows": 0,
        "raw_bytes_rehashed": 0,
        "native_text_bytes_rehashed": 0,
    }
    now_iso = utc_now()
    conn.execute("BEGIN IMMEDIATE")
    for outcome in outcomes:
        if outcome.status == "succeeded":
            conn.execute(
                "DELETE FROM content_locators WHERE content_sha256 = ?",
                (outcome.content_sha256,),
            )
            conn.executemany(
                """
                INSERT INTO content_locators (
                  content_sha256, segment_index, locator_type, locator_value,
                  page_number, text_start_char, text_end_char, text_chars,
                  text_sha256, has_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        outcome.content_sha256,
                        item.segment_index,
                        item.locator_type,
                        item.locator_value,
                        item.page_number,
                        item.text_start_char,
                        item.text_end_char,
                        item.text_chars,
                        item.text_sha256,
                        1 if item.has_text else 0,
                    )
                    for item in outcome.locators
                ],
            )
            cursor = conn.execute(
                """
                UPDATE locator_work
                SET state = 'succeeded', lease_owner = NULL,
                    lease_expires_at = NULL, locator_rows = ?,
                    native_text_bytes = ?, last_error = NULL,
                    completed_at = ?, updated_at = ?
                WHERE content_sha256 = ? AND state = 'leased'
                  AND lease_owner = ?
                """,
                (
                    len(outcome.locators),
                    outcome.native_text_bytes,
                    now_iso,
                    now_iso,
                    outcome.content_sha256,
                    owner,
                ),
            )
            if cursor.rowcount != 1:
                raise LocatorRunError(f"lost locator lease: {outcome.content_sha256}")
            totals["succeeded"] += 1
            totals["locator_rows"] += len(outcome.locators)
            totals["raw_bytes_rehashed"] += outcome.raw_bytes
            totals["native_text_bytes_rehashed"] += outcome.native_text_bytes
            continue
        row = conn.execute(
            """
            SELECT attempts, max_attempts FROM locator_work
            WHERE content_sha256 = ? AND state = 'leased' AND lease_owner = ?
            """,
            (outcome.content_sha256, owner),
        ).fetchone()
        if row is None:
            raise LocatorRunError(f"lost failed lease: {outcome.content_sha256}")
        dead = int(row["attempts"]) >= int(row["max_attempts"])
        conn.execute(
            """
            UPDATE locator_work
            SET state = ?, lease_owner = NULL, lease_expires_at = NULL,
                last_error = ?, updated_at = ?
            WHERE content_sha256 = ? AND lease_owner = ?
            """,
            (
                "dead" if dead else "pending",
                outcome.error,
                now_iso,
                outcome.content_sha256,
                owner,
            ),
        )
        totals["dead" if dead else "retried"] += 1
    conn.commit()
    return totals


def run_worker(
    conn: sqlite3.Connection,
    *,
    raw_root: Path,
    native_root: Path,
    workers: int,
    claim_size: int,
    max_items: int,
    lease_seconds: int,
    max_span_chars: int,
    pdf_timeout_seconds: float,
    markup_section_max_depth: int,
    max_semantic_markup_bytes: int,
    max_locators_per_content: int,
) -> dict[str, int]:
    owner = f"real-document-locator-{uuid.uuid4().hex}"
    totals = {
        "claimed": 0,
        "succeeded": 0,
        "retried": 0,
        "dead": 0,
        "locator_rows": 0,
        "raw_bytes_rehashed": 0,
        "native_text_bytes_rehashed": 0,
    }
    while max_items <= 0 or totals["claimed"] < max_items:
        remaining = (
            claim_size
            if max_items <= 0
            else min(claim_size, max_items - totals["claimed"])
        )
        if remaining <= 0:
            break
        claimed = claim_work(
            conn, owner=owner, limit=remaining, lease_seconds=lease_seconds
        )
        if not claimed:
            break
        totals["claimed"] += len(claimed)
        outcomes: list[LocatorOutcome] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = [
                executor.submit(
                    locate_one,
                    row,
                    raw_root=raw_root,
                    native_root=native_root,
                    max_span_chars=max_span_chars,
                    pdf_timeout_seconds=pdf_timeout_seconds,
                    markup_section_max_depth=markup_section_max_depth,
                    max_semantic_markup_bytes=max_semantic_markup_bytes,
                    max_locators_per_content=max_locators_per_content,
                )
                for row in claimed
            ]
            for future in as_completed(futures):
                outcomes.append(future.result())
        persisted = persist_outcomes(conn, owner=owner, outcomes=outcomes)
        for key, value in persisted.items():
            totals[key] += value
        if totals["claimed"] % 10_000 == 0:
            print(
                f"progress claimed={totals['claimed']} "
                f"succeeded={totals['succeeded']} dead={totals['dead']}",
                flush=True,
            )
    return totals


def terminal_state(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN state = 'succeeded' THEN 1 ELSE 0 END) AS succeeded
        FROM locator_work
        """
    ).fetchone()
    return int(row["total"] or 0) > 0 and int(row["total"] or 0) == int(
        row["succeeded"] or 0
    )


def iter_manifest_rows(conn: sqlite3.Connection) -> Iterator[dict[str, Any]]:
    cursor = conn.execute(
        """
        SELECT i.path, i.content_sha256, i.source_group, i.mime_type,
               i.page_count AS document_page_count,
               i.native_text_sha256, i.native_text_cas_path,
               i.native_text_chars, i.native_extraction_method,
               l.segment_index, l.locator_type, l.locator_value,
               l.page_number, l.text_start_char, l.text_end_char,
               l.text_chars, l.text_sha256, l.has_text
        FROM document_instances i
        JOIN content_locators l USING (content_sha256)
        ORDER BY i.path, l.segment_index
        """
    )
    for row in cursor:
        yield {
            "schema_version": ROW_SCHEMA,
            "path": row["path"],
            "content_sha256": row["content_sha256"],
            "source_group": row["source_group"],
            "mime_type": row["mime_type"],
            "document_page_count": row["document_page_count"],
            "native_text_sha256": row["native_text_sha256"],
            "native_text_cas_path": row["native_text_cas_path"],
            "native_text_chars": int(row["native_text_chars"]),
            "native_extraction_method": row["native_extraction_method"],
            "segment_index": int(row["segment_index"]),
            "locator_type": row["locator_type"],
            "locator_value": row["locator_value"],
            "page_number": row["page_number"],
            "text_start_char": int(row["text_start_char"]),
            "text_end_char": int(row["text_end_char"]),
            "text_chars": int(row["text_chars"]),
            "text_sha256": row["text_sha256"],
            "has_text": bool(row["has_text"]),
            "text_included_in_manifest": False,
            "synthetic_or_mock": False,
            "official_public_domain_personal_information_retained": True,
        }


def publish_manifest(
    conn: sqlite3.Connection,
    out_path: Path,
    *,
    max_rows: int,
    max_uncompressed_bytes: int,
) -> dict[str, Any]:
    manifest = publish_generation_manifest(
        manifest_path=out_path,
        rows=iter_manifest_rows(conn),
        dataset=DATASET,
        row_schema_version=ROW_SCHEMA,
        state_connection=conn,
        max_rows=max_rows,
        max_uncompressed_bytes=max_uncompressed_bytes,
        policy={
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "native_text_is_not_sanitized_or_identity_stripped": True,
            "locator_rows_copy_no_public_text": True,
            "automatic_deletion_forbidden": True,
        },
    )
    manifest["path"] = display_path(out_path)
    return manifest


def build_report(
    conn: sqlite3.Connection,
    *,
    native_manifest: Path,
    state_db: Path,
    manifest: Mapping[str, Any],
    max_span_chars: int,
    markup_section_max_depth: int,
    max_semantic_markup_bytes: int,
    max_average_locators_per_content: float,
    max_locators_per_content: int,
    run_totals: Mapping[str, int],
    performance: Mapping[str, Any],
) -> dict[str, Any]:
    state_counts = {
        str(row["state"]): int(row["total"])
        for row in conn.execute(
            "SELECT state, COUNT(*) AS total FROM locator_work GROUP BY state"
        )
    }
    totals = conn.execute(
        """
        SELECT COUNT(*) AS content_objects,
               COALESCE(SUM(locator_rows), 0) AS content_locator_rows,
               COALESCE(SUM(native_text_chars), 0) AS native_text_chars,
               COALESCE(SUM(native_text_bytes), 0) AS native_text_bytes,
               SUM(CASE WHEN mime_type LIKE '%pdf%' THEN 1 ELSE 0 END)
                 AS pdf_content_objects,
               SUM(CASE WHEN mime_type NOT LIKE '%pdf%' THEN 1 ELSE 0 END)
                 AS markup_content_objects,
               COALESCE(SUM(CASE WHEN mime_type LIKE '%pdf%'
                                 THEN page_count ELSE 0 END), 0)
                 AS expected_pdf_page_locators,
               COALESCE(AVG(locator_rows), 0) AS average_locator_rows_per_content,
               COALESCE(MAX(locator_rows), 0) AS max_locator_rows_per_content
        FROM locator_work
        """
    ).fetchone()
    locator_totals = conn.execute(
        """
        SELECT COUNT(*) AS locator_rows,
               SUM(CASE WHEN locator_type = 'pdf_page' THEN 1 ELSE 0 END)
                 AS pdf_page_locators,
               SUM(CASE WHEN locator_type = 'normalized_text_span' THEN 1 ELSE 0 END)
                 AS normalized_text_span_locators,
               SUM(CASE WHEN locator_type = 'markup_section' THEN 1 ELSE 0 END)
                 AS markup_section_locators,
               SUM(CASE WHEN locator_type = 'document_no_text' THEN 1 ELSE 0 END)
                 AS no_text_locators,
               COUNT(DISTINCT CASE WHEN locator_type = 'markup_section'
                                   THEN content_sha256 END)
                 AS semantic_markup_content_objects,
               COUNT(DISTINCT CASE WHEN locator_type = 'normalized_text_span'
                                   THEN content_sha256 END)
                 AS fallback_markup_content_objects,
               SUM(CASE WHEN has_text = 1 THEN 1 ELSE 0 END) AS locators_with_text,
               COALESCE(SUM(text_chars), 0) AS locator_text_chars,
               MAX(CASE WHEN locator_type IN (
                              'normalized_text_span', 'markup_section')
                        THEN text_chars ELSE 0 END) AS max_span_chars
        FROM content_locators
        """
    ).fetchone()
    file_instances = int(
        conn.execute("SELECT COUNT(*) FROM document_instances").fetchone()[0]
    )
    instance_locator_rows = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM document_instances i
            JOIN content_locators l USING (content_sha256)
            """
        ).fetchone()[0]
    )
    metadata_values = metadata(conn)
    complete = (
        state_counts.get("succeeded", 0) == int(totals["content_objects"])
        and state_counts.get("dead", 0) == 0
        and state_counts.get("pending", 0) == 0
        and state_counts.get("leased", 0) == 0
    )
    checks = {
        "native_manifest_bound_by_sha256": metadata_values.get("native_manifest_sha256")
        == sha256_path(native_manifest),
        "every_content_object_terminal_success": complete,
        "every_content_object_has_locator": int(locator_totals["locator_rows"] or 0)
        >= int(totals["content_objects"]),
        "every_file_instance_has_locator": instance_locator_rows >= file_instances,
        "every_pdf_page_has_locator": int(locator_totals["pdf_page_locators"] or 0)
        == int(totals["expected_pdf_page_locators"] or 0),
        "normalized_spans_within_configured_bound": int(
            locator_totals["max_span_chars"] or 0
        )
        <= max_span_chars,
        "semantic_markup_sections_materialized": int(
            locator_totals["markup_section_locators"] or 0
        )
        > 0,
        "average_locator_fanout_within_million_scale_bound": float(
            totals["average_locator_rows_per_content"] or 0
        )
        <= max_average_locators_per_content,
        "maximum_locator_fanout_within_bound": int(
            totals["max_locator_rows_per_content"] or 0
        )
        <= max_locators_per_content,
        "markup_content_objects_accounted_for": (
            int(locator_totals["semantic_markup_content_objects"] or 0)
            + int(locator_totals["fallback_markup_content_objects"] or 0)
            + int(locator_totals["no_text_locators"] or 0)
        )
        == int(totals["markup_content_objects"] or 0),
        "manifest_contains_every_instance_locator": instance_locator_rows
        == int(manifest.get("rows") or -1),
        "no_dead_work": state_counts.get("dead", 0) == 0,
        "no_public_text_copied_into_manifest": True,
        "no_synthetic_or_mock_records": True,
        "official_public_domain_personal_information_retained": True,
    }
    elapsed = float(performance["elapsed_seconds"])
    succeeded = int(run_totals.get("succeeded", 0))
    report_performance = {
        **performance,
        "content_objects_per_second": round(succeeded / elapsed, 6),
        "raw_bytes_per_second": round(
            int(run_totals.get("raw_bytes_rehashed", 0)) / elapsed, 6
        ),
    }
    return {
        "schema_version": REPORT_SCHEMA,
        "generated_at": utc_now(),
        "status": "ok" if all(checks.values()) else "partial",
        "policy": {
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "native_text_is_not_sanitized_or_identity_stripped": True,
            "locator_rows_copy_no_public_text": True,
            "pdf_locators_are_exact_pages": True,
            "markup_sections_come_only_from_observed_source_structure": True,
            "unproven_markup_structure_falls_back_to_exact_text_spans": True,
        },
        "configuration": {
            "locator_algorithm_version": DOCUMENT_LOCATOR_ALGORITHM_VERSION,
            "max_span_chars": max_span_chars,
            "max_average_locators_per_content": max_average_locators_per_content,
            "max_locators_per_content": max_locators_per_content,
            "markup_section_max_depth": markup_section_max_depth,
            "max_semantic_markup_bytes": max_semantic_markup_bytes,
            "pdf_locator": "page_number",
            "markup_locator": "source_xpath_plus_bounded_native_text_span",
            "markup_fallback_locator": "normalized_native_text_character_span",
        },
        "inputs": {
            "native_manifest": {
                "path": display_path(native_manifest),
                "bytes": native_manifest.stat().st_size,
                "sha256": metadata_values.get("native_manifest_sha256"),
            }
        },
        "state": {"database": display_path(state_db), "state_counts": state_counts},
        "manifest": dict(manifest),
        "run": dict(run_totals),
        "performance": report_performance,
        "totals": {
            "file_instances": file_instances,
            "distinct_content_objects": int(totals["content_objects"]),
            "native_text_chars": int(totals["native_text_chars"] or 0),
            "native_text_bytes": int(totals["native_text_bytes"] or 0),
            "content_locator_rows": int(locator_totals["locator_rows"] or 0),
            "instance_locator_rows": instance_locator_rows,
            "pdf_content_objects": int(totals["pdf_content_objects"] or 0),
            "markup_content_objects": int(totals["markup_content_objects"] or 0),
            "pdf_page_locators": int(locator_totals["pdf_page_locators"] or 0),
            "markup_section_locators": int(
                locator_totals["markup_section_locators"] or 0
            ),
            "normalized_text_span_locators": int(
                locator_totals["normalized_text_span_locators"] or 0
            ),
            "semantic_markup_content_objects": int(
                locator_totals["semantic_markup_content_objects"] or 0
            ),
            "fallback_markup_content_objects": int(
                locator_totals["fallback_markup_content_objects"] or 0
            ),
            "document_no_text_locators": int(locator_totals["no_text_locators"] or 0),
            "locators_with_text": int(locator_totals["locators_with_text"] or 0),
            "locator_text_chars": int(locator_totals["locator_text_chars"] or 0),
            "average_locator_rows_per_content": round(
                float(totals["average_locator_rows_per_content"] or 0), 6
            ),
            "max_locator_rows_per_content": int(
                totals["max_locator_rows_per_content"] or 0
            ),
            "projected_content_locator_rows_at_one_million_documents": round(
                float(totals["average_locator_rows_per_content"] or 0) * 1_000_000
            ),
        },
        "checks": checks,
        "next_action": (
            "Independently replay every raw/native object and page/section locator, "
            "then acquire a representative real office-format cohort before claiming "
            "office extraction support."
        ),
    }


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    positive = (
        int(args.max_span_chars),
        int(args.max_semantic_markup_bytes),
        float(args.max_average_locators_per_content),
        int(args.max_locators_per_content),
        float(args.pdf_timeout_seconds),
        int(args.workers),
        int(args.claim_size),
        int(args.max_attempts),
        int(args.lease_seconds),
        int(args.manifest_shard_max_rows),
        int(args.manifest_shard_max_uncompressed_bytes),
    )
    if (
        any(value <= 0 for value in positive)
        or int(args.max_items) < 0
        or int(args.markup_section_max_depth) < 0
    ):
        print("ERROR: locator bounds must be positive")
        return 2
    raw_root = Path(args.raw_root)
    native_root = Path(args.native_root)
    native_manifest = Path(args.native_manifest)
    state_db = Path(args.state_db)
    manifest_out = Path(args.manifest_out)
    report_out = Path(args.report_out)
    if (
        not raw_root.is_dir()
        or not native_root.is_dir()
        or not native_manifest.is_file()
    ):
        print("ERROR: real raw/native inputs are missing")
        return 2
    started = time.monotonic()
    usage_before = process_usage()
    try:
        with open_state(state_db) as conn:
            apply_schema(conn)
            seeded = seed_state(
                conn,
                native_manifest=native_manifest,
                max_span_chars=int(args.max_span_chars),
                markup_section_max_depth=int(args.markup_section_max_depth),
                max_semantic_markup_bytes=int(args.max_semantic_markup_bytes),
                max_attempts=int(args.max_attempts),
            )
            run_totals = run_worker(
                conn,
                raw_root=raw_root,
                native_root=native_root,
                workers=int(args.workers),
                claim_size=int(args.claim_size),
                max_items=int(args.max_items),
                lease_seconds=int(args.lease_seconds),
                max_span_chars=int(args.max_span_chars),
                pdf_timeout_seconds=float(args.pdf_timeout_seconds),
                markup_section_max_depth=int(args.markup_section_max_depth),
                max_semantic_markup_bytes=int(args.max_semantic_markup_bytes),
                max_locators_per_content=int(args.max_locators_per_content),
            )
            if terminal_state(conn):
                manifest = publish_manifest(
                    conn,
                    manifest_out,
                    max_rows=int(args.manifest_shard_max_rows),
                    max_uncompressed_bytes=int(
                        args.manifest_shard_max_uncompressed_bytes
                    ),
                )
            else:
                manifest = {
                    "path": display_path(manifest_out),
                    "rows": -1,
                    "publication": {
                        "activated": False,
                        "reason": "nonterminal_work_state",
                        "live_index_preserved": manifest_out.is_file(),
                        "automatic_deletion_performed": False,
                    },
                }
            usage_after = process_usage()
            performance = {
                "measurement_scope": "seed_rehash_locate_and_manifest",
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "cpu_seconds": round(
                    float(usage_after["cpu_seconds"])
                    - float(usage_before["cpu_seconds"]),
                    6,
                ),
                "peak_rss_bytes_self": int(usage_after["peak_rss_bytes_self"]),
                "peak_rss_bytes_child_max": int(
                    usage_after["peak_rss_bytes_child_max"]
                ),
            }
            report = build_report(
                conn,
                native_manifest=native_manifest,
                state_db=state_db,
                manifest=manifest,
                max_span_chars=int(args.max_span_chars),
                markup_section_max_depth=int(args.markup_section_max_depth),
                max_semantic_markup_bytes=int(args.max_semantic_markup_bytes),
                max_average_locators_per_content=float(
                    args.max_average_locators_per_content
                ),
                max_locators_per_content=int(args.max_locators_per_content),
                run_totals={"seeded": seeded, **run_totals},
                performance=performance,
            )
        write_json_atomic(report_out, report)
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if not args.enforce or report["status"] == "ok" else 1
    except (LocatorRunError, GenerationManifestError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
